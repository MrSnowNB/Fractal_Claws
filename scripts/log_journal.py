# scripts/log_journal.py — T06 helper
# Append a log entry to luffy-journal.jsonl
import json, os, time

def append_journal(record: dict) -> None:
    path = "logs/luffy-journal.jsonl"
    record.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
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