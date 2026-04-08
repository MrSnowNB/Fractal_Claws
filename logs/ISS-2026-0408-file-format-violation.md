---
title: "ISS-2026-0408: File format violation in test_delegate_task.py"
version: "0.7.0"
last_updated: "2026-04-08"
---

## Issue

**Status:** open  
**Blocked on:** human  
**Phase:** Build → Validate  
**Gate:** file format validation

## Symptom

`tests/integration/test_delegate_task.py` was written with YAML frontmatter but is a Python file.

**Violation:** Per `.clinerules/01-file-format.md`, files must be:
- Markdown with YAML frontmatter (`.md`)
- Pure YAML (`.yaml`/`.yml`)

Python files (`.py`) are not in the allowed formats.

## Context

- Task: STEP-07-E — Write `tests/integration/test_delegate_task.py`
- Agent action: `write_to_file` created file with YAML frontmatter header
- Pylance errors detected: 3 expression errors at start of file

## Probable Cause

Agent assumed all files could accept YAML frontmatter. Did not verify file extension compatibility with format policy.

## Quick Fix

Remove YAML frontmatter from `tests/integration/test_delegate_task.py`, leaving pure Python code.

## Permanent Fix

Option A: Update `.clinerules/01-file-format.md` to permit `.py` files without frontmatter  
Option B: Agent must check extension before writing and use appropriate format

## Prevention

- Add format validation gate before write
- Log file extension in tool call metadata
- Reject write_to_file if extension doesn't match allowed formats

## Human Action Required

Approve one of:
1. Remove frontmatter and proceed with STEP-07-E
2. Update file format policy to include `.py` files

---

## References

- `.clinerules/01-file-format.md`
- `.clinerules/03-failure-handling.md`
- `logs/luffy-journal.jsonl` (append only valid JSON)