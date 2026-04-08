import json

text = '{"outcome": "pass", "ticket_id": "INT-001", "elapsed_s": 2.0,\n "tool_calls": 3, "tokens": 200, "tok_s": 100.0, "finish": "stop", "attempt": 1,\n "ts": "2026-04-07T00:00:00"}\n'

print('Text:', repr(text))

lines = text.strip().split('\n')
for i, line in enumerate(lines):
    print(f'Line {i}: {repr(line)}')
    try:
        record = json.loads(line)
        print(f'  Record: {record}')
        print(f'  Outcome: {record.get("outcome")}')
    except json.JSONDecodeError as e:
        print(f'  JSON Error: {e}')