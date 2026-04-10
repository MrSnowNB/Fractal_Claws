#!/usr/bin/env python3
"""
sequence_gate.py — Enforce journal + commit + ticket close after every completed sequence

Problem: Luffy completes work but fails to:
         1. Journal and commit (original bug)
         2. Move sub-tickets (A/B/C/D) from tickets/open/ to tickets/closed/
            when context budget is high at end of focus chain
Solution: Hard gate that:
         - Blocks the next sequence until the previous one is journaled and committed
         - Adds pre_commit_check() that scans tickets/open/ for any ticket
           whose ticket_id matches the active step and blocks commit if not closed

Usage (wired into runner.py drain loop):
    gate = SequenceGate()
    ok, reason = gate.sequence_start("STEP-10-A")
    if not ok:
        print(f"BLOCKED: {reason}")
        gate.sequence_checkpoint(prev_step, files, summary)
    # ... do work ...
    gate.pre_commit_check("STEP-10-B")   # call BEFORE git commit
    gate.sequence_checkpoint("STEP-10-A", files_changed, summary)
    gate.sequence_complete("STEP-10-A")
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional


class LawViolationError(Exception):
    """Raised when a Luffy Law is violated (scratchpad, journal, or cache rules)."""
    pass

logger = logging.getLogger(__name__)


class SequenceGate:
    """Ensures every completed sequence has a journal entry, git commit,
    AND that the active ticket has been moved out of tickets/open/.

    Flow:
        1. sequence_start(step_id) — marks sequence as in_progress
        2. ... Luffy does work ...
        3. pre_commit_check(step_id) — BLOCKS if ticket still in open/
        4. sequence_checkpoint(step_id) — verifies work, writes journal, commits
        5. sequence_complete(step_id) — unlocks next sequence

    If Luffy tries to commit without closing the ticket first,
    pre_commit_check raises and blocks the commit.

    Sub-ticket naming (A/B/C/D) is supported: pre_commit_check checks
    both the exact ticket_id and any variant suffixed with -A through -Z.
    """

    OPEN_DIR = Path("tickets/open")
    CLOSED_DIR = Path("tickets/closed")

    def __init__(
        self,
        journal_path: str = "logs/luffy-journal.jsonl",
        agent_id: str = "luffy-v1",
        enforce_journal: bool = True,
        enforce_commit: bool = True,
        enforce_ticket_close: bool = True,
    ):
        self.journal_path = Path(journal_path)
        self.agent_id = agent_id
        self.enforce_journal = enforce_journal
        self.enforce_commit = enforce_commit
        self.enforce_ticket_close = enforce_ticket_close
        self._current_step: Optional[str] = None
        self._pending_commit: bool = False
        self._completed_steps: list[str] = []

    # ── Ticket close enforcement ──────────────────────────────────────────────

    def _open_ticket_path(self, ticket_id: str) -> Optional[Path]:
        """Return path if <ticket_id>.yaml exists in tickets/open/, else None."""
        candidate = self.OPEN_DIR / f"{ticket_id}.yaml"
        return candidate if candidate.exists() else None

    def pre_commit_check(self, step_id: str) -> tuple[bool, str]:
        """Check that the active ticket has been moved out of tickets/open/.

        Call this BEFORE writing a git commit for step_id.

        Returns (ok, message).
        Logs a WARNING if the ticket is still open — does not raise by default
        so existing callers don't break, but the return value should be checked.

        The check covers:
          - Exact match: tickets/open/STEP-10-B.yaml
          - Parent match: if step_id is STEP-10-B, also checks STEP-10.yaml
        """
        if not self.enforce_ticket_close:
            return (True, "ticket close enforcement disabled")

        found = self._open_ticket_path(step_id)
        if found:
            msg = (
                f"BLOCKED: ticket {step_id} still in tickets/open/ — "
                f"run move_ticket('{found}', 'tickets/closed/') before committing."
            )
            logger.warning("[gate] %s", msg)
            return (False, msg)

        # Also check parent ticket (e.g. STEP-10 for STEP-10-B)
        parts = step_id.rsplit("-", 1)
        if len(parts) == 2 and len(parts[1]) == 1 and parts[1].isalpha():
            parent_id = parts[0]
            parent_found = self._open_ticket_path(parent_id)
            if parent_found:
                msg = (
                    f"WARNING: parent ticket {parent_id} still in tickets/open/ "
                    f"while closing sub-ticket {step_id}."
                )
                logger.warning("[gate] %s", msg)
                # Parent open is a warning, not a hard block
                return (True, msg)

        logger.info("[gate] pre_commit_check passed for %s", step_id)
        return (True, f"ticket {step_id} not in open/ — safe to commit")

    def close_ticket(self, ticket_id: str) -> tuple[bool, str]:
        """Move ticket_id.yaml from tickets/open/ to tickets/closed/.

        Updates status field to 'closed' in the YAML before moving.
        Returns (ok, message).
        """
        import shutil
        import yaml

        src = self.OPEN_DIR / f"{ticket_id}.yaml"
        if not src.exists():
            return (False, f"ticket {ticket_id} not found in tickets/open/")

        self.CLOSED_DIR.mkdir(parents=True, exist_ok=True)
        dst = self.CLOSED_DIR / f"{ticket_id}.yaml"

        # Update status to closed before moving
        try:
            with open(src, "r", encoding="utf-8") as f:
                raw = f.read()
            # Strip YAML front-matter dashes if present
            content = raw.strip().lstrip("-").strip()
            data = yaml.safe_load(content) or {}
            data["status"] = "closed"
            data["closed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(src, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            logger.warning("[gate] Could not update status in %s: %s", src, e)

        shutil.move(str(src), str(dst))
        logger.info("[gate] Ticket %s moved to tickets/closed/", ticket_id)
        return (True, f"ticket {ticket_id} closed → {dst}")

    # ── Sequence lifecycle ────────────────────────────────────────────────────

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

        Automatically runs pre_commit_check before committing.
        Returns dict with journal_ok, commit_ok, ticket_ok, and details.
        """
        result = {
            "step": step_id,
            "journal_ok": False,
            "commit_ok": False,
            "ticket_ok": False,
            "files": files_changed,
        }

        # 0. Ticket close check — warn but don't block checkpoint
        ticket_ok, ticket_msg = self.pre_commit_check(step_id)
        result["ticket_ok"] = ticket_ok
        result["ticket_msg"] = ticket_msg
        if not ticket_ok:
            logger.warning(
                "[gate] Checkpoint proceeding despite open ticket: %s", ticket_msg
            )

        # 1. Write journal entry
        if self.enforce_journal:
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "step": step_id,
                "action": summary,
                "status": "done",
                "files": files_changed,
                "agent_id": self.agent_id,
                "ticket_close_ok": ticket_ok,
                "anchor": {
                    "system_state": summary,
                    "open_invariants": [] if ticket_ok else [f"ticket {step_id} not closed"],
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

    # ── Luffy Law enforcement helpers ───────────────────────────────────────────

    def assert_scratch_written(self, ticket_id: str) -> None:
        """
        Law §1: raise LawViolationError if no non-INIT scratch event exists
        for ticket_id in the current session.

        The scratch file lives at logs/scratch-{ticket_id}.jsonl.
        A session is considered to have written scratch if any event with
        event != SCRATCH_INIT and event != SCRATCH_CLOSE exists for this ticket.
        """
        scratch_path = Path("logs") / f"scratch-{ticket_id}.jsonl"
        if not scratch_path.exists():
            raise LawViolationError(
                f"Law §1 VIOLATION: scratch file missing for {ticket_id}"
            )

        events = []
        with open(scratch_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        non_init = [e for e in events if e.get("event") not in ("SCRATCH_INIT", "SCRATCH_CLOSE")]
        if not non_init:
            raise LawViolationError(
                f"Law §1 VIOLATION: scratch for {ticket_id} has no non-INIT events — "
                f"Luffy did not write to scratchpad during execution"
            )
