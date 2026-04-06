"""
First Principles Solver Unit Tests

This module contains unit tests for the FirstPrinciplesSolver class.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.first_principles_solver import FirstPrinciplesSolver, Component


class TestFirstPrinciplesSolverInit:
    """Test suite: FirstPrinciplesSolver initialization."""

    def test_solver_init(self):
        """FirstPrinciplesSolver initializes correctly."""
        solver = FirstPrinciplesSolver()
        assert solver is not None
        assert len(solver.components) == 0


class TestComponentCreation:
    """Test suite: Component creation and management."""

    def test_component_creation(self):
        """Component can be created."""
        solver = FirstPrinciplesSolver()
        component = solver.create_component(
            name="analyze_requirements",
            description="Analyze project requirements",
            effort=3
        )
        assert isinstance(component, Component)
        assert component.name == "analyze_requirements"
        assert component.effort == 3
        assert component.status == "pending"

    def test_component_from_dict(self):
        """Component can be created from dictionary."""
        data = {
            "name": "design_database",
            "description": "Design database schema",
            "effort": 5,
            "dependencies": ["analyze_requirements"]
        }
        component = Component.from_dict(data)
        assert component.name == "design_database"
        assert component.effort == 5


class TestTaskDecomposition:
    """Test suite: Task decomposition."""

    def test_first_principles_breakdown(self):
        """First principles breakdown returns components."""
        solver = FirstPrinciplesSolver()
        task = "Build a web application"
        components = solver._first_principles_breakdown(task)
        assert isinstance(components, list)
        assert len(components) >= 2
        assert components[0].name != ""

    def test_recursive_decomposition(self):
        """Recursive decomposition returns steps."""
        solver = FirstPrinciplesSolver()
        task = "Implement user authentication"
        subtasks = solver._recursive_decomposition(task)
        assert isinstance(subtasks, list)
        assert len(subtasks) >= 1


class TestSolverStats:
    """Test suite: Solver statistics."""

    def test_get_stats(self):
        """Stats return correct counts."""
        solver = FirstPrinciplesSolver()
        solver.create_component(name="task1", effort=3)
        solver.create_component(name="task2", effort=5)
        solver.create_component(name="task3", effort=2)
        
        stats = solver.get_stats()
        assert stats["total_components"] == 3
        assert stats["pending_components"] == 3
        assert stats["total_effort"] == 10