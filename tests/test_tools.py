# tests/test_tools.py — T06
# Unit tests for tools/registry.py

import pytest
from pathlib import Path


def test_registry_loads():
    """Test that registry loads toolbox.yaml correctly."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.registry import load_registry
    
    registry = load_registry()
    assert "read_file" in registry
    assert "write_file" in registry
    assert "exec_python" in registry
    assert "shell" in registry


def test_tool_definition_structure():
    """Test that tool definitions have required fields."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.registry import load_registry, ToolDef
    
    registry = load_registry()
    for name, tool in registry.items():
        assert isinstance(tool, ToolDef)
        assert tool.name == name
        assert isinstance(tool.path, str)
        assert tool.path.endswith(".py")
        assert tool.stage in ("bud", "branch", "planted", "rooted")
        assert isinstance(tool.description, str)
        assert tool.risk in ("low", "medium", "high")


def test_stage_filtering_bud():
    """Test that only bud-stage tools are returned for bud."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.registry import list_tools
    
    tools = list_tools(stage="bud")
    stages = {t.stage for t in tools}
    assert stages == {"bud"}


def test_stage_filtering_branch():
    """Test that bud+branch tools are returned for branch."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.registry import list_tools
    
    tools = list_tools(stage="branch")
    stages = {t.stage for t in tools}
    assert stages <= {"bud", "branch"}


def test_get_tool_available():
    """Test getting an available tool."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.registry import get_tool
    
    tool = get_tool("read_file", stage="bud")
    assert tool is not None
    assert tool.name == "read_file"


def test_get_tool_not_available():
    """Test getting a tool not available at current stage."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.registry import get_tool
    
    # graphify is planted+ only
    tool = get_tool("graphify", stage="bud")
    assert tool is None


def test_get_tool_not_found():
    """Test getting a non-existent tool."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.registry import get_tool
    
    tool = get_tool("nonexistent_tool_xyz", stage="bud")
    assert tool is None