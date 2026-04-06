---
protocol_id: MT-01
name: Model Selection Test
version: "0.1.0"
status: active
parameter: model_slot
default_max_depth: 2
created: 2026-04-05
hardware_target: ZBook (single node)
origin: >
  HaloClaw autonomously ran this test unprompted in an early session,
  spending several hours benchmarking before selecting Qwen3-Coder-Next-GGUF
  and spinning up a secondary Lemonade instance. This protocol formalizes
  that emergent behavior.
---

# Protocol MT-01 — Model Selection Test

## Purpose

Determine the optimal model for tool-use reliability at each swarm depth level. **Model selection is the primary testing parameter.** Recursion depth is secondary and held fixed at `max_depth: 2` for this protocol.

A model passes MT-01 only if it demonstrates **reliable, structured tool-use** — not coherent text output alone. The bar: correct tool name, correct args, first try, consistently.

---

## Test Parameter Space

```yaml
models_under_test:
  - lfm2.5-it-1.2b-FLM         # NPU path, sub-300ms TTFT
  - Qwen3.5-35B-A3B-GGUF       # MoE, 19.7GB
  - Qwen3-Coder-Next-GGUF      # Dense coder, 43.7GB — HaloClaw autonomous pick

fixed_params:
  max_depth: 2
  swarm_size: 1
  node: zbook-local
  lemonade_endpoint: http://localhost:11434
  consecutive_pass_required: 5
```

---

## Test Cases (6 total, 5 runs each = 30 points max)

### TC-01 — Single Tool, No Context
```yaml
depth: 0
prompt: "Write the string 'HALOCLAW_PING' to a file called ping.txt"
expected_tool: write_file
expected_args: {path: ping.txt, content: HALOCLAW_PING}
pass: exact tool name + path match, 5/5
```

### TC-02 — Sequential Tool Chain
```yaml
depth: 0
prompt: "Read ping.txt, append '_ACK' to its content, write it back"
expected_tools: [read_file, write_file]
pass: correct sequence, correct mutation, 5/5
```

### TC-03 — Tool Use at Depth 1
```yaml
depth: 1
parent_context: "Parent ticket: assess connectivity. Subtask: run shell command 'echo DEPTH1_OK'"
expected_tool: shell
expected_output_contains: DEPTH1_OK
pass: output captured and returned to parent, 5/5
```

### TC-04 — Decrement Trigger (Forced Escalation)
```yaml
depth: 2
decrement: 1
prompt: "Read a file that does not exist: ghost_file.txt"
expected_behavior: recognizes missing file, decrements, returns structured error to parent
pass: escalation JSON with error field populated, 5/5
```

### TC-05 — Context Inheritance (Telescope)
```yaml
depth: 1
parent_prompt_subset: "GPS: 40.29, -74.73. Trigger: !fire. Phase: triage."
child_prompt: "Using only the context provided, state the GPS and trigger type."
pass: correct values, no hallucinated fields, 5/5
```

### TC-06 — Concurrent Tickets (Single-Node Swarm Simulation)
```yaml
depth: 0
concurrent_tickets: 2
ticket_a: "Write 'SLOT_A' to slot_a.txt"
ticket_b: "Write 'SLOT_B' to slot_b.txt"
pass: correct content, no cross-contamination, both complete <120s, 5/5
```

---

## Scoring Matrix

| Model | TC-01 | TC-02 | TC-03 | TC-04 | TC-05 | TC-06 | /30 | Pass? |
|---|---|---|---|---|---|---|---|---|
| lfm2.5-it-1.2b-FLM | — | — | — | — | — | — | — | — |
| Qwen3.5-35B-A3B-GGUF | — | — | — | — | — | — | — | — |
| Qwen3-Coder-Next-GGUF | — | — | — | — | — | — | — | — |

**Pass threshold: 28/30 (93%).** Models below threshold are restricted to depth-2 leaf-only roles or excluded.

---

## Post-Test Depth Assignment

```yaml
depth_model_assignment:
  depth_0:    # Operator root — full tool chain + context retention
    min_score: 28
    preferred: highest on TC-02 + TC-05
  depth_1:    # Worker — tool use + escalation handling
    min_score: 26
    preferred: highest on TC-03 + TC-04
  depth_2:    # Leaf — single tool, deterministic, fastest TTFT
    min_score: 20
    preferred: fastest TTFT passing TC-01
```

---

## ZBook Performance Baselines (observed 2026-04-05)

| Model | Prompt tok/s | Gen tok/s | TTFT 21k ctx | TTFT fresh |
|---|---|---|---|---|
| Qwen3-Coder-Next-GGUF | ~410 | ~35 | 12–22s | <1s |
| lfm2.5-it-1.2b-FLM | NPU | ~40 | <0.3s | <0.3s |
| Qwen3.5-35B-A3B-GGUF | TBD | TBD | TBD | TBD |

**KV cache note:** Checkpoint anchor locks at ~16,372 tokens. Keep system prompt + ticket context under 16k tokens for minimum TTFT on Qwen3-Coder.

---

## Failure Handling

On any TC failure:
1. Log full exchange → `logs/mt01_failures_YYYYMMDD.jsonl`
2. Append to `TROUBLESHOOTING.md` (Context / Symptom / Error / Cause / Quick Fix / Permanent Fix / Prevention)
3. Append to `REPLICATION-NOTES.md` under "MT-01 Run [date]"
4. Open entry in `ISSUE.md`
5. **Halt. Wait for human review before rotating to next model.**

---

## Unlock Condition

MT-01 pass (28/30, 5 consecutive) unlocks **Protocol DT-01 — Depth Scaling Test:**
- `max_depth` 2 → 3
- `swarm_size` 1 → 2 (second Lemonade instance)
- Depth slots assigned from MT-01 winners
