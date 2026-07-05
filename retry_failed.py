import os
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = "project-f3ec0b47-4580-4493-a79"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "E:/password/GCP_medical-azure-key.json"

import sys
sys.path.insert(0, ".")
import asyncio
from hub.runner.task_runner import run_task_async

failing = [
    ("T05", "F14"),
    ("T04", "F15"),
    ("T05", "F17"),
    ("T05", "F18"),
]

async def main():
    for task_id, feature in failing:
        print(f"=== Retrying {feature}/{task_id} ===")
        result = await run_task_async(
            task_id, project_id="project-2026-07-05", feature=feature, max_retries=3,
        )
        print("ok:", result.get("ok"))
        print("error:", result.get("error"))
        print("commit_sha:", result.get("commit_sha"))
        print()

asyncio.run(main())
