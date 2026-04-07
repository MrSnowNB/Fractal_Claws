# tools/registry.py — T06
# Terminal tool registry for toolbox.yaml entries.

from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class ToolDef:
    """Definition of a tool from toolbox.yaml."""
    name: str
    path: str
    stage: str
    description: str
    risk: str = "low"


def load_registry(path: str = "tools/toolbox.yaml") -> Dict[str, ToolDef]:
    """Load tool registry from toolbox.yaml."""
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    registry = {}
    for entry in data.get("tools", []):
        tool = ToolDef(
            name=entry["name"],
            path=entry["path"],
            stage=entry["stage"],
            description=entry.get("description", ""),
            risk=entry.get("risk", "low"),
        )
        registry[tool.name] = tool
    return registry


def list_tools(stage: str = "bud") -> List[ToolDef]:
    """Return tools available at or below the given stage."""
    registry = load_registry()
    stages = {"bud": 1, "branch": 2, "planted": 3, "rooted": 4}
    max_level = stages.get(stage, 1)
    return [
        tool for tool in registry.values()
        if stages.get(tool.stage, 1) <= max_level
    ]


def get_tool(name: str, stage: str = "bud") -> ToolDef | None:
    """Get a tool by name if available at the given stage."""
    registry = load_registry()
    tool = registry.get(name)
    if not tool:
        return None
    stages = {"bud": 1, "branch": 2, "planted": 3, "rooted": 4}
    if stages.get(tool.stage, 1) > stages.get(stage, 1):
        return None
    return tool