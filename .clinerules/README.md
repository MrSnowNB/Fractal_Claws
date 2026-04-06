---
title: ClawBot Rules Manifest
version: "1.0"
last_updated: "2026-04-01"
---

# ClawBot .clinerules Manifest

| File | Scope | Purpose |
|------|-------|---------|
| `00-policy.md` | Global | Master policy: core mandates, lifecycle, validation gates, failure procedure |
| `01-file-format.md` | Global | All output files must be Markdown+frontmatter or pure YAML |
| `02-lifecycle.md` | Global | Phase-by-phase rules for Plan→Build→Validate→Review→Release |
| `03-failure-handling.md` | Global | 5-step ordered procedure on any failure or uncertainty |
| `04-qwen-coder.md` | Workspace | Orchestrator-specific rules for Qwen3-Coder-Next thinking budget and tool discipline |

## Living Documents (project root)

| File | Purpose |
|------|---------|
| `TROUBLESHOOTING.md` | Append-only failure log with seeded entries |
| `REPLICATION-NOTES.md` | Environment setup, hardware notes, pitfalls, deltas |
| `ISSUE.md` | Open issue tracker — agents open entries on halt |
| `SPEC.md` | _(created per task)_ Task specification |
| `PLAN.md` | _(created per task)_ Agent plan awaiting human approval |
| `CHECKPOINT.md` | _(created at 60% context)_ Mid-task state snapshot |
