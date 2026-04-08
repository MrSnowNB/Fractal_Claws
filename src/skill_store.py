"""
Skill Store — Skill-aware decomposition support.

Provides functions to load, write, and match skill files for
cached toolpath execution (Step 6).
"""

import os
import re
import yaml
from typing import Optional


class SkillLoadError(RuntimeError):
    """Raised when a skill file cannot be loaded."""
    pass


class SkillWriteError(RuntimeError):
    """Raised when a skill cannot be written."""
    pass


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def load_skill(goal_class: str, skills_dir: str = "skills") -> Optional[dict]:
    """
    Load a skill file by goal_class.

    Args:
        goal_class: The skill filename stem (e.g., "fibonacci_generator")
        skills_dir: Path to skills directory (default: "skills")

    Returns:
        Parsed YAML dict, or None if file not found.

    Raises:
        SkillLoadError: If YAML is malformed.
    """
    if not os.path.exists(skills_dir):
        return None

    skill_path = os.path.join(skills_dir, f"{goal_class}.yaml")
    if os.path.exists(skill_path):
        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise SkillLoadError(f"Malformed YAML in {skill_path}: {e}")

    # Fuzzy match: scan skills/ for any filename with Levenshtein distance <= 2
    try:
        files = [f for f in os.listdir(skills_dir) if f.endswith(".yaml")]
    except OSError:
        return None

    for filename in files:
        stem = filename[:-5]  # remove .yaml
        if _levenshtein_distance(stem, goal_class) <= 2:
            try:
                with open(os.path.join(skills_dir, filename), "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise SkillLoadError(f"Malformed YAML in {filename}: {e}")

    return None


def write_skill(goal_class: str, skill: dict, skills_dir: str = "skills") -> None:
    """
    Write a skill file.

    Args:
        goal_class: The skill filename stem
        skill: Skill dict with required keys: goal_class, tool_sequence, elapsed_s
        skills_dir: Path to skills directory (default: "skills")

    Raises:
        SkillWriteError: If required keys are missing.
    """
    required_keys = {"goal_class", "tool_sequence", "elapsed_s"}
    missing = required_keys - set(skill.keys())
    if missing:
        raise SkillWriteError(f"Skill dict missing required keys: {missing}")

    os.makedirs(skills_dir, exist_ok=True)
    skill_path = os.path.join(skills_dir, f"{goal_class}.yaml")

    with open(skill_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(skill, f, default_flow_style=False, sort_keys=False)


def match_goal_class(ticket_task: str, skills_dir: str = "skills") -> Optional[str]:
    """
    Extract goal_class from ticket task and match against skill files.

    Args:
        ticket_task: The task string from a ticket
        skills_dir: Path to skills directory (default: "skills")

    Returns:
        Best matching skill filename stem, or None if no match.
    """
    if not ticket_task:
        return None

    if not os.path.exists(skills_dir):
        return None

    try:
        files = [f for f in os.listdir(skills_dir) if f.endswith(".yaml")]
    except OSError:
        return None

    if not files:
        return None

    # Tokenize task to extract goal_class-like string
    # Extract capitalized words and combine them (e.g., "Fibonacci Generator")
    words = re.findall(r"[A-Z][a-z]+", ticket_task)
    candidate = "_".join(words).lower() if words else ticket_task.lower()

    # Exact match first
    for filename in files:
        stem = filename[:-5]
        if stem == candidate:
            return stem

    # Fuzzy match (distance <= 2)
    best_match = None
    best_distance = 3  # Start above threshold

    for filename in files:
        stem = filename[:-5]
        dist = _levenshtein_distance(stem, candidate)
        if dist <= 2 and dist < best_distance:
            best_distance = dist
            best_match = stem

    return best_match