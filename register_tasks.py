import sys
sys.path.insert(0, ".")
from hub.memory import spec_loader
from pathlib import Path

tasks_dir = Path("specs/tasks")
count = 0
for feature_dir in sorted(tasks_dir.glob("F1[4-8]")):
    feature_id = feature_dir.name
    for task_file in sorted(feature_dir.glob("*.md")):
        task_id = task_file.stem.split("-")[0]
        result = spec_loader.update_board_status(task_id, "pending", feature=feature_id)
        ok = result.get("ok")
        err = result.get("error")
        status = "OK" if ok else "FAILED: " + str(err)
        print(feature_id + "/" + task_id + ": " + status)
        count += 1

print()
print("Registered " + str(count) + " tasks.")
