from __future__ import annotations
import os
from crewai import Agent
from langchain_openai import ChatOpenAI
from typing import List, Any

from .mcp_tools import filter_tools

def _llm() -> ChatOpenAI:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model, temperature=0)


def build_research_agent(all_tools: List[Any]) -> Agent:
    return Agent(
        role="Research Coordinator",
        goal="Gather accurate, relevant information using search and browsing tools.",
        backstory="You are careful, skeptical, and cite sources in your own scratch notes.",
        llm=_llm(),
        allow_delegation=False,
        verbose=False,
        tools=[]
    )


def build_planner_agent(all_tools: List[Any]) -> Agent:
    tools = []
    return Agent(
        role="Task Planner",
        goal="Convert user goals into a structured step-by-step plan, track it in Notes.",
        backstory=(
            "You create deterministic plans with clear success criteria and tool choices.\n\n"
            "TOOL SELECTION RULES:\n"
            "- For web searches: Use 'tavily_search'\n"
            "- For weather: Use 'get_weather'\n"
            "- Keep plans simple - prefer single-step solutions"
        ),
        llm=_llm(),
        allow_delegation=False,
        verbose=True,
        tools=[],
    )


def build_executor_agent(all_tools: List[Any]) -> Agent:
    tools = filter_tools(all_tools, allow=["weather"])
    return Agent(
        role="Action Executor",
        goal=(
            "Execute the plan using the provided tool results.\n"
            "Rules:\n"
            "- DO NOT retry tools\n"
            "- DO NOT explain failures\n"
            "- DO NOT include thoughts or reasoning\n"
            "- If tool data is missing, state failure clearly and stop\n"
            "- Output ONLY the final user-facing answer"
        ),
        backstory="You are practical and focus on completing tasks with tool calls.",
        llm=_llm(),
        allow_delegation=False,
        verbose=True,
        tools=[]
    )
