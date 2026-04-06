---
title: "ClawBot Agent Governance Policy"
version: "1.0.0"
owner: "MrSnowNB"
project: "Liberty Mesh / nemoclaw-setup"
status: "canonical"
lifecycle_phase: "plan"
updated: "2026-04-05"
---

# ClawBot Agent Governance Policy

> **This document is canonical.** All coding agents operating in this repo MUST read it before
> taking any action. On any ambiguity, defer to this policy. On any failure, update living docs,
> then halt and wait for human input.

---

## Core Principles

1. **All files are Markdown with YAML frontmatter or pure YAML.** No plain text files without
   frontmatter. No JSON configs without a YAML equivalent.
2. **Each task is atomic, testable, and gated.** One task = one clear deliverable that can be
   verified independently. Never bundle multiple deliverables into one commit.
3. **On any failure or uncertainty: update living docs, then stop.** Do not attempt workarounds
   without appending to `TROUBLESHOOTING.md` and `REPLICATION-NOTES.md` first.

---

## Lifecycle (Sequential Only)

Tasks follow this pipeline. **No phase may be skipped.** If any gate fails, halt, document, and
wait for human input before retrying or advancing.

```
Plan → Build → Validate → Review → Release
```

| Phase | Agent Action | Human Gate |
|-------|-------------|------------|
| **Plan** | Write or update `CLAUDE.md`/task spec. Declare inputs, outputs, acceptance criteria. | Human approves task scope. |
| **Build** | Implement the minimal change to pass validation gates. No speculative features. | — |
| **Validate** | Run all four validation gates below. All must pass. | — |
| **Review** | Update `REPLICATION-NOTES.md` with any environment deltas. Diff review. | Human reviews diff + docs. |
| **Release** | Commit. Tag if applicable. Close any related ISSUE entries. | Human confirms. |

---

## Validation Gates

All four gates must be green before the Review phase begins. Run in this order.

### Gate 1 — Unit Tests

```bash
pytest -q
```

- **Pass:** Zero failures, zero errors. Warnings acceptable.
- **Fail action:** Append to `TROUBLESHOOTING.md` → open `ISSUE.md` → halt.

### Gate 2 — Lint

```bash
ruff check . --select E,F,W,I
# or
flake8 .
```

- **Pass:** Zero errors. Warnings acceptable.
- **Fail action:** Fix lint errors, re-run. If unresolvable: append to `TROUBLESHOOTING.md` → halt.

### Gate 3 — Type Check

```bash
mypy . --ignore-missing-imports
# or
pyright
```

- **Pass:** Zero type errors on modified files. Pre-existing errors in unmodified files are exempt
  **only if documented** in `REPLICATION-NOTES.md`.
- **Fail action:** Append to `TROUBLESHOOTING.md` → halt.

### Gate 4 — Spec Drift Check

```bash
# Compare SPEC.md or CLAUDE.md against current implementation.
# Manually diff declared interfaces vs. actual code signatures.
```

- **Pass:** No undocumented public API changes. No removed capabilities without spec update.
- **Fail action:** Update spec first, then re-run gates 1–3, then proceed.

---

## Harness Acceptance Tests

Before any ticket spawning, self-improvement loop, or multi-agent work is enabled, the **single-agent
harness** must pass all six tests five consecutive times without tool hallucination.

| # | Test | Command/Prompt | Pass Condition |
|---|------|---------------|----------------|
| H-1 | Write file | `write a file scratch/hello.txt containing exactly: "HARNESS OK"` | File exists with exact content 5/5 runs. |
| H-2 | Read file | `read scratch/hello.txt and return its full contents` | Returned content matches disk exactly 5/5 runs. No hallucinated content. |
| H-3 | Edit file | `append a newline and "EDIT OK" to scratch/hello.txt` | Diff shows exactly one line added. No duplicate/garbled edits. |
| H-4 | Shell command | `run: git status and return the output verbatim` | Exact stdout returned without added narration. |
| H-5 | Two-step sequential | `write scratch/seq.txt with "STEP1", then read it back and confirm exact contents` | Both tool calls execute. Model confirms real contents, not hallucinated. |
| H-6 | Repo-local change | `add a comment to the top of operator_v7.py: # HARNESS VERIFIED` | Change lands in correct file and path. No phantom path creation. |

> **Gate rule:** If any test fails, do NOT proceed to ticket spawning. Append failure to
> `TROUBLESHOOTING.md`, update `REPLICATION-NOTES.md`, open `ISSUE.md`, and halt.

---

## Self-Improvement Loop Protocol

The self-improvement loop is a controlled, bounded process. It is **not** open-ended autonomous
rewriting. Follow this exact sequence.

### Loop Scope Rules

- Operate only on the declared `target_path` in the active task spec.
- A single loop iteration may not modify more than **5 files**.
- Each iteration must produce at least one test that validates its own change.
- The loop halts after **3 consecutive iterations without a green test suite**.

### Loop Cycle

```
Inspect → Identify Defect → Write Patch → Run Gates → Record → Repeat or Halt
```

1. **Inspect:** Read the target file(s). Identify one specific, testable defect.
2. **Identify Defect:** Write a failing test that captures the defect before patching.
3. **Write Patch:** Make the minimal code change to make the test pass.
4. **Run Gates:** All four validation gates must pass.
5. **Record:** Append a loop iteration entry to `REPLICATION-NOTES.md`.
6. **Repeat or Halt:** If gates pass and more defects exist, continue. If gates fail three times
   consecutively, halt and document.

### Loop Iteration Log Entry (append to REPLICATION-NOTES.md)

```yaml
- type: loop_iteration
  date: YYYY-MM-DD HH:MM
  iteration: N
  target_path: "path/to/file.py"
  defect_identified: "one sentence"
  test_written: "test_function_name"
  patch_summary: "one sentence"
  gates_passed: true | false
  notes: ""
```

---

## Ticket System Schema

Each ticket is a YAML file in `tickets/open/`. On dispatch, move to `tickets/active/`. On
completion, move to `tickets/closed/`.

### Parent Ticket (written by root claw / Operator)

```yaml
---
title: "Ticket title"
ticket_id: "TRIG-{UNIX_TIMESTAMP}"        # e.g. FIRE-1712345678
created_at: "YYYY-MM-DDTHH:MM:SS"
trigger: "!fire | !ems | !police | !help | task_name"
status: "open | active | escalated | closed"
depth: 0                                  # increments on escalation
decrement: 3                              # attempts before bubble-up
priority: "critical | high | normal | low"
gps_lat: null                             # float or null
gps_lon: null                             # float or null
context: "Full context string (max 240 chars for LoRa compat)"
goal: "One sentence statement of what this ticket achieves"
allowed_tools:
  - shell
  - read_file
  - write_file
model_slot: "fast | deep | intent"        # maps to HaloClaw intelligence profile
result_path: "tickets/results/TRIG-{id}.yaml"
spawned_by: "root | parent_ticket_id"
---
```

### Child Ticket (mini claw / leaf worker)

```yaml
---
title: "Child task title"
ticket_id: "CHILD-{UNIX_TIMESTAMP}"
parent_ticket_id: "TRIG-1712345678"
created_at: "YYYY-MM-DDTHH:MM:SS"
worker_model: "nemo-mini | gemma4 | qwen2.5-0.5b"
worker_backend: "ollama | lemonade"
worker_endpoint: "http://localhost:11434/v1"
status: "queued | running | done | failed"
depth: 0
decrement: 2
goal: "Narrow single-action goal"
allowed_tools:
  - shell                                 # shell-mini class
  # OR
  - read_file                             # reasoning-mini class
  - write_file
cwd: "path/to/working/directory"
timeout_seconds: 120
result:
  status: null                            # "success" | "failure"
  output: null                            # string
  files_modified: []
  exit_code: null
---
```

### Result File (written by worker on completion)

```yaml
---
ticket_id: "CHILD-1712345678"
parent_ticket_id: "TRIG-1712345678"
completed_at: "YYYY-MM-DDTHH:MM:SS"
status: "success | failure | escalated"
output: "verbatim output or summary"
files_modified:
  - "path/to/file1.py"
  - "path/to/file2.md"
exit_code: 0
notes: ""
---
```

---

## Mini Claw Worker Classes

Two worker classes only. Expand only after both are reliably passing harness tests.

| Class | Model(s) | Tools | Use Case | Max Depth | Timeout |
|-------|----------|-------|----------|-----------|---------|
| `shell-mini` | `nemo-mini`, `qwen2.5-0.5b` | `shell` only | Deterministic repo ops, file diffs, git commands, test runs | 1 | 60s |
| `reasoning-mini` | `gemma4`, `nemo-mini` | `read_file`, `write_file` | Bounded reasoning, doc updates, spec drift checks | 2 | 120s |

> **Do not introduce a third class without updating this table and passing 5/5 harness tests
> for the new class.**

---

## Model Selection Strategy

| Layer | Model | Backend | Role |
|-------|-------|---------|------|
| Root / Cline harness | Qwen 7B coding variant | Lemonade (preferred) / Ollama | Primary coding brain, tool use, orchestration |
| `shell-mini` worker | Nemo Mini or `qwen2.5-0.5b` | Ollama | Fast deterministic shell ops |
| `reasoning-mini` worker | Gemma 4 or Nemo Mini | Ollama / Lemonade | Bounded doc/code reasoning tasks |
| Guardian / intent check | `granite-guardian-8b` | Lemonade | Adversarial review on escalated tickets |

> **Frozen baseline rule:** During harness validation, do not rotate models. One model, one
> endpoint, one tool schema until H-1 through H-6 pass 5/5 consecutively.

---

## Failure Handling Protocol

On any failure, the agent MUST execute these steps in order before stopping.

### Step 1 — Capture Logs

```bash
# Save stdout/stderr to a dated log file
python -m pytest -q 2>&1 | tee logs/test_$(date +%Y%m%dT%H%M%S).log
```

### Step 2 — Append to TROUBLESHOOTING.md

Append a new `TROUBLE-XXX` entry using the full seven-field schema:

```yaml
- id: TROUBLE-XXX
  date: YYYY-MM-DD
  context: "What was being attempted"
  symptom: "What was observed"
  error_snippet: |
    exact error text here
  probable_cause: "Root cause hypothesis"
  quick_fix: "Immediate workaround"
  permanent_fix: "Correct long-term resolution"
  prevention: "How to avoid next time"
```

### Step 3 — Append to REPLICATION-NOTES.md

Append to the **Recurring Errors** table and add a freeform dated note under
**Known Pitfalls to Avoid Next Run**.

### Step 4 — Open ISSUE.md

Append a new `ISSUE-XXX` entry:

```yaml
- id: ISSUE-XXX
  date: YYYY-MM-DD HH:MM UTC
  status: open
  blocking: true
  summary: "One sentence description"
  trouble_ref: TROUBLE-XXX
  action_required: "Exact human action needed"
  resolved_date: null
  resolution_notes: null
```

### Step 5 — Halt and Wait

```
[AGENT HALT] Failure documented. Awaiting human input before proceeding.
ISSUE: ISSUE-XXX
TROUBLE: TROUBLE-XXX
Logs: logs/test_YYYYMMDDTHHMMSS.log
```

**Do not retry. Do not attempt alternative approaches. Wait.**

---

## Directory Layout (canonical)

```
.
├── AGENT-POLICY.md          ← this file (read before any action)
├── CLAUDE.md                ← task spec / active context for coding agent
├── TROUBLESHOOTING.md       ← append-only failure log
├── REPLICATION-NOTES.md     ← append-only environment + loop log
├── ISSUE.md                 ← append-only open issues
├── SPEC.md                  ← system spec (gated against implementation)
├── tickets/
│   ├── open/                ← new tickets waiting for worker
│   ├── active/              ← tickets currently being worked
│   ├── closed/              ← completed tickets
│   └── results/             ← result YAML files from workers
├── logs/                    ← dated test/lint/type logs
├── config/
│   └── settings.yaml        ← model slots, endpoints, profiles
└── src/
    └── ...                  ← implementation
```

---

## Seeded Troubleshooting Entries (Harness-Specific)

### TROUBLE-H01 — Tool Call Hallucination (Model Returns JSON as Text)

```yaml
id: TROUBLE-H01
date: 2026-04-05
context: Cline harness running coding agent against repo files
symptom: Agent emits tool call JSON as plain text in the chat reply instead of executing it
error_snippet: |
  {"tool": "write_file", "path": "scratch/test.txt", "content": "HARNESS OK"}
  (appears in chat, file is NOT written to disk)
probable_cause: |
  Model does not have reliable tool/function calling support, OR the Ollama/Lemonade
  endpoint is not returning tool_calls in the API response format. Common with models
  that were not fine-tuned for tool use (e.g., base models, some GGUF quantizations).
quick_fix: |
  1. Verify model supports tool calling: curl localhost:11434/api/chat with a tools[]
     parameter and check response has tool_calls field.
  2. Switch to qwen2.5-coder:7b or a known tool-calling model.
  3. If using Lemonade, verify it returns OpenAI-compatible tool_calls (not just text).
permanent_fix: |
  Freeze harness to a specific model+backend that passes H-1 through H-6 five times
  consecutively. Document the passing config in REPLICATION-NOTES.md. Never rotate
  models during harness validation.
prevention: |
  Before any new model is added to rotation, run H-1 (write file) as the single
  acceptance criterion. If H-1 fails, do not proceed.
```

### TROUBLE-H02 — Sequential Tool Call Memory Loss

```yaml
id: TROUBLE-H02
date: 2026-04-05
context: Agent completes first tool call (write_file) then loses context for second call (read_file)
symptom: |
  Agent successfully writes a file on turn 1, then on turn 2 claims no file exists,
  OR fabricates the file contents rather than reading from disk.
error_snippet: |
  Turn 1: [write_file] scratch/seq.txt → "STEP1" ✓
  Turn 2: [read_file] scratch/seq.txt → "I cannot find that file" (hallucinated)
  OR: "Contents: STEP1 CONFIRMED" (invented, file not actually read)
probable_cause: |
  Message history is malformed after a tool-calling turn. The assistant message that
  contains tool_calls has content=None, which some model endpoints reject or truncate.
  See HaloClaw core.py bug: tool_call turn must append role=tool result before next
  user turn, or the model loses the tool context.
quick_fix: |
  Ensure the message history after a tool call has this exact structure:
  1. {role: assistant, content: null, tool_calls: [...]}
  2. {role: tool, tool_call_id: "...", content: "result"}
  3. {role: user, content: "next message"}
  Missing step 2 causes the hallucination.
permanent_fix: |
  Patch agent loop (core.py or equivalent) to always append role=tool result immediately
  after any tool_calls turn before queuing the next user message.
prevention: |
  Test H-5 (two-step sequential) as part of every harness validation run. If H-5 fails,
  the message history format is broken regardless of which tool call passes individually.
```

### TROUBLE-H03 — Shell Command Returns Narration Instead of Output

```yaml
id: TROUBLE-H03
date: 2026-04-05
context: Agent asked to run a shell command and return verbatim output
symptom: |
  Agent responds with "I ran git status and the repository appears clean" instead of
  returning the actual stdout text from the shell execution.
error_snippet: |
  Expected: "On branch main\nnothing to commit, working tree clean"
  Got: "The git status command shows the working tree is clean."
probable_cause: |
  Model is paraphrasing tool output instead of passing it through. Often caused by
  a system prompt that says "be concise" or "summarize results" conflicting with the
  verbatim output requirement.
quick_fix: |
  Add explicit instruction to system prompt: "When executing shell commands, return
  the verbatim stdout output in a code block. Do not paraphrase or summarize."
permanent_fix: |
  Add a post-processor assertion in the harness that checks shell tool results are
  returned verbatim. If the result contains the exact expected string, pass. If not, fail.
prevention: |
  H-4 (shell command verbatim) must be in every harness validation run. A model that
  passes H-1 but fails H-4 is not suitable for shell-mini worker class.
```

### TROUBLE-H04 — Self-Improvement Loop Does Not Replicate

```yaml
id: TROUBLE-H04
date: 2026-04-05
context: Attempting to recreate Cline self-improvement loop that worked previously
symptom: |
  Loop either does not start (model does not self-inspect) or runs once and stops,
  or produces patches that break existing tests without writing new ones first.
error_snippet: |
  Iteration 1: patch written → gates fail → no TROUBLESHOOTING.md entry → model retries anyway
  OR: Iteration 1: patch written → model claims "done" with no test written
probable_cause: |
  The self-improvement loop requires an explicit "write a failing test first" instruction
  in the task spec. Without this, the model skips straight to patching. The loop also
  requires a halt condition (3 consecutive failures) to be stated explicitly, or it will
  either loop infinitely or stop after one iteration.
quick_fix: |
  In CLAUDE.md / task spec, add:
  1. "Before patching, write a failing test named test_<defect>.py."
  2. "Halt after 3 consecutive gate failures. Append to TROUBLESHOOTING.md first."
  3. "Each iteration appends one entry to REPLICATION-NOTES.md."
permanent_fix: |
  The Loop Iteration Log Entry schema in AGENT-POLICY.md must be included verbatim in
  every self-improvement task spec. This forces the model to record state before it can
  claim the loop is complete.
prevention: |
  Start every self-improvement session by running H-1 through H-6. If any harness test
  fails, fix it before starting the loop. The loop cannot be reliable if the base harness
  is unreliable.
```

---

## Quick Reference Card

```
LIFECYCLE:     Plan → Build → Validate → Review → Release (no skipping)
GATES:         pytest -q | ruff/flake8 | mypy/pyright | spec drift
HARNESS:       H-1 write | H-2 read | H-3 edit | H-4 shell | H-5 seq | H-6 repo
               Must pass 5/5 before ticket spawning or self-improvement loop
ON FAILURE:    logs → TROUBLESHOOTING.md → REPLICATION-NOTES.md → ISSUE.md → HALT
TICKETS:       Parent YAML in tickets/open/ → active/ → closed/
               Child inherits subset of allowed_tools + model_slot
               Decrement: 3 (parent), 2 (child) before escalation
MODELS:        Root = Qwen7B/Lemonade | shell-mini = NemoMini/qwen0.5b | reasoning-mini = Gemma4
FROZEN RULE:   One model, one endpoint, one tool schema during harness validation.
```
