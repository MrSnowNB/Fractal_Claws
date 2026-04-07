"""tools/registry.py — ToolRegistry with schema validation."""
from __future__ import annotations
import json
import time
import os
from typing import Any, Callable, Dict, Optional


class ToolNotFoundError(Exception):
    """Raised when a tool name is not registered in the registry."""
    pass


class ToolArgError(Exception):
    """Raised when tool arguments fail validation."""
    pass


def _log_entry(path: str, record: dict) -> None:
    """Append a JSONL record to the journal."""
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


class ToolRegistry:
    """Maps tool name strings to callables with schema validation."""

    def __init__(self) -> None:
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        callable: Callable[..., Any],
        schema: Dict[str, Dict[str, Any]],
    ) -> None:
        """Register a tool with its schema."""
        self._tools[name] = {"callable": callable, "schema": schema}

    def call(self, name: str, args: Dict[str, Any]) -> Any:
        """Call a registered tool with argument validation."""
        # Log dispatch start
        _log_entry(
            "logs/luffy-journal.jsonl",
            {
                "ticket_id": "STEP-02-B",
                "step": "registry.call",
                "tool": name,
                "args": args,
                "status": "start",
                "detail": "dispatching tool call",
            },
        )

        if name not in self._tools:
            _log_entry(
                "logs/luffy-journal.jsonl",
                {
                    "ticket_id": "STEP-02-B",
                    "step": "registry.call",
                    "tool": name,
                    "status": "fail",
                    "detail": f"tool '{name}' not found",
                },
            )
            raise ToolNotFoundError(f"tool '{name}' not found")

        tool_def = self._tools[name]
        schema = tool_def["schema"]
        callable_fn = tool_def["callable"]

        # Validate arguments
        final_args: Dict[str, Any] = {}

        for arg_name, arg_spec in schema.items():
            arg_type = arg_spec.get("type")
            is_required = arg_spec.get("required", False)
            default = arg_spec.get("default")

            if arg_name in args:
                value = args[arg_name]
                if arg_type is not None and not isinstance(value, arg_type):
                    _log_entry(
                        "logs/luffy-journal.jsonl",
                        {
                            "ticket_id": "STEP-02-B",
                            "step": "registry.call",
                            "tool": name,
                            "status": "fail",
                            "detail": f"argument '{arg_name}' expected {arg_type}, got {type(value)}",
                        },
                    )
                    raise ToolArgError(
                        f"argument '{arg_name}' expected {arg_type}, got {type(value)}"
                    )
                final_args[arg_name] = value
            else:
                if is_required:
                    _log_entry(
                        "logs/luffy-journal.jsonl",
                        {
                            "ticket_id": "STEP-02-B",
                            "step": "registry.call",
                            "tool": name,
                            "status": "fail",
                            "detail": f"required argument '{arg_name}' is missing",
                        },
                    )
                    raise ToolArgError(f"required argument '{arg_name}' is missing")
                if default is not None:
                    final_args[arg_name] = default

        # Pass through extra args not in schema (forward-compatible)
        for extra_arg in args:
            if extra_arg not in schema:
                final_args[extra_arg] = args[extra_arg]

        try:
            result = callable_fn(**final_args)
            _log_entry(
                "logs/luffy-journal.jsonl",
                {
                    "ticket_id": "STEP-02-B",
                    "step": "registry.call",
                    "tool": name,
                    "status": "pass",
                    "detail": f"tool returned successfully",
                },
            )
            return result
        except Exception as e:
            _log_entry(
                "logs/luffy-journal.jsonl",
                {
                    "ticket_id": "STEP-02-B",
                    "step": "registry.call",
                    "tool": name,
                    "status": "fail",
                    "detail": str(e),
                },
            )
            raise

    def list_tools(self) -> list[str]:
        """Return a list of registered tool names."""
        return list(self._tools.keys())