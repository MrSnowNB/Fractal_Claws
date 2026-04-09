#!/usr/bin/env python3
"""
sequence_gate.py — Enforce journal + commit after every completed sequence

Problem: Luffy completes work but fails to journal and commit.
         His only commit yesterday was "ISSUE: no commit from Luffy."
Solution: Hard gate that blocks the next sequence until the previous one
         is properly journaled and committed.

Usage (wired into runner.py drain loop):
    gate = SequenceGate()
    ok, reason = gate.sequence_start("STEP-10-A")
    if not ok:
        print(f"BLOCKED: {reason}")
        gate.sequence_checkpoint(prev_step, files, summary)
    # ... do work ...
    gate.sequence_checkpoint("STEP-10-A", files_changed, summary)
    gate.sequence_complete("STEP-10-A")
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SequenceGate:
    """Ensures every completed sequence has a journal entry and git commit.

    Flow:
        1. sequence_start(step_id) — marks sequence as in_progress
        2. ... Luffy does work ...
        3. sequence_checkpoint(step_id) — verifies work, writes journal, commits
        4. sequence_complete(step_id) — unlocks next sequence

    If Luffy tries to start a new sequence without completing the gate,
    the gate blocks and forces the commit.
    """

    def __init__(
        self,
        journal_path: str = "logs/luffy-journal.jsonl",
        agent_id: str = "luffy-v1",
        enforce_journal: bool = True,
        enforce_commit: bool = True,
    ):
        self.journal_path = Path(journal_path)
        self.agent_id = agent_id
        self.enforce_journal = enforce_journal
        self.enforce_commit = enforce_commit
        self._current_step: Optional[str] = None
        self._pending_commit: bool = False
        self._completed_steps: list[str] = []

    def sequence_start(self, step_id: str) -> tuple[bool, str]:
        """Begin a new sequence. Returns (allowed, reason).

        If previous sequence has uncommitted work, returns (False, reason).
        """
        if self._pending_commit and self.enforce_commit:
            return (
                False,
                f"BLOCKED: Previous step {self._current_step} has uncommitted work. "
                f"Run sequence_checkpoint('{self._current_step}') first.",
            )
        self._current_step = step_id
        logger.info("[gate] Sequence %s started", step_id)
        return (True, f"Sequence {step_id} started")

    def sequence_checkpoint(
        self,
        step_id: str,
        files_changed: list[str],
        summary: str,
    ) -> dict:
        """Write journal entry and create git commit for completed work.

        Returns dict with journal_ok, commit_ok, and details.
        """
        result = {
            "step": step_id,
            "journal_ok": False,
            "commit_ok": False,
            "files": files_changed,
        }

        # 1. Write journal entry
        if self.enforce_journal:
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "step": step_id,
                "action": summary,
                "status": "done",
                "files": files_changed,
                "agent_id": self.agent_id,
                "anchor": {
                    "system_state": summary,
                    "open_invariants": [],
                    "next_entry_point": f"Next step after {step_id}",
                },
            }

            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            result["journal_ok"] = True
            logger.info("[gate] Journal entry written for %s", step_id)

        # 2. Git add + commit
        if self.enforce_commit:
            try:
                all_files = files_changed + [str(self.journal_path)]
                for fpath in all_files:
                    subprocess.run(
                        ["git", "add", fpath],
                        capture_output=True,
                        check=False,
                    )

                commit_msg = f"{step_id}: {summary}"
                proc = subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    capture_output=True,
                    text=True,
                )
                result["commit_ok"] = proc.returncode == 0
                result["commit_msg"] = commit_msg
                if proc.returncode != 0:
                    result["commit_error"] = proc.stderr.strip()
                    logger.warning(
                        "[gate] Commit failed for %s: %s",
                        step_id,
                        proc.stderr.strip(),
                    )
                else:
                    logger.info("[gate] Committed: %s", commit_msg)
            except Exception as e:
                result["commit_error"] = str(e)
                logger.error("[gate] Commit exception for %s: %s", step_id, e)

        self._pending_commit = not result.get("commit_ok", False)
        return result

    def sequence_complete(self, step_id: str) -> None:
        """Mark sequence as fully complete. Unlocks next sequence."""
        self._pending_commit = False
        self._completed_steps.append(step_id)
        self._current_step = None
        logger.info("[gate] Sequence %s complete", step_id)

    def has_pending_work(self) -> tuple[bool, Optional[str]]:
        """Check if there's uncommitted work from a previous sequence."""
        return (self._pending_commit, self._current_step)

    @property
    def completed(self) -> list[str]:
        """List of completed step IDs this session."""
        return list(self._completed_steps)
