# scripts/log_journal.py — T06 helper
# Append a log entry to luffy-journal.jsonl
# STEP-09: agent_id field added — every record is attributable
import json, os, time


def append_journal(record: dict, agent_id: str = "luffy-v1") -> None:
    """Append one record to logs/luffy-journal.jsonl.

    Args:
        record:   Journal entry dict. Must contain at minimum: step, action, status.
        agent_id: Who wrote this entry. Defaults to 'luffy-v1'.
                  Children use IDs like 'luffy-child-TASK-042' (STEP-11+).
    """
    path = "logs/luffy-journal.jsonl"
    record.setdefault("agent_id", agent_id)
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    # legacy compat: also set 'timestamp' if callers expect it
    record.setdefault("timestamp", record["ts"])
    os.makedirs("logs", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    # STEP-02-A completion log
    append_journal({
        "ticket_id": "STEP-02-A",
        "step": "terminal-tool-setup",
        "action": "committed tools/terminal.py and updated toolbox.yaml",
        "status": "success",
        "detail": "Terminal tool implementation complete. MCP tool connection error logged - no github MCP server configured."
    })
    print("Logged to logs/luffy-journal.jsonl")
