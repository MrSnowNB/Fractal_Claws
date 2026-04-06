# VISION.md — Fractal Claws
### An AI-First, First-Principles Architecture for Autonomous Agent Systems

> *"The only way to know the outcome is to run the process."*
> — Stephen Wolfram, on computational irreducibility

---

## Preamble: Why This Document Exists

Every failed attempt at building this system died the same death: complexity was introduced before correctness was proven. Features were built on foundations that had never been tested. Memory systems were designed before a single ticket completed. Swarms of 100 bots were launched before 1 bot was reliable.

This document is the immune system against that failure mode. It is not a roadmap. It is not a feature list. It is the **philosophical and architectural contract** that every new instance of this system — every new Bot-Buddy, every new bud — must be born knowing. It travels with the codebase. It is read before a single line of new code is written. It is the thing that stays true when everything else is in flux.

---

## Part I: First Principles

### 1.1 What Is This System, Really?

Strip away the code. Strip away the YAML tickets, the Lemonade endpoint, the Qwen models, the folder structure. What remains?

**A goal arrives. Work happens. The goal is resolved or it is not. The system learns either way.**

That is the entire system. Everything else is implementation. The moment any implementation detail starts driving architectural decisions — the moment "we need Redis for the queue" or "we need a cron job for the heartbeat" becomes load-bearing — the system has been captured by its own scaffolding. This has happened before. It must not happen again.

### 1.2 Computational Irreducibility as a Design Constraint

Wolfram's principle of computational irreducibility states that for many systems, there is no shortcut to knowing the outcome other than running the process step by step. You cannot predict what tickets a goal will generate. You cannot predict how deep the dependency tree will go. You cannot predict which tool calls will fail and need retry. You cannot schedule completion.

**This is not a limitation. It is the correct model of what intelligence looks like when applied to genuinely novel problems.**

The implications are architectural:

- **No external clocks.** A timer-based trigger (cron, Task Scheduler, sleep loops) assumes you know when work will be ready. You don't. The system clocks itself through the completion of work, not through the passage of time.
- **No pre-allocated turns.** A fixed retry depth assumes you know how many attempts a problem needs. You don't. Depth is determined by the problem, not by a configuration value.
- **No pre-designed tool chains.** A tool is added when solved tickets demonstrate the need, not when a designer anticipates it. The toolchain emerges from evidence.

The solved-ticket library is the only place where irreducibility is partially tamed. A problem that has been solved before has a known path. The system navigates that path in one step. But the frontier — genuinely new problems — remains irreducible. The bud runs until it's done.

### 1.3 The Bud as the Atomic Unit

The term "bud" is deliberate. A bud is:

- **Self-contained.** It carries everything it needs to start: a goal, a model endpoint, a tool whitelist, and the memory of every solved problem before it.
- **Finite.** It is born with a goal and dies when that goal is resolved or permanently failed. It does not linger. It does not idle. It does not accumulate state beyond its purpose.
- **Reproducible.** Any bud can be cloned from the rooted tree. The folder structure IS the bot. `cp -r Fractal_Claws/ New_Bot/` produces a new bot with the full institutional memory of its parent.
- **Provable.** A bud that cannot complete the proof gate — `python init.py "write hello world to output/test.txt"` — is not a bud. It is a broken script. The proof gate runs before any new work begins, every time.

### 1.4 The Daemon as Pure Witness

The daemon does not manage. It does not schedule. It does not retry. It does not intervene.

The daemon watches the filesystem and reports what it sees: tickets open, tickets done, tickets failed, bud alive or dead. It is a super-robot-secretary with no authority and total visibility. It is the only component in the system that has a continuous existence — everything else is born and dies with its purpose.

The reason the daemon has no authority is the same reason a scientific observer cannot be part of the experiment: **intervention corrupts the signal.** If the daemon could trigger retries, it would become a second parent agent. If it could spawn new buds, it would become a second orchestrator. The moment it acts, it is no longer a witness — it is a participant, and the system has gained a hidden control path that is not documented in the ticket record.

---

## Part II: The Architecture

### 2.1 The Three Layers

The system has exactly three layers. They do not mix. Communication between layers is one-directional and filesystem-mediated.

```
┌─────────────────────────────────────────────────────┐
│  LAYER 0 — FOUNDATION                               │
│  pre_flight.py   call_model()   3 base tools        │
│  These never change. They are the proof gate.       │
├─────────────────────────────────────────────────────┤
│  LAYER 1 — MEMORY                                   │
│  memory/solved/   memory/tools/   memory/failures/  │
│  Read-only at runtime. Written only during          │
│  post-run consolidation. The institutional memory.  │
├─────────────────────────────────────────────────────┤
│  LAYER 2 — EXECUTION                                │
│  tickets/open/   tickets/done/   tickets/failed/    │
│  The live work queue. Born with a goal, dies        │
│  when the queue is empty.                           │
└─────────────────────────────────────────────────────┘
```

**Layer 0 is the constitution.** It cannot be modified by a running bud. It is tested before any bud runs. It is the one thing that must be true for everything else to be possible.

**Layer 1 is the library.** It is the accumulated intelligence of every bud that came before. A new goal consults the library before decomposing. If a matching solved path exists, it is replayed. If not, the new path is discovered and recorded. The library grows. It is the only thing that makes the system smarter over time.

**Layer 2 is the work surface.** It is temporary, local, and disposable. Tickets are created, executed, and resolved here. When a bud dies, Layer 2 is either empty (success) or contains a record of failure (which is promoted to Layer 1 so the next bud knows what not to try).

### 2.2 The Ticket as a Solved-Path Record

A ticket is not a task description. A ticket is a **navigational record**.

When a ticket is written to `tickets/open/`, it contains a task — a description of work to be done. When it moves to `tickets/done/`, it contains something more valuable: **proof that a specific sequence of tool calls resolved a specific class of problem**. The task field is the question. The result file is the answer. Together, they are a solved path.

The solved-path record includes:
- The exact tool calls made, in order
- The allowed_tools that were sufficient
- The depth reached (how many retries were needed)
- The result that constituted success
- The timestamp (how long the path took to walk)

When a new goal arrives that resembles a previously solved goal, the parent agent does not decompose from scratch. It retrieves the matching solved path and replays it. The search space has been reduced from infinite to one known path. **This is the only form of intelligence acceleration that does not violate computational irreducibility** — you are not predicting the outcome, you are recognizing a previously traversed path.

### 2.3 The Tool Chain Is Emergent, Not Designed

The base tools are three:

1. `read_file` — read any file on the local filesystem
2. `write_file` — write any file on the local filesystem
3. `exec_python` — execute a Python script from the output/ directory

These three tools are sufficient to solve any problem that can be expressed as a sequence of read, write, and compute operations. They are the Turing-complete foundation. Everything else is convenience.

A new tool is added to the system only when solved tickets demonstrate the need. The threshold is three: three solved tickets that required the same improvised tool call pattern, implemented manually via `write_file` + `exec_python`, earn the right to a dedicated tool. The tool chain is a compression of proven patterns, not an anticipation of future needs.

This constraint prevents the most common failure mode in agent system design: building a rich tool ecosystem before understanding what problems the agent actually encounters. The tool list starts at three. It grows by evidence. It never shrinks — a tool that was earned by evidence remains, because the evidence that earned it is still in `memory/solved/`.

### 2.4 The Lifecycle of a Bud

```
BIRTH
  A goal arrives via: --goal "..." argument, or a ticket dropped into tickets/open/
  pre_flight.py runs — Lemonade alive? call_model() returns non-empty? if not, die.
  memory/solved/ is consulted — is this a known path?
    YES: replay the solved path directly
    NO:  A3B decomposes the goal into atomic tickets

WORK
  The parent agent enters the wave-based dispatch loop:
    Scan tickets/open/ for tickets whose deps_met() returns True
    Dispatch each ready ticket to a child agent subprocess
    Child executes tool calls, writes result file, exits
    Parent evaluates result file — pass or fail
    Pass: ticket moves to tickets/done/
    Fail: ticket retries at depth+1, or moves to tickets/failed/ if max_depth reached
    Wave repeats until tickets/open/ is empty or deadlocked

CONSOLIDATION
  After each wave:
    tickets/done/ tickets with N successes → promoted to memory/solved/
    tickets/failed/ tickets → reason appended to memory/failures/
    Tool usage patterns extracted → memory/tools/ updated

DEATH
  tickets/open/ is empty AND no deferred tickets remain
  The bud exits cleanly
  locks/agent.lock is deleted
  The daemon records the final state
  memory/solved/ is richer than when the bud was born
```

### 2.5 The Daemon Contract

The daemon has one job: **observe and report**.

It watches four things:
- `tickets/open/` — work remaining
- `tickets/done/` — work completed
- `tickets/failed/` — work that could not be resolved
- `locks/agent.lock` — is a bud currently alive?

It reports these counts continuously. It takes no action based on what it observes. It does not restart a dead bud. It does not requeue a failed ticket. It does not alert anyone (unless an alerting tool has been earned by the evidence threshold and added to its allowed_tools — which would require three solved tickets demonstrating the need for alerting, which is a high bar for a witness).

The daemon's output is the ground truth for any human monitoring the system. It is the answer to "what is the bot doing right now?" It does not interpret. It does not summarize. It counts and timestamps.

---

## Part III: The Rules

These five rules are the atomic ruleset. They are not guidelines. They are the invariants of the system. A bud that violates any of them is not a Fractal Claws bud — it is a different system wearing the same folder structure.

### Rule 1 — Pre-flight before everything

`pre_flight.py` runs before any ticket is dispatched. It verifies that the model endpoint is alive and returns a non-empty response. If pre-flight fails, the bud does not start. It exits with a clear error. It does not try to work around a dead endpoint. It does not queue tickets for later. It dies cleanly and waits for the human to fix the environment.

**Why:** A bud that starts working with a broken model endpoint will fail every ticket, generate a full `tickets/failed/` directory, and leave the human with a useless failure log and no signal about the actual problem. Pre-flight surfaces the real problem in 3 seconds instead of 3 minutes.

### Rule 2 — Search memory before decomposing

For any new goal, `memory/solved/` is searched for a matching solved path before A3B is called. If a match is found, the solved path is replayed directly. A3B is expensive — it uses the large decomposition model, consumes tokens, and takes time. Every call to A3B that could have been a memory lookup is waste.

**Why:** The value of the solved-ticket library compounds over time only if it is actually used. A system that always decomposes from scratch is not learning. It is rediscovering. The library exists to make the second traversal of any path free.

### Rule 3 — One ticket, one result file

A ticket is not complete until a result file exists at the path specified in `result_path`. Not a log entry. Not a print statement. Not an exception that was caught and swallowed. A file. On disk. Readable by the parent agent's `evaluate_result()` function.

**Why:** The result file is the contract between the child agent and the parent agent. It is the only signal the parent has about what happened. A child that "succeeds" without writing a result file has left the parent agent blind. The parent cannot evaluate what it cannot read. The file is the proof.

### Rule 4 — Failures are data, not shame

Every failed ticket appends a one-line failure reason to `memory/failures/`. The reason is specific: not "task failed" but "exec_python returned returncode 1: ModuleNotFoundError: numpy not found". The failure record includes the ticket_id, the task description, the tool calls attempted, and the exact error.

**Why:** A failure that is not recorded is a failure that will repeat. The entire history of this project — Swarm-100, 4-Stage-memory, Strix-Swarm, HaloClaw — is a story of the same failures repeating because they were not recorded in a place that the next attempt would read. `memory/failures/` is that place. It is the scar tissue of the system. Scar tissue is what makes skin stronger.

### Rule 5 — A tool earns its place

No new tool is added to `allowed_tools` until three solved tickets demonstrate the need. The tool list starts at three (read_file, write_file, exec_python). It grows by evidence. Feature anticipation — "we'll probably need an HTTP tool eventually" — is not evidence. Three solved tickets that required manually writing a Python script to make an HTTP request because no HTTP tool existed is evidence.

**Why:** Every tool added to the system is a new surface for failure. A tool that has never been tested in a real ticket cycle is a guaranteed source of unexpected behavior. The evidence threshold is not bureaucracy — it is the minimum signal needed to know that a tool addresses a real, recurring need rather than an imagined future one.

---

## Part IV: The Institutional Memory

### 4.1 What Travels With Every Clone

When a new Bot-Buddy is born from this repository, it inherits:

- `pre_flight.py` — the proof gate
- `AGENT-POLICY.md` — the operational rules
- `LESSONS_LEARNED.md` — the retrospective record of every major failure
- `VISION.md` — this document
- `memory/solved/` — every solved path from every previous bud
- `memory/failures/` — every recorded failure reason
- `memory/tools/` — every proven tool usage pattern

It does NOT inherit:
- `tickets/open/` — cleared for the new goal
- `tickets/done/` — cleared (but source of solved/ promotion)
- `tickets/failed/` — cleared (but source of failures/ promotion)
- `locks/agent.lock` — deleted on clone
- `output/` — cleared for new work
- `logs/` — cleared for new session

The new bud starts fresh on the work surface but inherits the full intelligence of every bud before it. **The memory layer is the gene. The work surface is the phenotype.**

### 4.2 LESSONS_LEARNED.md Is Sacred

`LESSONS_LEARNED.md` is not documentation. It is not a changelog. It is the hardest-won knowledge in the system — the things that were learned by failing, not by reasoning. It is written in plain English, not code. It is read by every new Cline session before a single ticket is written. It is never deleted. It is only appended.

The format is simple:
```
## [date] — [what was attempted]
**What happened:** [specific failure]
**Why it happened:** [root cause, not symptom]
**What to do instead:** [specific corrective action]
**Still true as of:** [last verified date]
```

The "still true as of" field is critical. A lesson that was true in October 2025 may be obsolete by April 2026. But it remains in the document with its last-verified date so that a human can decide whether to act on it, rather than a bud silently ignoring it.

### 4.3 The Solved-Ticket Library Is the Only Form of Learning

The system does not fine-tune models. It does not update weights. It does not maintain a vector database of embeddings. These are all forms of implicit learning that are opaque, hard to inspect, and impossible to audit.

The solved-ticket library is **explicit, auditable, and human-readable learning**. Every entry is a YAML file. Every YAML file is a complete record of a solved problem: the goal, the tickets, the tool calls, the result. A human can read any entry and understand exactly what the bud did and why it worked.

This is not a limitation of the system. This is a deliberate design choice. **Explainable intelligence is more valuable than opaque intelligence in a system that a human must trust and maintain.** The solved-ticket library can be inspected, corrected, pruned, and extended by a human with a text editor. No model fine-tuning pipeline required.

---

## Part V: The AI-First Principles

### 5.1 The Model Is the Executor, Not the Orchestrator

The model (currently Qwen3.5 in its various quantizations) is responsible for one thing: given a ticket's task description and context files, generate the correct tool call sequence. It is not responsible for understanding the overall goal. It is not responsible for knowing what other tickets exist. It is not responsible for managing state.

The parent agent is the orchestrator. The model is the executor. These roles must never be conflated. A model that is asked to orchestrate — to maintain awareness of the full goal while executing individual tickets — will hallucinate orchestration decisions, create phantom dependencies, and generate tickets for work that has already been done. This has happened in every previous attempt.

**The model sees exactly one ticket at a time.** Its context window contains: the ticket task, the allowed tools, the context files specified in `context_files`, and the system prompt. Nothing else. The constraint is not a limitation — it is what makes the model's output reliable.

### 5.2 Small Model, Large Model, Right Model

The system currently uses two models for two distinct purposes:

- **A3B (Qwen3.5-35B)** — goal decomposition. This requires reasoning about the full goal, identifying atomic subtasks, and expressing dependencies correctly. It needs the larger model's reasoning capacity.
- **Child (Qwen3.5-4B)** — ticket execution. This requires precise tool call generation for a single, specific, narrow task. The smaller model is faster, cheaper, and sufficient for well-constrained single-ticket work.

The principle: **use the smallest model that is sufficient for the task**. Decomposition is hard — it requires understanding context, identifying dependencies, and generating structured output that will drive real execution. Execution is narrow — it requires generating one or two tool calls for a task description that already specifies exactly what to do.

As the solved-ticket library grows, decomposition becomes less necessary (memory lookup replaces it), and the A3B model is called less frequently. Eventually, for a fully mature system working entirely within known problem domains, A3B is called only for genuinely novel goals. The system becomes faster and cheaper as it learns.

### 5.3 Local-First Is a Principle, Not a Preference

All compute runs on the local machine. Lemonade serves models from unified RAM. No API calls to external services. No cloud inference. No data leaves the machine.

This is not just a cost decision. It is an **architectural correctness decision**. A system that depends on external APIs for its core intelligence has an availability dependency that cannot be solved by the system itself. When the API is down, the bud dies for a reason it cannot diagnose or recover from. The lockfile shows it as dead. The daemon reports it as dead. But the actual cause — a rate limit, a network partition, an API deprecation — is invisible to the system.

Local inference means the system's availability is bounded by hardware it controls. Pre-flight can verify that the model endpoint is alive before starting work. If it's not alive, the human can fix it. The system's failure modes are local, diagnosable, and correctable.

### 5.4 The Filesystem Is the Message Bus

There is no Redis. There is no RabbitMQ. There is no ZeroMQ. There is no database. The filesystem is the message bus, the queue, the state store, the audit log, and the memory system.

This is not a simplification. It is a correctness decision. Every state transition in the system is a file operation: a ticket moves from `open/` to `done/` or `failed/`. A result is written to `logs/`. A solved path is promoted to `memory/solved/`. The daemon reads directory listings. The parent evaluates result files.

The filesystem is:
- **Durable** — files survive process crashes
- **Inspectable** — a human with `ls` can see the full system state
- **Auditable** — file modification times are timestamps
- **Portable** — `cp -r` clones the entire system state

No message bus offers all four properties at zero operational cost. The filesystem does.

---

## Part VI: The Growth Model

### 6.1 The Tree Metaphor

The system is called Fractal Claws for a reason. The architecture is fractal: the bud is a microcosm of the tree, and the tree is a macrocosm of the bud. A bud that solves a goal and records its solved paths becomes the root of a new tree. A new Bot-Buddy cloned from this root inherits the solved paths and starts with a richer library than its parent had.

The growth is fractal because the structure at every scale is identical:
- A ticket is a micro-goal with sub-steps (tool calls)
- A bud is a macro-goal with sub-goals (tickets)
- A tree is a meta-goal with sub-buds (clones with different missions)

The rules that govern ticket execution are the same rules that govern bud lifecycle which are the same rules that govern tree growth. The five rules apply at every level of scale.

### 6.2 The Proof Gate Is the Growth Constraint

A bud cannot grow — cannot spawn child buds, cannot accept new goals, cannot be cloned into new trees — until it has passed the proof gate on its current goal. This is not a technical limitation. It is a principled constraint.

A system that grows before it is proven is a system that propagates its failures. If the base bud has a broken `call_model()` function, cloning it 100 times produces 100 broken bots. Swarm-100 was this mistake at scale. The proof gate is what prevents that mistake from recurring.

**The proof gate is the price of growth.** It is not a tax. It is the minimum evidence that the bud is worth replicating.

### 6.3 The Long-Term Vision

The long-term vision is a tree of specialized buds, each the master of a specific problem domain, sharing a common memory layer:

- A bud that has solved 50 file-manipulation tickets knows everything about local filesystem operations
- A bud that has solved 30 Python debugging tickets knows every common error pattern and its fix
- A bud that has solved 20 data-pipeline tickets knows the standard tool call sequences for ETL work

These buds share `memory/solved/` across the tree. A new bud inheriting from all three starts with the combined knowledge of all three predecessors. The solved-path library becomes the collective intelligence of the entire system.

This is not RAG. It is not fine-tuning. It is not a vector database. It is a **curated, explicit, human-readable knowledge base** built from proven execution records. Every entry earned its place by working in a real ticket cycle. Nothing is hypothetical.

---

## Appendix: The Proof Gate Procedure

Before any new work begins, before any new feature is added, before any new Bot-Buddy is deployed:

```bash
python pre_flight.py
# Expected: [pre_flight] OK — model alive, non-empty response

python init.py "write the string hello world to output/test.txt and verify the file exists"
# Expected:
#   tickets/open/TASK-001.yaml created
#   tickets/open/TASK-002.yaml created
#   [parent] PASS: TASK-001
#   [parent] PASS: TASK-002
#   [parent] done
#   output/test.txt contains: hello world
```

If both commands produce the expected output, the bud is proven. Work may begin.

If either command fails, work does not begin. The failure is recorded in `LESSONS_LEARNED.md`. The root cause is fixed. The proof gate is run again. This loop continues until the proof gate passes. There is no other path forward.

---

*This document was written on April 6, 2026. It is a living document. Append to it. Never delete from it. The lessons are permanent. The architecture evolves.*

*— Mark Snow / GarageAGI*
