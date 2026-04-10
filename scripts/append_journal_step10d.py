import json

line = json.dumps({
    "ts": "2026-04-10T11:28:04-04:00",
    "step": "STEP-10-D",
    "agent_id": "luffy-v1",
    "action": "gate passed",
    "status": "done",
    "files": ["logs/luffy-journal.jsonl", "logs/ctx-cache.json"],
    "anchor": {
        "system_state": "STEP-10 complete: graphify_repo working, 4 tests green, ctx-cache.json valid",
        "open_invariants": ["journal append-only", "ctx-cache.json hashes non-empty"],
        "next_entry_point": "STEP-11-A: add LawViolationError + assert_scratch_written() to agent/sequence_gate.py"
    }
})

with open("logs/luffy-journal.jsonl", "a") as f:
    f.write(line + "\n")

print("Journal entry appended successfully")