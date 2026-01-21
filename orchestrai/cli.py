from __future__ import annotations

import asyncio
from datetime import datetime
from dotenv import load_dotenv
from orchestrai.metrics import MetricsTracker
from .mcp_tools import load_mcp_tools, get_tool_names
from .workflow import run_orchestration

def print_banner():
    """Display startup banner"""
    print("\n" + "=" * 60)
    print("MCP NAVIGATOR 2.0 - Multi-Agent Orchestration System")
    print("=" * 60)

def print_tools_loaded(tools):
    """Display loaded tools in organized categories"""
    tool_names = get_tool_names(tools)
    
    # Categorize tools
    search_tools = [t for t in tool_names if 'tavily' in t]
    github_tools = [t for t in tool_names if 'github' in t.lower() or any(x in t for x in ['issue', 'repo', 'pull', 'branch'])]
    weather_tools = [t for t in tool_names if 'weather' in t]
    
    print("\n📦 Loaded MCP Tools:")
    if search_tools:
        print(f"Search: {', '.join(search_tools)}")
    if weather_tools:
        print(f"Weather: {', '.join(weather_tools)}")
    if github_tools:
        print(f"GitHub: {', '.join(github_tools[:3])}..." if len(github_tools) > 3 else f"   GitHub: {', '.join(github_tools)}")
    
    print(f"\n   Total: {len(tool_names)} tools across 3 servers")

def print_help():
    """Display usage examples and commands"""
    print("\nExamples:")
    print(" Search:")
    print("      - Find the latest AI news")
    print("      - Search for Python best practices")
    print()
    print(" GitHub:")
    print("      - Create an issue in owner/repo titled 'Bug fix needed'")
    print("      - List issues for deepmehta27/mcp-navigator")
    print("      - Get file contents from my-username/my-repo")
    print()
    print(" Weather:")
    print("      - What's the weather in San Francisco?")
    print("      - Weather in NYC")
    print()
    print(" Multi-step:")
    print("      - Search for trending AI repos and create GitHub issue summary")
    print("      - Weather in Tokyo and list issues in travel-planner repo")
    print()
    print("Commands:")
    print("   metrics       - View performance metrics")
    print("   metrics 5     - View last 5 runs")
    print("   help          - Show this help message")
    print("   clear         - Clear screen")
    print("   exit          - Quit the application")
    print("\n" + "-" * 60)

async def main():
    load_dotenv()
    
    # Display banner
    print_banner()
    
    # Load tools
    print("\n⏳ Loading MCP servers...")
    try:
        tools, _ = await load_mcp_tools()
    except Exception as e:
        print(f"❌ Failed to load tools: {e}")
        return
    
    # Display loaded tools
    print_tools_loaded(tools)
    
    # Initialize metrics
    metrics = MetricsTracker()
    
    # Show help
    print_help()
    
    # Main loop
    while True:
        try:
            # Prompt with timestamp
            prompt = f"\n💬 You [{datetime.now().strftime('%H:%M')}]: "
            user_input = input(prompt).strip()
            
            # Handle empty input
            if not user_input:
                continue
            
            # Handle commands
            cmd = user_input.lower()
            
            if cmd == "exit":
                print("\n👋 Goodbye! Thanks for using MCP Navigator.\n")
                break
            
            elif cmd == "help":
                print_help()
                continue
            
            elif cmd == "clear":
                print("\033[2J\033[H")  # ANSI clear screen
                print_banner()
                print_tools_loaded(tools)
                continue
            
            elif cmd.startswith("metrics"):
                parts = user_input.split()
                last_n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                metrics.print_summary(last_n)
                continue
            
            # Execute workflow
            print(f"\n{'='*60}")
            print(f"🤖 Processing: {user_input}")
            print(f"{'='*60}")
            
            try:
                result = await run_orchestration(user_input, tools)
                
                # Display result
                print(f"\n{'─'*60}")
                print("✅ FINAL ANSWER")
                print(f"{'─'*60}")
                print(result.final_answer)
                print(f"{'─'*60}\n")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Task cancelled by user\n")
                continue
                
            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")
                continue
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break
        except EOFError:
            print("\n\n👋 Goodbye!\n")
            break

if __name__ == "__main__":
    asyncio.run(main())
