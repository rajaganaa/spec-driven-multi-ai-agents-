import os
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = "project-f3ec0b47-4580-4493-a79"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "E:/password/GCP_medical-azure-key.json"

import sys, json
sys.path.insert(0, ".")
import asyncio
from hub.runner.task_runner import run_task_async

async def main():
    result = await run_task_async("T05", project_id="project-2026-07-05", feature="F17", max_retries=2)
    print("=== F17/T05 ===")
    print("ok:", result.get("ok"))
    print("error:", result.get("error"))
    print("commit_sha:", result.get("commit_sha"))
    print()
    if not result.get("ok"):
        print("--- FINAL TEXT ---")
        print(result.get("final_text"))

asyncio.run(main())
