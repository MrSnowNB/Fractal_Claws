---
name: validate-gates
description: >
  Run project validation gates including pytest unit tests, ruff or flake8 lint,
  mypy or pyright type checking, and spec drift check. Use when validating a build,
  running tests, checking gate status, or before any phase transition from Build to Validate.
version: "1.0"
last_updated: "2026-04-01"
---

# validate-gates

## Purpose

Execute all four ClawBot validation gates in sequence. Every gate must be green before
the Build → Validate → Review phase transition is permitted. A single gate failure
triggers the full failure handling procedure defined in `03-failure-handling.md`.

## Instructions

Run gates **in order**. Do not skip ahead. Do not run gates in parallel.
If any gate fails, stop immediately — do not run remaining gates.

### Gate 1 — Unit Tests

```powershell
pytest -q
```

**Pass condition**: Output ends with `X passed` and `0 failed, 0 errors`.
**Capture**: Save full output to `logs/gate-unit-<YYYY-MM-DD>.log`.

If failed:
- Note the test name(s) and error message(s)
- Proceed to Failure Handling below

---

### Gate 2 — Lint

```powershell
ruff check .
```

If `ruff` is not installed, fall back to:

```powershell
flake8 .
```

**Pass condition**: No output (clean exit code 0).
**Capture**: Save full output to `logs/gate-lint-<YYYY-MM-DD>.log`.

If failed:
- Note each file, line number, and rule violation
- Proceed to Failure Handling below

---

### Gate 3 — Type Check

```powershell
mypy .
```

If `mypy` is not installed, fall back to:

```powershell
pyright .
```

**Pass condition**: Output ends with `Success: no issues found` or `0 errors`.
**Capture**: Save full output to `logs/gate-type-<YYYY-MM-DD>.log`.

If failed:
- Note each file and type error
- Proceed to Failure Handling below

---

### Gate 4 — Spec Drift Check

Compare `SPEC.md` against the current state of all files modified during the Build phase.

```powershell
git diff --name-only HEAD
```

For each modified file, verify it was listed in the approved `SPEC.md` scope.
Check that no undocumented files were created or deleted.

**Pass condition**: All modified files are within the spec scope. No undocumented changes.
**Capture**: Save `git diff --stat HEAD` output to `logs/gate-drift-<YYYY-MM-DD>.log`.

If failed:
- List the out-of-scope files
- Proceed to Failure Handling below

---

## Gate Status Report

After all four gates, write a `GATE-REPORT.md` in the project root:

```yaml
---
title: Gate Status Report
date: "<YYYY-MM-DD>"
phase_transition: "Build → Validate"
---
```

| Gate | Command | Status | Log File |
|------|---------|--------|----------|
| unit | `pytest -q` | ✅ PASS / ❌ FAIL | `logs/gate-unit-<date>.log` |
| lint | `ruff check .` | ✅ PASS / ❌ FAIL | `logs/gate-lint-<date>.log` |
| type | `mypy .` | ✅ PASS / ❌ FAIL | `logs/gate-type-<date>.log` |
| docs | spec drift check | ✅ PASS / ❌ FAIL | `logs/gate-drift-<date>.log` |

**Overall**: ALL GREEN — phase transition approved
**or**
**Overall**: BLOCKED — see failure handling

---

## Failure Handling

On any gate failure, execute the procedure from `03-failure-handling.md` in full:

1. Logs are already captured in `logs/` from the gate run above
2. Append a new entry to `TROUBLESHOOTING.md` using the TS-XXX format
3. Append to the Recurring Errors table in `REPLICATION-NOTES.md`
4. Open a new issue in `ISSUE.md` with `status: open` and `blocked_on: human`
5. Report to the human: "Gate <gate-name> failed. Halted on ISS-XXX. See ISSUE.md."
6. **Stop. Do not attempt to fix the failure autonomously.**

---

## Output Format

All output files are Markdown with YAML frontmatter.
Log files in `logs/` are plain text captures of terminal output (no frontmatter required).
`GATE-REPORT.md` uses the template above.
