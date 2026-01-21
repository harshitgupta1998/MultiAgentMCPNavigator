# MCP Navigator 2.0

A production-style multi-agent orchestration system built with CrewAI and the Model Context Protocol (MCP). Demonstrates role-based agent collaboration, LLM-as-judge evaluation, and enterprise-grade tool integration patterns.

## 🚀 What's New in v2.0

**v2.0** is a complete architectural rebuild focused on **production patterns over demos**:

- **Multi-Agent Architecture**: Role-based CrewAI agents (Task Planner, Action Executor) with strict JSON schemas
- **LLM-as-Judge Evaluation**: Every execution auto-scored on success, plan quality, and reasoning
- **Enterprise Tool Integration**: GitHub API (issues, PRs, repos), Tavily search (4 tools), custom Weather MCP server
- **Production Observability**: Persistent metrics tracking, performance visualization, goal-type inference
- **Robust Error Handling**: Parameter validation, connection retries, graceful fallbacks

**Results from ~60+ test runs:**
- ≈4/5 average plan quality across all dimensions
- ~15-20s end-to-end execution for multi-step workflows
- 90%+ tool routing accuracy with explicit failure reporting
- 100% success rate on weather/search queries

## 🏗️ Architecture

### Multi-Agent System (CrewAI)
```
User Query → Task Planner → Tool Execution → Action Executor → LLM Judge → Final Answer
              ↓                    ↓                              ↓
         (Pydantic          (Async parallel           (Score + persist
          TaskPlan)          execution)                 metrics)
```

**Three specialized agents:**
1. **Task Planner**: Creates validated execution plans with strict tool constraints
2. **Action Executor**: Synthesizes tool results into user-facing answers
3. **Research Coordinator**: Optional deep-dive research (disabled by default for speed)

### MCP Server Integration
- **GitHub MCP** (`@modelcontextprotocol/server-github`): 20+ tools for repo management, issues, PRs
- **Tavily MCP** (`mcp-remote` bridge): Reliable web search with 4 specialized tools (search, extract, crawl, map)
- **Weather MCP** (custom FastAPI): Built from scratch with SSE transport for real-time data

### Tool Execution Engine
Centralized, generic tool router with:
- Smart parameter extraction (regex-based parsing for owner/repo, city names, file paths)
- Async parallel execution for multi-step workflows
- Type-safe tool result passing between agents
- Graceful error handling with explicit failure messages

### Evaluation & Observability
- **LLM-as-Judge** (`eval/judge.py`): Auto-scores every run on 3 dimensions (0-5 scale)
- **Metrics Tracking** (`orchestrai/metrics.py`): Persistent JSON logs with goal type inference
- **Performance Visualization** (`view_metrics.py`): Aggregates, trends, success rates

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ (for MCP servers)
- OpenAI API key
- GitHub Personal Access Token (for GitHub MCP)
- Tavily API key (for search)

### Setup
```bash
# Clone and install
git clone https://github.com/deepmehta27/MCP_Navigator.git
cd MCP_Navigator
pip install -r requirements.txt

# Install MCP servers
npm install -g @modelcontextprotocol/server-github
npm install -g mcp-remote

# Configure environment
cp .env.example .env
# Add: OPENAI_API_KEY, GITHUB_TOKEN, TAVILY_API_KEY
```

### Configuration
Edit `servers/browser_mcp.json` for MCP server connections:
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "tavily": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "tavily"],
      "env": {
        "TAVILY_API_KEY": "${TAVILY_API_KEY}"
      }
    }
  }
}
```

## 🎯 Usage

### Starting the CLI
```bash
python orchestrai/cli.py
```

### Example Workflows

#### Web Search
```
You: Search for the latest multi-agent AI frameworks in 2026
→ Plan: 1-step (tavily_search)
→ Result: CrewAI, LangGraph, AutoGen, LlamaIndex...
→ Judge: Success=4/5, Plan=4/5, Reasoning=4/5
```

#### Weather Queries
```
You: What's the weather in San Francisco?
→ Plan: 1-step (get_weather)
→ Result: 15.9°C, wind 9.1 km/h
→ Judge: Success=5/5, Plan=5/5, Reasoning=5/5
```

#### GitHub Operations
```
You: List issues for deepmehta27/mcp-navigator-test
→ Plan: 1-step (list_issues)
→ Result: [Issue #1..... ]
→ Judge: Success=5/5

You: Create an issue titled "Add streaming support"
→ Plan: 1-step (create_issue)
→ Result: Issue #10 created
→ Judge: Success=5/5
```

#### Multi-Step Workflows
```
You: Search for trending AI repos and create GitHub issue summary
→ Plan: 2 steps (tavily_search → create_issue)
→ Tool 1: Finds 12 trending repos
→ Tool 2: Creates issue with formatted summary
→ Judge: Success=5/5, Plan=4/5
```

### Viewing Metrics
```bash
python view_metrics.py

# Output:
# Total Runs: 60
# Success Rate: 93.3%
# Avg Success Score: 4.5/5
# Avg Plan Score: 4.0/5
# Performance Trend: ↑ IMPROVING
```

## 📊 System Design Decisions

### Why CrewAI over LangGraph?
- **Role-based separation**: Cleaner agent boundaries vs. monolithic ReAct loop
- **Built-in schema validation**: Pydantic TaskPlan enforcement at agent boundaries
- **Easier debugging**: Sequential agent execution = linear trace inspection

### Why Tavily over DuckDuckGo?
- **Reliability**: DuckDuckGo MCP had anti-bot issues causing 40%+ failures
- **Quality**: Tavily returns structured results with relevance scores
- **Speed**: Sub-second response times vs. 3-5s for DuckDuckGo

### Why Custom Weather MCP?
- Existing weather tools lacked proper MCP transport implementation
- Built with FastAPI + SSE for streaming real-time data
- Full control over error handling and retry logic

### Why LLM-as-Judge?
- **Automated quality tracking**: No manual evaluation needed across 60+ runs
- **Regression detection**: Catches plan quality degradation early
- **Systematic debugging**: Judge notes pinpoint exact failure reasons

## 🧪 Development

### Project Structure
```
MCP_Navigator/
├── orchestrai/
│   ├── cli.py              # Main CLI application
│   ├── workflow.py         # Multi-agent orchestration logic
│   ├── agents.py           # CrewAI agent definitions
│   ├── schemas.py          # Pydantic models (TaskPlan, ExecutionResult)
│   ├── mcp_tools.py        # MCP server connection management
│   ├── tool_runner.py      # Generic tool execution engine
│   └── metrics.py          # Metrics tracking and persistence
├── eval/
│   └── judge.py            # LLM-as-judge evaluation
├── servers/
│   ├── weather.py          # Custom Weather MCP server
│   └── browser_mcp.json    # MCP server configuration
├── data/
│   └── metrics.json        # Persistent execution metrics
└── view_metrics.py         # Metrics visualization CLI
```

### Running Tests
```bash
# Manual test suite (no pytest yet - realistic for v2.0)
python orchestrai/cli.py
> Search for AI frameworks
> Weather in NYC
> Create issue in deepmehta27/mcp-navigator-test titled "Test"
> metrics
```

### Adding New MCP Servers
1. Add server to `servers/browser_mcp.json`
2. Update `TOOL SELECTION RULES` in `workflow.py` planner prompt
3. Add parameter extraction logic to `execute_plan_tools()` if needed
4. Test tool routing with sample queries

## 🐛 Known Limitations

- **Notes server removed**: Inconsistent parameter contracts caused failures (pragmatic cut)
- **Research agent disabled by default**: Adds 10-15s latency with minimal quality gain
- **No streaming UI**: CLI shows final results only (batch mode)
- **Single-user only**: No auth, rate limiting, or multi-tenancy
tes deployment guide for production scale

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions welcome! Focus areas:
- **New MCP integrations**: Slack, Calendar, Database tools
- **Evaluation improvements**: Add precision/recall metrics for search quality
- **Performance optimization**: Reduce cold-start latency (<10s target)
- **Documentation**: Production deployment guides

***

Made with ❤️ by Deep Mehta
