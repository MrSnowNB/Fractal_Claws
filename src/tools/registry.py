"""
src/tools/registry.py — Lightweight tool registry for the Fractal_Claws tool layer.

Provides ToolRegistry, ToolNotFoundError, ToolArgError used by runner.py
and test_tools.py / test_runner_dispatch.py.
"""

from typing import Any, Callable, Dict, List, Optional


class ToolNotFoundError(KeyError):
    """Raised when a tool name is not registered."""


class ToolArgError(TypeError):
    """Raised when required args are missing or of wrong type."""


class ToolRegistry:
    """
    Registry mapping tool names to callables with optional schema validation.

    Schema format (per arg):
        {
            "arg_name": {
                "type":     <python type>,
                "required": bool,
                "default":  <value>   # only when required=False
            }
        }
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        fn: Callable,
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a callable under the given name."""
        self._tools[name] = fn
        self._schemas[name] = schema or {}

    def call(self, name: str, args: Dict[str, Any]) -> Any:
        """Validate args against schema, then call the registered tool.

        Raises:
            ToolNotFoundError: tool name not registered.
            ToolArgError: required arg missing or wrong type.
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool not found: {name!r}")

        schema = self._schemas[name]
        resolved: Dict[str, Any] = {}

        for arg_name, spec in schema.items():
            required = spec.get("required", True)
            expected_type = spec.get("type")

            if arg_name in args:
                value = args[arg_name]
                if expected_type is not None and not isinstance(value, expected_type):
                    raise ToolArgError(
                        f"Tool {name!r}: arg {arg_name!r} expected "
                        f"{expected_type.__name__}, got {type(value).__name__}"
                    )
                resolved[arg_name] = value
            elif required:
                raise ToolArgError(
                    f"Tool {name!r}: required arg {arg_name!r} missing"
                )
            else:
                resolved[arg_name] = spec.get("default")

        # Pass through extra args not in schema
        for k, v in args.items():
            if k not in resolved:
                resolved[k] = v

        return self._tools[name](**resolved)

    def list_tools(self) -> List[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools.keys())
