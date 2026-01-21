# Unified LangGraph agent client
import os
import sys
import json
import time
import socket
import subprocess
import asyncio
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

# ---- Pretty step-by-step tracing via a LangChain callback -------------------
try:
    from langchain_core.callbacks import BaseCallbackHandler
except Exception:
    # Older LangChain fallback import
    from langchain.callbacks.base import BaseCallbackHandler  # type: ignore

class StepPrinter(BaseCallbackHandler):
    """Prints each tool call with inputs/outputs so we can see the agent's decisions live."""
    def __init__(self):
        self.step = 0

    def _tick(self) -> int:
        self.step += 1
        return self.step

    def on_tool_start(self, serialized, input_str, **kwargs):
        n = self._tick()
        tool = serialized.get("name", "Tool")
        print(f"\n[Step {n}] → Calling tool: {tool}")
        print(f"           • input: {input_str}")

    def on_tool_end(self, output, **kwargs):
        # Truncate very large outputs for readability
        out = str(output)
        if len(out) > 1200:
            out = out[:1200] + " ...[truncated]"
        print(f"           • output: {out}")

    def on_tool_error(self, error, **kwargs):
        print(f"           • ERROR: {error}")

# ---- Env & small helpers ----------------------------------------------------
load_dotenv()  #load .env

# Respect OPENAI* envs from .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY  # ensure downstream libs see it

def repo_path(*parts: str) -> str:
    """
    Resolve a path relative to the repository root (this file's parent).
    """
    root = Path(__file__).resolve().parent
    return str((root / Path(*parts)).resolve())

def ensure_weather_server() -> None:
    """
    If Weather MCP (HTTP) is not running on :8000, start it detached.
    """
    s = socket.socket()
    try:
        s.settimeout(0.3)
        s.connect(("127.0.0.1", 8000))
        s.close()
        return  # already running
    except Exception:
        pass
    
    print("Starting Weather MCP on :8000")
    # On Windows, DETACHED_PROCESS avoids tying the child to the parent console.
    DETACHED = 0x00000008 if sys.platform == "win32" else 0
    subprocess.Popen(
        [sys.executable, repo_path("servers", "weather.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=DETACHED,
    )

async def build_agent():
    """
    Create a MultiServerMCPClient for Notes + Weather (+ optional browser MCPs),
    fetch tools, and return a LangGraph ReAct agent with step printing enabled.
    """
    # Ensure Weather HTTP server is available
    ensure_weather_server()

    # Base connections: Notes (stdio) + Weather (HTTP)
    connections = {
        "notes": {
            "command": sys.executable,
            "args": [repo_path("servers", "notes_server.py")],
            "transport": "stdio",
        },
        "weather": {
            "url": "http://localhost:8000/mcp",
            "transport": "streamable_http",
        },
    }

    # load Node MCPs (Playwright, DuckDuckGo, Airbnb) from browser_mcp.json
    browser_cfg_path = Path(repo_path("servers", "browser_mcp.json"))
    if browser_cfg_path.exists():
        try:
            cfg = json.loads(browser_cfg_path.read_text(encoding="utf-8"))
            mcp_servers = cfg.get("mcpServers", {})
            for name, spec in mcp_servers.items():
                # These run via npx using stdio transport
                connections[name] = {
                    "command": spec.get("command"),
                    "args": spec.get("args", []),
                    "transport": "stdio",
                }
        except Exception as e:
            print(f"Warning: failed to load browser_mcp.json: {e}")

    # Initialize MCP client and discover tools across all servers
    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()

    # Clear system guidance so the agent knows WHEN to use what
    system = (
    "You are a tool-using assistant.\n"
    "- Use 'Notes' for CRUD and search of local notes.\n"
    "- Use 'Weather' for city weather.\n"
    "- Use Playwright when web interaction is required. "
    "When using Playwright, complete the entire task in the SAME session "
    "(navigate, type, click, extract), and only finish after you’ve extracted the final answer. "
    "Avoid opening/closing the browser multiple times.\n"
    "- Use duckduckgo-search for quick info without browsing.\n"
    "Be concise and return a clear final answer."
    )

    # LLM (OpenAI by default; swap to Groq later if you want)
    llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)

    # Add our step printer so the CLI shows each tool call
    step_printer = StepPrinter()

    # Create a ReAct-style agent that can call tools
    agent = create_react_agent(llm, tools)
    return agent, system

# ---- CLI --------------------------------------------------------------------
async def run_cli():
    """
    Simple REPL-style CLI that lets you chat with the agent.
    It prints the final answer AND the step-by-step tool calls used.
    """
    agent, system = await build_agent()
    history = []  # minimal in-memory conversation so the agent has context
    step_printer = StepPrinter()


    print("\nMCP Navigator — CLI (OpenAI only)")
    print("=" * 56)
    print("Examples:")
    print("  • Create a note titled 'ideas' with content 'Ship MCP demo on Friday'")
    print("  • List my notes")
    print("  • Weather in New York")
    print("  • browse: open google.com, then go to airbnb.com and find cheapest NYC stays on 13 Aug")
    print("      - Use 'browse: clear' to clear Playwright memory\n")
    print("Type 'exit' to quit.")
    print("=" * 56 + "\n")

    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye!")
            return

        if not q:
            continue
        if q.lower() in {"exit", "quit","bye"}:
            print("bye!")
            return

        # Assemble messages (simple memory)
        messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": q}]

        t0 = time.time()
        result = await agent.ainvoke({"messages": messages}, config = {"callbacks":[step_printer]},
        )
        ms = (time.time() - t0) * 1000

        # Final model message is the answer
        answer = result["messages"][-1].content
        print(f"\n[Final Answer] {answer}\n(took {ms:.0f} ms)\n")

        # Save turn to history
        history.extend(
            [
                {"role": "user", "content": q},
                {"role": "assistant", "content": answer},
            ]
        )

if __name__ == "__main__":
    asyncio.run(run_cli())