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
    result = await run_task_async("T05", project_id="project-2026-07-05", feature="F14", max_retries=1)
    print("ok:", result.get("ok"))
    print("error:", result.get("error"))
    print()
    print("--- FULL RESULT ---")
    print(json.dumps(result, indent=2, default=str)[:4000])

asyncio.run(main())
