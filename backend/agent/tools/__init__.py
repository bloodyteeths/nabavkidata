"""
Tool registry for the TenderUK AI agent.

Auto-discovers tool classes from all modules in this package.
Each tool must inherit from BaseTool.
"""

import importlib
import inspect
import pkgutil
from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class BaseTool(Protocol):
    """Protocol that all agent tools must satisfy."""

    name: str
    description: str
    parameters: dict

    async def execute(self, params: dict, conn: Any) -> dict: ...


class ToolRegistry:
    """
    Collects tool instances from all modules in agent.tools.

    Usage:
        registry = ToolRegistry()
        registry.discover()          # scans this package
        tool = registry.get("search_tenders")
        result = await tool.execute(params, conn)
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    @property
    def tools(self) -> dict[str, BaseTool]:
        return dict(self._tools)

    def tool_declarations(self) -> list[dict]:
        """
        Return tool declarations in the format expected by google-genai
        function calling (list of dicts with name, description, parameters).
        """
        decls = []
        for tool in self._tools.values():
            decls.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            )
        return decls

    def discover(self) -> None:
        """
        Auto-discover and register all tool classes in this package.

        Scans every module in agent.tools.* for classes that have
        the required attributes (name, description, parameters, execute).
        Skips this __init__ module.
        """
        package = importlib.import_module("agent.tools")
        for importer, modname, ispkg in pkgutil.iter_modules(
            package.__path__, prefix="agent.tools."
        ):
            if modname == "agent.tools":
                continue
            module = importlib.import_module(modname)
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    inspect.isclass(obj)
                    and hasattr(obj, "name")
                    and hasattr(obj, "description")
                    and hasattr(obj, "parameters")
                    and hasattr(obj, "execute")
                    and isinstance(getattr(obj, "name", None), str)
                ):
                    instance = obj()
                    self.register(instance)
