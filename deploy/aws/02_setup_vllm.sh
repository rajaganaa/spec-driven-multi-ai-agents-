#!/usr/bin/env bash
# deploy/aws/02_setup_vllm.sh — Part 1: install vLLM + run it as a
# systemd service (survives SSH disconnects and reboots — a bare
# foreground `python -m vllm...` dies the moment your terminal does).
#
# Run THIS ON THE EC2 INSTANCE (after 01_launch_ec2.sh), e.g.:
#   scp -i key.pem deploy/aws/02_setup_vllm.sh ubuntu@<ip>:~
#   ssh -i key.pem ubuntu@<ip>
#   VLLM_API_KEY='choose-a-real-secret' ./02_setup_vllm.sh
#
# Model: Qwen2.5-Coder-7B-Instruct, NOT the originally-requested 32B —
# the 32B variant does not fit in a T4's 16GB VRAM at any reasonable
# context length. 7B does, comfortably, at --max-model-len 8192.

set -euo pipefail

VLLM_API_KEY="${VLLM_API_KEY:?Set VLLM_API_KEY to a real secret before running this script, e.g. VLLM_API_KEY=$(openssl rand -hex 24) ./02_setup_vllm.sh}"
VLLM_MODEL="${VLLM_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"

echo "==> Installing vLLM (this can take a few minutes on first run)…"
pip install --upgrade pip -q
pip install vllm -q

VENV_PY="$(command -v python3)"

echo "==> Writing systemd unit…"
sudo tee /etc/systemd/system/vllm.service > /dev/null <<EOF
[Unit]
Description=vLLM OpenAI-compatible server (${VLLM_MODEL})
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${HOME}
Environment="VLLM_API_KEY=${VLLM_API_KEY}"
ExecStart=${VENV_PY} -m vllm.entrypoints.openai.api_server \\
  --model ${VLLM_MODEL} \\
  --host 0.0.0.0 \\
  --port ${VLLM_PORT} \\
  --max-model-len ${VLLM_MAX_MODEL_LEN} \\
  --dtype auto \\
  --api-key ${VLLM_API_KEY}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vllm
sudo systemctl restart vllm

echo "==> Waiting for the model to load (first load downloads weights, can take a few minutes)…"
for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${VLLM_PORT}/health" > /dev/null 2>&1; then
    echo "✓ vLLM is up on port ${VLLM_PORT}"
    echo "  Logs: sudo journalctl -u vllm -f"
    exit 0
  fi
  sleep 10
done

echo "vLLM didn't report healthy within 10 minutes — check logs:" >&2
echo "  sudo journalctl -u vllm -n 100 --no-pager" >&2
exit 1
