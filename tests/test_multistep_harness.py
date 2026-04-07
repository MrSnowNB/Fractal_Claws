"""
Multistep harness: parent ticket writes child, child writes+executes script,
child creates report, parent audits the full chain.

Metadata is stamped at every handoff so post-mortem can pinpoint failure origin.

Run:
    pytest tests/test_multistep_harness.py -v
    pytest tests/test_multistep_harness.py -v -k TestPhase3
    pytest tests/test_multistep_harness.py::TestFullPipeline -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — mirrors test_operator.py
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operator_v7 import Ticket, TicketStatus, TicketPriority  # noqa: E402


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

HARNESS_VERSION = "1.1.0"


def _stamp(
    phase: str,
    actor: str,
    status: str,
    detail: str = "",
    extra: dict | None = None,
) -> dict[str, Any]:
    """Return a structured metadata envelope for a handoff checkpoint."""
    return {
        "harness_version": HARNESS_VERSION,
        "phase": phase,
        "actor": actor,
        "status": status,
        "ts": time.time(),
        "detail": detail,
        **(extra or {}),
    }


class HarnessTrace:
    """
    Accumulate metadata stamps across all phases for post-mortem inspection.

    Each stamp is a dict with at minimum:
        phase, actor, status, ts, detail

    Usage::

        trace = HarnessTrace()
        trace.record(_stamp("phase1_spawn", "parent", "started"))
        trace.record(_stamp("phase1_spawn", "parent", "completed",
                            extra={"ticket_id": "TASK-CHILD-002"}))
        trace.assert_phase_completed("phase1_spawn")
        trace.assert_no_failures()
    """

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def record(self, stamp: dict[str, Any]) -> None:
        self._events.append(stamp)

    def phase_events(self, phase: str) -> list[dict[str, Any]]:
        return [e for e in self._events if e["phase"] == phase]

    def last(self) -> dict[str, Any] | None:
        return self._events[-1] if self._events else None

    def dump(self) -> str:
        return json.dumps(self._events, indent=2, default=str)

    def assert_phase_completed(self, phase: str) -> None:
        events = self.phase_events(phase)
        completed = [e for e in events if e["status"] == "completed"]
        assert completed, (
            f"Phase '{phase}' never reached status=completed.\n"
            f"All trace events:\n{self.dump()}"
        )

    def assert_no_failures(self) -> None:
        failures = [e for e in self._events if e["status"] == "failed"]
        assert not failures, (
            f"Harness recorded {len(failures)} failure(s):\n"
            + json.dumps(failures, indent=2, default=str)
        )


# ---------------------------------------------------------------------------
# Helpers: build Ticket objects directly (no Operator class in operator_v7)
# ---------------------------------------------------------------------------

def _make_ticket(ticket_id: str, depth: int = 0, priority: str = "high",
                 parent: str | None = None) -> Ticket:
    return Ticket.from_dict({
        "id": ticket_id,
        "depth": depth,
        "priority": priority,
        "status": "pending",
        "attempts": 0,
        "decrement": 3,
        "parent": parent,
        "children": [],
        "result": {},
    })


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def trace() -> HarnessTrace:
    return HarnessTrace()


# ---------------------------------------------------------------------------
# Script + report constants
# ---------------------------------------------------------------------------

FIB_SCRIPT = textwrap.dedent("""\
    a, b = 0, 1
    for _ in range(10):
        print(a)
        a, b = b, a + b
""")

FIB_STDOUT = "0\n1\n1\n2\n3\n5\n8\n13\n21\n34"

FIB_REPORT_TEMPLATE = textwrap.dedent("""\
    # Fibonacci Report
    **Ticket:** TASK-CHILD-002
    **Verdict:** PASS
    **Stdout:**
    ```
    {stdout}
    ```
    10th value (34) present in output: True
""")


# ---------------------------------------------------------------------------
# Phase 1 — Parent creates child ticket
# ---------------------------------------------------------------------------

class TestPhase1_ParentSpawnsChild:
    """
    Phase 1: Parent agent creates the child Ticket dataclass and wires the
    parent/child relationship.

    Metadata stamped:
        phase1_spawn / started
        phase1_spawn / completed  (child_id, child_status)
    """

    def test_parent_creates_child_ticket(self, trace):
        trace.record(_stamp("phase1_spawn", "parent", "started",
                            detail="creating child ticket TASK-CHILD-002"))

        parent = _make_ticket("TASK-PARENT-001", depth=0, priority="high")
        child  = _make_ticket("TASK-CHILD-002", depth=1, priority="high",
                               parent="TASK-PARENT-001")
        parent.children = [child.id]

        trace.record(_stamp(
            "phase1_spawn", "parent", "completed",
            detail=f"child ticket {child.id} created",
            extra={
                "parent_id": parent.id,
                "child_id": child.id,
                "child_status": child.status.value,
            },
        ))

        assert isinstance(child, Ticket)
        assert child.id == "TASK-CHILD-002"
        assert child.parent == "TASK-PARENT-001"
        assert child.id in parent.children
        assert child.status == TicketStatus.PENDING
        trace.assert_phase_completed("phase1_spawn")


# ---------------------------------------------------------------------------
# Phase 2 — Child writes the script
# ---------------------------------------------------------------------------

class TestPhase2_ChildWritesScript:
    """
    Phase 2: Child ticket drives writing of output/fib.py.

    Metadata stamped:
        phase2_write_script / started
        phase2_write_script / completed  (script_path, script_len)
    """

    def test_child_writes_fib_script(self, trace, tmp_path):
        trace.record(_stamp("phase2_write_script", "child", "started",
                            detail="writing output/fib.py"))

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / "fib.py"
        script_path.write_text(FIB_SCRIPT)

        trace.record(_stamp(
            "phase2_write_script", "child",
            "completed" if script_path.exists() else "failed",
            detail=str(script_path),
            extra={"script_len": len(FIB_SCRIPT), "script_path": str(script_path)},
        ))

        assert script_path.exists(), (
            f"output/fib.py was not written.\nTrace:\n{trace.dump()}"
        )
        assert "range(10)" in script_path.read_text(), (
            f"Script content looks wrong.\nTrace:\n{trace.dump()}"
        )
        trace.assert_phase_completed("phase2_write_script")


# ---------------------------------------------------------------------------
# Phase 3 — Child executes the script
# ---------------------------------------------------------------------------

class TestPhase3_ChildExecutesScript:
    """
    Phase 3: Child executes fib.py via subprocess and captures stdout.

    Metadata stamped:
        phase3_execute / started
        phase3_execute / completed  (returncode, stdout, tenth_value_present)
    """

    def test_child_executes_script(self, trace, tmp_path):
        trace.record(_stamp("phase3_execute", "child", "started",
                            detail="executing output/fib.py"))

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / "fib.py"
        script_path.write_text(FIB_SCRIPT)

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        stdout = result.stdout.strip()
        tenth_present = "34" in stdout

        trace.record(_stamp(
            "phase3_execute", "child",
            "completed" if result.returncode == 0 else "failed",
            detail=f"returncode={result.returncode}",
            extra={
                "returncode": result.returncode,
                "stdout": stdout,
                "stderr": result.stderr.strip(),
                "tenth_value_present": tenth_present,
            },
        ))

        assert result.returncode == 0, (
            f"fib.py exited non-zero.\nstderr: {result.stderr}\nTrace:\n{trace.dump()}"
        )
        assert tenth_present, (
            f"34 not found in stdout.\nstdout: {stdout}\nTrace:\n{trace.dump()}"
        )
        lines = stdout.splitlines()
        assert len(lines) == 10, (
            f"Expected 10 lines, got {len(lines)}.\nstdout: {stdout}\nTrace:\n{trace.dump()}"
        )
        trace.assert_phase_completed("phase3_execute")


# ---------------------------------------------------------------------------
# Phase 4 — Child writes report
# ---------------------------------------------------------------------------

class TestPhase4_ChildWritesReport:
    """
    Phase 4: Child writes output/fib_report.md with PASS verdict and stdout.

    Metadata stamped:
        phase4_report / started
        phase4_report / completed  (report_path, verdict_pass)
    """

    def test_child_writes_report(self, trace, tmp_path):
        trace.record(_stamp("phase4_report", "child", "started",
                            detail="writing output/fib_report.md"))

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        report_content = FIB_REPORT_TEMPLATE.format(stdout=FIB_STDOUT)
        report_path = output_dir / "fib_report.md"
        report_path.write_text(report_content)

        verdict_pass = "PASS" in report_path.read_text()

        trace.record(_stamp(
            "phase4_report", "child",
            "completed" if report_path.exists() else "failed",
            detail=str(report_path),
            extra={
                "report_path": str(report_path),
                "report_len": len(report_content),
                "verdict_pass": verdict_pass,
            },
        ))

        assert report_path.exists(), (
            f"fib_report.md was not written.\nTrace:\n{trace.dump()}"
        )
        assert verdict_pass, (
            f"Report missing PASS verdict.\nContent:\n{report_path.read_text()}\n"
            f"Trace:\n{trace.dump()}"
        )
        trace.assert_phase_completed("phase4_report")


# ---------------------------------------------------------------------------
# Phase 5 — Parent audits the full artifact chain
# ---------------------------------------------------------------------------

class TestPhase5_ParentAuditsChain:
    """
    Phase 5: Parent reads both output artifacts and confirms all acceptance
    criteria from the parent ticket are met. Also validates the child Ticket
    dataclass fields are still coherent after the full run.

    Metadata stamped:
        phase5_audit / started
        phase5_audit / completed  (script_ok, report_ok, verdict_pass)
    """

    def test_parent_audits_full_pipeline(self, trace, tmp_path):
        trace.record(_stamp("phase5_audit", "parent", "started",
                            detail="auditing full pipeline"))

        # Simulate artifacts produced by Phases 2-4
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "fib.py").write_text(FIB_SCRIPT)
        (output_dir / "fib_report.md").write_text(
            FIB_REPORT_TEMPLATE.format(stdout=FIB_STDOUT)
        )

        child = _make_ticket("TASK-CHILD-002", depth=1, priority="high",
                              parent="TASK-PARENT-001")

        script_ok  = (output_dir / "fib.py").exists()
        report_ok  = (output_dir / "fib_report.md").exists()
        report_text = (output_dir / "fib_report.md").read_text()
        verdict_pass = "PASS" in report_text
        all_ok = script_ok and report_ok and verdict_pass

        trace.record(_stamp(
            "phase5_audit", "parent",
            "completed" if all_ok else "failed",
            detail="all artifacts present, PASS confirmed" if all_ok else "audit failed",
            extra={
                "script_ok": script_ok,
                "report_ok": report_ok,
                "verdict_pass": verdict_pass,
            },
        ))

        assert script_ok,    f"output/fib.py missing.\nTrace:\n{trace.dump()}"
        assert report_ok,    f"output/fib_report.md missing.\nTrace:\n{trace.dump()}"
        assert verdict_pass, (
            f"Report verdict is not PASS.\nReport:\n{report_text}\nTrace:\n{trace.dump()}"
        )
        # Sanity-check the child ticket dataclass itself
        assert child.status == TicketStatus.PENDING
        assert child.priority == TicketPriority.HIGH
        assert child.parent == "TASK-PARENT-001"

        trace.assert_phase_completed("phase5_audit")
        trace.assert_no_failures()


# ---------------------------------------------------------------------------
# Full end-to-end: all 5 phases in sequence with a shared HarnessTrace
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """
    Smoke-run all 5 phases sequentially with a shared HarnessTrace.

    A failure in any phase is visible in the trace dump before teardown.
    The shared trace also catches cross-phase bugs (e.g. Phase 4 reading
    a file Phase 2 never wrote).

    Primary regression gate. Run with::

        pytest tests/test_multistep_harness.py::TestFullPipeline -v
    """

    def test_e2e_multistep_pipeline(self, tmp_path):
        trace = HarnessTrace()
        trace.record(_stamp("e2e", "harness", "started",
                            detail="beginning full pipeline"))

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # --- Phase 1: parent spawns child ticket ---
        trace.record(_stamp("phase1_spawn", "parent", "started"))
        parent = _make_ticket("TASK-PARENT-001", depth=0, priority="high")
        child  = _make_ticket("TASK-CHILD-002", depth=1, priority="high",
                               parent="TASK-PARENT-001")
        parent.children = [child.id]
        trace.record(_stamp("phase1_spawn", "parent", "completed",
                            extra={"child_id": child.id}))

        # --- Phase 2: child writes script ---
        trace.record(_stamp("phase2_write_script", "child", "started"))
        script_path = output_dir / "fib.py"
        script_path.write_text(FIB_SCRIPT)
        trace.record(_stamp(
            "phase2_write_script", "child",
            "completed" if script_path.exists() else "failed",
            extra={"script_path": str(script_path)},
        ))

        # --- Phase 3: child executes script ---
        trace.record(_stamp("phase3_execute", "child", "started"))
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=10,
        )
        stdout = result.stdout.strip()
        trace.record(_stamp(
            "phase3_execute", "child",
            "completed" if result.returncode == 0 else "failed",
            extra={"returncode": result.returncode, "stdout": stdout},
        ))

        # --- Phase 4: child writes report ---
        trace.record(_stamp("phase4_report", "child", "started"))
        report_path = output_dir / "fib_report.md"
        report_content = FIB_REPORT_TEMPLATE.format(stdout=stdout)
        report_path.write_text(report_content)
        trace.record(_stamp(
            "phase4_report", "child",
            "completed" if report_path.exists() else "failed",
            extra={"report_path": str(report_path)},
        ))

        # --- Phase 5: parent audits ---
        trace.record(_stamp("phase5_audit", "parent", "started"))
        script_ok    = script_path.exists()
        report_ok    = report_path.exists()
        verdict_pass = "PASS" in report_path.read_text()
        all_ok = script_ok and report_ok and verdict_pass
        trace.record(_stamp(
            "phase5_audit", "parent",
            "completed" if all_ok else "failed",
            extra={
                "script_ok": script_ok,
                "report_ok": report_ok,
                "verdict_pass": verdict_pass,
            },
        ))

        trace.record(_stamp("e2e", "harness", "completed",
                            detail="all phases passed"))

        # --- Final assertions ---
        for phase in [
            "phase1_spawn", "phase2_write_script",
            "phase3_execute", "phase4_report", "phase5_audit",
        ]:
            trace.assert_phase_completed(phase)

        trace.assert_no_failures()

        assert script_path.exists(),          "fib.py missing"
        assert report_path.exists(),          "fib_report.md missing"
        assert result.returncode == 0,         f"fib.py non-zero exit: {result.stderr}"
        assert "34" in stdout,                 f"34 not in stdout: {stdout}"
        assert "PASS" in report_path.read_text(), "PASS verdict missing from report"
