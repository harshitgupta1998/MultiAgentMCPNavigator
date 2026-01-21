from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Dict, Any
from crewai import Task, Crew, Process
from pydantic import ValidationError

from orchestrai.schemas import ResearchPacket, TaskPlan, ExecutionResult
from orchestrai.agents import build_research_agent, build_planner_agent, build_executor_agent
from orchestrai.tool_runner import ToolRunner
from orchestrai.mcp_tools import get_tool_names
from eval.judge import judge_run
from orchestrai.metrics import MetricsTracker, MetricEntry, infer_goal_type

# ============================================================================
# PARAMETER EXTRACTION FUNCTIONS (NEW)
# ============================================================================

def extract_city(text: str) -> str:
    """Extract city name from natural language query"""
    text_lower = text.lower()
    
    # Pattern 1: "weather in CITY" or "weather for CITY"
    match = re.search(r'\b(?:in|for)\s+([a-z]+(?:\s+[a-z]+)*?)(?:\s+weather|$|\?|,)', text_lower)
    if match:
        return match.group(1).strip().title()
    
    # Pattern 2: "CITY weather"
    match = re.search(r'\b([a-z]+(?:\s+[a-z]+)?)\s+weather', text_lower)
    if match:
        return match.group(1).strip().title()
    
    # Pattern 3: Look for capitalized words
    words = text.split()
    for i, word in enumerate(words):
        if word and word[0].isupper() and len(word) > 2:
            if i + 1 < len(words) and words[i + 1][0].isupper():
                return f"{word} {words[i + 1]}"
            return word
    
    # City abbreviations
    city_map = {"nyc": "New York", "sf": "San Francisco", "la": "Los Angeles"}
    for abbr, full_name in city_map.items():
        if abbr in text_lower:
            return full_name
    
    return "New York"

# ============================================================================
# GENERIC TOOL EXECUTION ENGINE (NEW)
# ============================================================================

async def execute_plan_tools(plan: TaskPlan, runner: ToolRunner, user_goal: str) -> Dict[str, Any]:
    """
    Execute all tools in the plan by extracting parameters from user_goal.
    Returns a dict of {tool_name: result}
    """
    results = {}
    
    for step in plan.steps:
        if not step.tools:
            continue
        
        for tool_name in step.tools:
            if tool_name in results:
                continue  # Already executed
            
            try:
                print(f"\n🔧 Executing: {tool_name}")
                
                # ===== TAVILY SEARCH (NEW!) =====
                if tool_name == "tavily_search":
                    result = await runner.call(tool_name, {
                        "query": user_goal,
                        "max_results": 10
                    })
                
                # ===== WEATHER =====
                elif tool_name == "get_weather":
                    city = extract_city(user_goal)
                    print(f"City: {city}")
                    result = await runner.call(tool_name, {"city": city})
                
                # ===== GITHUB =====
                elif tool_name == "create_issue":
                    match = re.search(
                        r'(?:in|for)\s+(?:repo\s+)?([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)',
                        user_goal
                    )
                    repo_full = match.group(1) if match else "deepmehta27/mcp-navigator-test"
                    owner, repo = repo_full.split('/')
                    
                    # Smart title extraction with quote priority
                    title = user_goal
                    
                    # Priority 1: Extract quoted text (highest priority)
                    quoted_match = re.search(r'["\']([^"\']+)["\']', user_goal)
                    if quoted_match:
                        title = quoted_match.group(1)
                    else:
                        # Priority 2: Extract after keywords like "issue", "titled", "called"
                        keyword_match = re.search(
                            r'(?:issue|titled|called|named)\s+["\']?([^"\']+?)["\']?(?:\s+(?:in|for|repo)|$)',
                            user_goal,
                            re.IGNORECASE
                        )
                        if keyword_match:
                            title = keyword_match.group(1).strip()
                        else:
                            # Priority 3: Remove boilerplate phrases
                            title = re.sub(r'create\s+(?:a\s+)?(?:github\s+)?issue\s+(?:about|for|on|titled)?\s*', '', title, flags=re.IGNORECASE)
                            title = re.sub(r'\s*(?:and\s+)?(?:in|for)\s+repo\s+[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+', '', title).strip()
                            # Remove leading "and" connectors
                            title = re.sub(r'^\s*(?:and|then)\s+', '', title, flags=re.IGNORECASE).strip()
                    
                    # Build body from ALL previous tool results
                    body = ""
                    if results:
                        body += "## Automated Issue Summary\n\n"
                        body += f"**Generated from:** {user_goal}\n\n"
                        body += "---\n\n"
                        
                        for tool_name_prev, result_data in results.items():
                            if tool_name_prev == "create_issue":
                                continue
                            
                            body += f"### Results from `{tool_name_prev}`\n\n"
                            result_str = str(result_data)
                            if len(result_str) > 2000:
                                result_str = result_str[:2000] + "\n\n... (truncated)"
                            
                            body += f"```\n{result_str}\n```\n\n"
                    else:
                        body = f"**Issue created via MCP Navigator**\n\n**Request:** {user_goal}"
                    
                    print(f"Creating issue with title: '{title}'")
                    result = await runner.call(tool_name, {
                        "owner": owner,
                        "repo": repo,
                        "title": title if title else user_goal,
                        "body": body
                    })


                elif tool_name == "list_issues":
                    match = re.search(
                        r'(?:in|for|from)\s+(?:repo\s+)?([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)',
                        user_goal
                    )
                    repo_full = match.group(1) if match else "deepmehta27/mcp-navigator-test"
                    owner, repo = repo_full.split('/')
                    print(f"Owner: {owner}, Repo: {repo}")
                    
                    # Request multiple issues per page
                    result = await runner.call(tool_name, {
                        "owner": owner,
                        "repo": repo,
                        "perPage": 100,
                        "state": "all"   
                    })

                elif tool_name == "get_file_contents":
                    match = re.search(
                        r'(?:in|for|from)\s+(?:repo\s+)?([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)',
                        user_goal
                    )
                    repo_full = match.group(1) if match else "deepmehta27/mcp-navigator-test"
                    owner, repo = repo_full.split('/')
                    
                    # Extract file path
                    path_match = re.search(r'(?:file|path)\s+([^\s]+)', user_goal)
                    path = path_match.group(1) if path_match else "README.md"
                    
                    print(f"Owner: {owner}, Repo: {repo}, Path: {path}")
                    result = await runner.call(tool_name, {
                        "owner": owner,
                        "repo": repo,
                        "path": path
                    })

                elif tool_name == "create_or_update_file":
                    match = re.search(
                        r'(?:in|for)\s+(?:repo\s+)?([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)',
                        user_goal
                    )
                    repo_full = match.group(1) if match else "deepmehta27/mcp-navigator-test"
                    owner, repo = repo_full.split('/')
                    
                    # Extract file path
                    path_match = re.search(r'(?:file|path)\s+([^\s]+)', user_goal)
                    path = path_match.group(1) if path_match else "test.txt"
                    
                    print(f"Owner: {owner}, Repo: {repo}, Path: {path}")
                    result = await runner.call(tool_name, {
                        "owner": owner,
                        "repo": repo,
                        "path": path,
                        "content": f"Updated via MCP Navigator: {user_goal}",
                        "message": f"Update from MCP Navigator"
                    })

                # Generic GitHub fallback
                elif tool_name.startswith(("create_", "list_", "get_", "update_", "search_")) and any(x in tool_name for x in ["issue", "repo", "pull", "branch"]):
                    # Try to extract owner/repo if possible
                    match = re.search(
                        r'(?:in|for|from)\s+(?:repo\s+)?([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)',
                        user_goal
                    )
                    if match:
                        repo_full = match.group(1)
                        owner, repo = repo_full.split('/')
                        result = await runner.call(tool_name, {
                            "owner": owner,
                            "repo": repo
                        })
                    else:
                        result = await runner.call(tool_name, {})
                
                # ===== FALLBACK =====
                else:
                    result = await runner.call(tool_name, {})
                
                # Store result
                result_str = str(result)
                results[tool_name] = result_str[:2000] if len(result_str) > 2000 else result_str
                print(f"Preview: {result_str[:150]}...")
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                print(f"⚠️  Failed: {error_msg}")
                results[tool_name] = error_msg
    
    return results


def _parse(model_cls, text: str):
    return model_cls.model_validate_json(text)


# ============================================================================
# MAIN ORCHESTRATION (UPDATED)
# ============================================================================

async def run_orchestration(user_goal: str, tools) -> ExecutionResult:
    # Start timing
    start_time = time.time()
    
    # Initialize metrics tracker
    metrics = MetricsTracker()
    
    # ----------------------------
    # 0. SETUP
    # ----------------------------
    research_agent = build_research_agent(tools)
    planner_agent = build_planner_agent(tools)
    executor_agent = build_executor_agent(tools)
    runner = ToolRunner(tools)
    
    print("Available MCP tools:", runner.list_tools())
    
    allowed_tools = ", ".join(get_tool_names(tools))

    # ----------------------------
    # 1. CREATE PLAN
    # ----------------------------
    plan_task = Task(
    description=(
        "You are the Task Planner.\n\n"
        "Create a task plan for the following goal.\n\n"
        "CRITICAL RULES (VIOLATION = FAILURE):\n"
        "1. Return ONLY valid JSON\n"
        "2. JSON MUST match this schema exactly:\n"
        f"{TaskPlan.model_json_schema()}\n\n"
        "3. You may ONLY use tool names from this list:\n"
        f"{allowed_tools}\n\n"
        "TOOL SELECTION RULES:\n"
        "- For web searches: Use 'tavily_search' (reliable, fast)\n"
        "- For weather: Use 'get_weather'\n"
        "- For GitHub: Use 'create_issue', 'list_issues', 'create_or_update_file'\n"
        "- Prefer simple, single-step solutions\n\n"
        "**MULTI-TOOL RULES:**\n"
        "- Each step should have EXACTLY ONE tool\n"
        "- If you need data from Tool A to use in Tool B, create TWO steps:\n"
        "  Step 1: Use Tool A to gather data\n"
        "  Step 2: Use Tool B with the data from Step 1\n"
        "- NEVER combine tools that depend on each other in the same step\n"
        "- Example: 'search then create issue' = 2 steps, NOT 1 step\n\n"
        "DO NOT invent tools.\n"
        "DO NOT use generic terms like 'browser', 'internet', or 'API'.\n"
        "If no tool is needed for a step, omit the tools field.\n\n"
        f"Goal: {user_goal}"
    ),
    expected_output="Valid JSON matching TaskPlan schema",
    agent=planner_agent,
)

    planner_crew = Crew(
        agents=[planner_agent],
        tasks=[plan_task],
        process=Process.sequential,
        verbose=True,
    )

    raw_plan = planner_crew.kickoff()
    if not isinstance(raw_plan, str):
        raw_plan = str(raw_plan)

    # ----------------------------
    # SANITIZE PLANNER OUTPUT
    # ----------------------------
    raw_plan = raw_plan.strip()

    if raw_plan.startswith("```"):
        raw_plan = raw_plan.strip("`").strip()
        if raw_plan.lower().startswith("json"):
            raw_plan = raw_plan[4:].strip()

    # ----------------------------
    # 2. VALIDATE PLAN (HARD GATE)
    # ----------------------------
    try:
        task_plan = TaskPlan.model_validate_json(raw_plan)
    except ValidationError as e:
        raise RuntimeError(
            f"Planner produced invalid TaskPlan.\n\n"
            f"Validation error:\n{e}\n\n"
            f"Raw output:\n{raw_plan}"
        )
    
    # Validate tool names
    allowed = set(get_tool_names(tools))
    print(f"\n✅ Allowed tools: {sorted(allowed)}")
    
    for step in task_plan.steps:
        for tool in step.tools or []:
            if tool not in allowed:
                raise RuntimeError(
                    f"\nVALIDATION FAILED: Planner used invalid tool '{tool}' in step {step.step_id}.\n"
                    f"Allowed tools: {sorted(allowed)}\n\n"
                    f"Full plan:\n{task_plan.model_dump_json(indent=2)}"
                )
    
    print(f"✅ Plan validated: {len(task_plan.steps)} steps, all tools valid\n")

    # ----------------------------
    # 3. EXECUTE ALL TOOLS IN PLAN
    # ----------------------------
    print("\n" + "="*60)
    print("🔧 EXECUTING TOOLS FROM PLAN")
    print("="*60)

    tool_results = await execute_plan_tools(task_plan, runner, user_goal)

    # DEBUG: Show what we got
    print(f"\n📦 Tool results collected: {len(tool_results)} tools")
    for tool_name, result in tool_results.items():
        print(f"  - {tool_name}: {result[:100]}..." if len(str(result)) > 100 else f"  - {tool_name}: {result}")

    if not tool_results:
        print("WARNING: No tool results collected!")
    
    # ----------------------------
    # 4. OPTIONAL RESEARCH STEP (EXISTING)
    # ----------------------------
    print("\nSkipping research (using direct tool execution)")
    research_output = '{"query": "' + user_goal + '", "findings": [], "notes": "Skipped - using tool results directly"}'

    # ----------------------------
    # 5. RUN EXECUTOR (WITH TOOL RESULTS)
    # ----------------------------
    exec_description = (
    "You are the Action Executor.\n\n"
    "You MUST use the tool results below to complete the user's goal.\n\n"
    f"Task Plan:\n{task_plan.model_dump_json(indent=2)}\n\n"
)

    if tool_results:
        exec_description += "\n**Tool Execution Results:**\n"
        for tool_name, result in tool_results.items():
            exec_description += f"\n{tool_name}:\n{result}\n"
        
    exec_description += (
            "\n**CRITICAL INSTRUCTIONS:**\n"
            "1. Synthesize ALL tool results above into a coherent answer\n"
            "2. If multiple steps were executed, combine the results logically\n"
            "3. For example, if you searched for repos AND created an issue:\n"
            "   - Extract repo names/URLs from search results\n"
            "   - Format them into a summary\n"
            "   - Confirm the issue was created with that summary\n"
            "4. DO NOT just say 'task completed' - provide specific details\n"
            "5. Show what data was found and what action was taken\n\n"
            f"Original user goal: {user_goal}"
        )
    
    exec_task = Task(
        description=exec_description,
        expected_output="Final answer for the user",
        agent=executor_agent,
    )

    executor_crew = Crew(
        agents=[executor_agent],
        tasks=[exec_task],
        process=Process.sequential,
        verbose=False,
    )

    # Execute with error handling
    try:
        raw_exec = executor_crew.kickoff()
        if not isinstance(raw_exec, str):
            raw_exec = str(raw_exec)
        execution_succeeded = True
        execution_errors = []
        
    except Exception as e:
        raw_exec = f"Execution failed: {str(e)}"
        execution_succeeded = False
        execution_errors = [str(e)]

    # ----------------------------
    # 6. EVALUATE WITH JUDGE
    # ----------------------------
    judge = judge_run(
        goal=user_goal,
        plan=task_plan.model_dump(),
        final_answer=raw_exec,
        trace=None,
    )

    print(f"\n📊 Judge scores: Success={judge.success}/5, Plan={judge.plan_quality}/5, Reasoning={judge.reasoning_quality}/5")
    print(f"Notes: {judge.notes}\n")
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Extract tools used from plan
    tools_used = []
    for step in task_plan.steps:
        if step.tools:
            tools_used.extend(step.tools)
    tools_used = list(set(tools_used))  # Deduplicate
    
    # Log metrics
    metric_entry = MetricEntry(
        timestamp=datetime.now().isoformat(),
        goal=user_goal,
        goal_type=infer_goal_type(user_goal),
        success_score=judge.success,
        plan_score=judge.plan_quality,
        reasoning_score=judge.reasoning_quality,
        execution_time_seconds=execution_time,
        completed=execution_succeeded,
        errors=execution_errors,
        tools_used=tools_used,
    )
    metrics.log(metric_entry)
    
    # Print quick stats
    print(f"⏱️  Execution time: {execution_time:.2f}s")
    
    return ExecutionResult(
        goal=user_goal,
        completed=execution_succeeded,
        outputs={
            "plan": task_plan.model_dump(),
            "research": research_output,
            "judge": judge.model_dump(),
            "tool_results": tool_results,  
            "execution_time": execution_time,
        },
        errors=execution_errors,
        final_answer=raw_exec,
    )
# ============================================================================