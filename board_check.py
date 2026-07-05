import json
with open("status/board.json", encoding="utf-8") as f:
    data = json.load(f)
tasks = data.get("tasks", [])
by_status = {}
for t in tasks:
    by_status.setdefault(t.get("status"), []).append(t.get("id") + " (" + str(t.get("feature")) + ")")
for status, ids in by_status.items():
    print(status + " (" + str(len(ids)) + "):", ", ".join(ids))
