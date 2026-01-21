from __future__ import annotations
from typing import Any, Dict, List


class ToolRunner:
    def __init__(self, tools: List[Any]):
        self.tools = tools
        self.by_name = {}
        for t in tools:
            name = getattr(t, "name", None)
            if name:
                self.by_name[name] = t

    def list_tools(self) -> List[str]:
        return sorted(self.by_name.keys())

    async def call(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name not in self.by_name:
            raise KeyError(f"Tool '{tool_name}' not found. Available: {self.list_tools()}")
        
        tool = self.by_name[tool_name]
        
        # SPECIAL HANDLING: Weather tool requires "location" not "city"
        if tool_name == "get_weather" and "city" in args:
            # Transform to correct schema
            city = args["city"]
            args = {
                "location": {
                    "city": city,
                    "state": "",
                    "country": "US"
                }
            }

        # LangChain tools support ainvoke for async calls
        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke(args)
        # Fallback (rare)
        if hasattr(tool, "invoke"):
            return tool.invoke(args)

        raise TypeError(f"Tool '{tool_name}' is not invokable")
