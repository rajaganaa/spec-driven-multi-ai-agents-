#!/usr/bin/env bash
# deploy/gcp/deploy.sh — Part 7: deploy api.py to Cloud Run
#
# Run from the repo root: ./deploy/gcp/deploy.sh
#
# IMPORTANT ARCHITECTURE NOTE — read before running this:
#
# my-agent-hub keeps ALL of its state (project.meta.json,
# status/board.json, specs/, workspace/projects/<id>/, git history) on
# the local container filesystem. Cloud Run containers are ephemeral
# and, by default, can be scaled to multiple concurrent instances that
# do NOT share a filesystem — so "container instance #2" would not see
# the project that "container instance #1" created with /api/new.
#
# This script pins --min-instances=1 --max-instances=1 so there is
# always exactly one instance, which makes local-disk state behave
# like a single small persistent VM... with one big caveat: a new
# deploy, a crash, or Cloud Run recycling that one instance still WIPES
# the workspace, because the underlying disk is still not persistent
# storage. That's an acceptable tradeoff for a personal/demo tool, and
# matches what the original ask described, but it is NOT what
# "industry grade" usually means for stateful data.
#
# For real production use, do ONE of:
#   (a) Mount a GCS bucket via Cloud Run volume mounts (gcsfuse) so
#       workspace/, specs/, and status/ persist across instances and
#       restarts — https://cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts
#   (b) Move api.py off Cloud Run entirely, onto a small persistent
#       Compute Engine VM or GKE pod with a real attached disk.
# Both are bigger changes than fit in "wrap the existing CLI" — flagging
# this rather than silently shipping something that loses your work on
# the first redeploy.

set -euo pipefail

GCP_PROJECT="${GCP_PROJECT:?Set GCP_PROJECT to your GCP project id}"
GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-agentforge-api}"
VLLM_BASE_URL="${VLLM_BASE_URL:-}"   # e.g. http://1.2.3.4:8000/v1 — optional
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:?Set FRONTEND_ORIGIN to your deployed frontend's origin, e.g. https://you.github.io}"

echo "==> Deploying $SERVICE_NAME to Cloud Run ($GCP_REGION, project $GCP_PROJECT)"
echo "    (pinned to exactly 1 instance — see the note at the top of this script)"

ENV_VARS="FRONTEND_ORIGIN=${FRONTEND_ORIGIN},GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${GCP_PROJECT},GOOGLE_CLOUD_LOCATION=${GCP_REGION}"
if [[ -n "$VLLM_BASE_URL" ]]; then
  ENV_VARS="${ENV_VARS},VLLM_BASE_URL=${VLLM_BASE_URL},VLLM_MODEL=${VLLM_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"
fi

# VLLM_API_KEY and any GCP service-account key go through Secret
# Manager, NOT --set-env-vars — env vars set this way are visible in
# `gcloud run services describe` output and in the Cloud Console to
# anyone with read access to the service.
SECRET_FLAGS=()
if [[ -n "$VLLM_BASE_URL" ]]; then
  if ! gcloud secrets describe vllm-api-key --project "$GCP_PROJECT" >/dev/null 2>&1; then
    echo "==> Secret 'vllm-api-key' not found. Create it once with:"
    echo "      printf '%s' 'your-real-vllm-key' | gcloud secrets create vllm-api-key --project $GCP_PROJECT --data-file=-"
    exit 1
  fi
  SECRET_FLAGS+=(--set-secrets "VLLM_API_KEY=vllm-api-key:latest")
fi

# Prefer this over GOOGLE_APPLICATION_CREDENTIALS pointing at a key
# file baked into the image: grant the Cloud Run service's own runtime
# service account the "Vertex AI User" role instead, and skip
# GOOGLE_APPLICATION_CREDENTIALS entirely — ADC picks it up
# automatically. Only fall back to a mounted key-file secret if your
# org requires a separate service account.
echo "==> NOTE: this deploy relies on Application Default Credentials via the"
echo "    Cloud Run service's runtime service account. Make sure it has the"
echo "    'Vertex AI User' role:"
echo "      gcloud projects add-iam-policy-binding $GCP_PROJECT \\"
echo "        --member=serviceAccount:\$(gcloud run services describe $SERVICE_NAME --project $GCP_PROJECT --region $GCP_REGION --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || echo '<service-account>') \\"
echo "        --role=roles/aiplatform.user"

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$GCP_PROJECT" \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 1 \
  --set-env-vars "$ENV_VARS" \
  "${SECRET_FLAGS[@]}"

URL=$(gcloud run services describe "$SERVICE_NAME" --project "$GCP_PROJECT" --region "$GCP_REGION" --format='value(status.url)')
echo
echo "✓ Deployed: $URL"
echo "  Set this as VITE_API_URL in frontend/.env, then rebuild/redeploy the frontend."
