# KNOWN ISSUE — Context Window Bottleneck

> **AI-FIRST DOC** — Temporary working document. Superseded when Step 9 (GraphRAG
> index) is complete. Delete after `AI-FIRST/STEP-09-GRAPHIFY.md` is merged.

**Status:** OPEN  
**Severity:** High — slows every multi-file reasoning step  
**Opened:** 2026-04-08  
**Owner:** Mark Snow + Luffy  

---

## Symptom

Every time Cline needs to reason across more than 2–3 files, it re-reads
each file in full. A single STEP-06-B session consumed 64K+ tokens re-reading
`runner.py`, `skill_store.py`, `ticket_io.py`, and four spec files — repeatedly.
Even at 64K context, the window fills before the agent finishes reasoning.
Performance degrades non-linearly as file count grows.

**Root cause:** The agent has no persistent navigation layer. Every cold start
is a full re-read. There is no index that says "`execute_ticket()` calls
`call_model()` on line 247" — the agent must discover it by loading the file.

---

## Why SOTA Cloud Models Appear Faster

Cloud models (Gemini 1.5/2.0, Claude 3.x, GPT-4o) are not faster because they
have 1M token windows. They are faster because:

1. They were trained on code navigation patterns — they guess structure without
   reading every line
2. Their KV cache is always warm (server-side persistent cache across calls)
3. They carry implicit graph structure of common OSS repos in weights

A local model starting cold does not have these advantages. The fix is
architectural, not model-size.

---

## Solution Trajectory (3 phases, in order)

### Phase 1 — Immediate (zero code, spec enforcement only)

**Ticket-scoped context discipline.**

Every ticket in `tickets/open/` already has a `context_files` field.
Enforce it strictly: Cline must load ONLY the files listed in `context_files`
before starting work on a ticket. No speculative file reads.

Ticket authors (human or Luffy) must populate `context_files` precisely:
```yaml
context_files:
  - agent/runner.py
  - src/skill_store.py
```

This alone eliminates 60–70% of redundant file loads. Most tickets touch
2–3 files. The current default is to load everything.

**Action required:** Add a lint gate to STEP-XX-A audit tickets:
> `context_files` must be non-empty for any ticket that touches existing code.

---

### Phase 2 — Step 7 (incremental journal as working memory)

**Anchor summarization pattern.**

The `logs/luffy-journal.jsonl` file is already the system's audit trail.
Extend it to carry compressed working memory so the agent can resume
without re-reading spec files.

Each journal entry gains an `anchor` field — a structured summary of the
current system state, written at commit time:

```json
{
  "ts": "2026-04-08T11:00:00",
  "step": "STEP-06-D",
  "action": "skill cache wired into execute_ticket()",
  "status": "done",
  "files": ["agent/runner.py", "src/skill_store.py"],
  "anchor": {
    "runner_state": "execute_ticket() checks skill cache before call_model(). Cache hit skips LLM. write_skill() called on pass.",
    "open_invariants": ["REGISTRY dispatch intact", "typed Ticket access intact", "journal append-only"],
    "next_entry_point": "STEP-07-A: add TicketResult dataclass to src/operator_v7.py"
  }
}
```

On cold start, Cline reads ONLY:
1. `AI-FIRST/CONTEXT.md` (static, rarely changes)
2. The LAST journal entry (single line, anchor field)
3. The current ticket's `context_files`

No spec re-reads. No full file loads until the ticket declares them.

**Implementation:** Add `anchor` field to the journal entry schema in
`AI-FIRST/NEXT-STEPS.md`. Update the Luffy Law commit protocol to require it.

---

### Phase 3 — Step 9 (GraphRAG navigation index)

**Graphify: knowledge graph over the codebase.**

Once the repo exceeds ~30 files with complex cross-file dependencies,
a knowledge graph replaces speculative file reads entirely.

**Graph schema for Fractal Claws:**

```
Nodes:
  FILE       — every .py file in src/, agent/, tools/
  FUNCTION   — every def in those files
  CLASS      — every class
  TICKET     — every YAML in tickets/
  SKILL      — every YAML in skills/
  STEP       — every AI-FIRST/STEP-XX-*.md

Edges:
  CALLS      — function → function (static analysis)
  IMPORTS    — file → file
  MODIFIES   — ticket → file
  DEPENDS_ON — ticket → ticket
  PRODUCES   — ticket → skill
  SPEC_FOR   — step → file
  TESTS      — test_file → file
```

**Agent query before any file load:**
```
Q: "What functions does execute_ticket() call?"
A: [call_model, parse_and_run_tools, _evaluate, append_attempt_log,
    match_goal_class, load_skill, write_skill]
   → Load only those 3 function definitions (~40 lines each)
   → Skip the other 350 lines of runner.py
```

**Ingestion pipeline (Step 9 implementation):**
- `tools/graphify.py` — static AST walker, writes `graph/fractal-claws.json`
- Runs on every commit (pre-commit hook or CI)
- Cline calls `REGISTRY.call("query_graph", {"q": "..."})` before any `read_file`

**Tooling options (all local, no API required):**

| Option | Format | Query method | Notes |
|---|---|---|---|
| `networkx` + JSON | JSON adjacency | Python API | Zero deps beyond networkx |
| `sqlite` + FTS | SQLite DB | SQL + FTS5 | Query with grep-like speed |
| `neo4j` (local) | Property graph | Cypher | Overkill for <100 files |
| `kuzu` (embedded) | Columnar graph | Cypher subset | Best perf/weight tradeoff |

**Recommendation:** Start with `networkx` + JSON (Step 9). Migrate to `kuzu`
if the graph exceeds 500 nodes (roughly 50+ Python files).

---

## GraphRAG vs Vector RAG — Why Graph Wins for Code

Vector RAG (ChromaDB, sqlite-vec) retrieves semantically similar chunks.
This works for natural language but breaks for code because:

- `execute_ticket()` and `drain()` are semantically similar (both process tickets)
  but structurally unrelated for most edits
- The question "what calls load_skill?" is a **graph traversal**, not a
  **semantic similarity** query
- Code has explicit, parseable structure — use it

Use vector RAG for: ticket task matching (already in `match_goal_class()`),
documentation retrieval, error message lookup.

Use graph RAG for: call graph navigation, dependency resolution,
"what breaks if I change X" impact analysis.

---

## Interim Mitigation (applies immediately)

Until Phase 2 anchor summarization is implemented, use this Cline prompt
pattern to reduce re-reads:

```
Do NOT read any file unless it is listed in the ticket's context_files.
Do NOT re-read a file you have already read in this session.
If you need to know the structure of a function, read only that function
using a targeted grep, not the full file.
If the ticket has no context_files, ask before reading anything.
```

Add this as a standing instruction in `AI-FIRST/AGENT-PERSONA.md`.

---

## Files to Modify When Implementing Each Phase

**Phase 1:**
- `AI-FIRST/AGENT-PERSONA.md` — add context_files discipline rule
- `AI-FIRST/NEXT-STEPS.md` — add lint gate requirement to audit tickets

**Phase 2:**
- `AI-FIRST/NEXT-STEPS.md` — update journal entry schema with `anchor` field
- `logs/luffy-journal.jsonl` — anchor fields added at STEP-07-D onwards

**Phase 3:**
- `tools/graphify.py` — new file: AST walker + graph builder
- `graph/fractal-claws.json` — generated artifact (add to .gitignore or commit)
- `tools/registry.py` — register `query_graph` tool
- `AI-FIRST/STEP-09-GRAPHIFY.md` — full spec (written at Step 8 close)
- `AI-FIRST/AGENT-PERSONA.md` — add `query_graph` as preferred first tool

---

## Closure Condition

This document is closed and deleted when:
1. Phase 1 rules are in `AGENT-PERSONA.md` ✓
2. Phase 2 anchor field is in journal schema and last 3 entries carry it ✓
3. `tools/graphify.py` is committed and `query_graph` is in REGISTRY ✓
4. `AI-FIRST/STEP-09-GRAPHIFY.md` exists ✓

At that point, delete this file and add a single journal entry:
```json
{"ts": "...", "step": "HOUSEKEEPING", "action": "KNOWN-ISSUE-context-window.md closed — all 3 phases implemented", "status": "done", "files": ["AI-FIRST/KNOWN-ISSUE-context-window.md"]}
```

---

*Written: 2026-04-08*  
*Maintained by: Mark Snow + Luffy*  
*Delete after: STEP-09-GRAPHIFY.md merged*
