# Dockerfile — FastAPI hub API (api.py), for Cloud Run.
#
# NOTE on statelessness: this hub keeps state on the local filesystem
# (project.meta.json, status/board.json, specs/, workspace/projects/).
# A container image has none of that baked in — every fresh container
# starts with an empty repo-state. See deploy/gcp/deploy.sh and
# DEPLOYMENT.md for how this is constrained to one always-on instance,
# and the GCS-mount alternative for real multi-instance use.

FROM python:3.11-slim

WORKDIR /app

# System deps for git (the hub auto-commits on task success) and for
# building any wheels that need compiling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects $PORT — uvicorn must bind to it, not a hardcoded 8080.
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn api:app --host 0.0.0.0 --port ${PORT} --workers 1
