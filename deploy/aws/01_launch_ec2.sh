#!/usr/bin/env bash
# deploy/aws/01_launch_ec2.sh — Part 1: provision the vLLM EC2 box
#
# Launches a g4dn.xlarge (T4, 16GB VRAM) running the AWS Deep Learning
# AMI, with a security group that:
#   - opens 22 (SSH)  only to YOUR current public IP, not 0.0.0.0/0
#   - opens 8000 (vLLM) to 0.0.0.0/0, since Cloud Run's outbound IPs are
#     dynamic and not practical to allowlist — this is why
#     02_setup_vllm.sh ALWAYS starts vLLM with --api-key. Anyone who
#     can reach the box still needs that key. If you want this
#     tighter, put the box behind a VPN / AWS PrivateLink / a
#     Cloud Run VPC connector with a private IP instead — out of
#     scope for this script, called out so it's a conscious choice,
#     not an accident.
#
# Usage:
#   chmod +x deploy/aws/*.sh
#   ./deploy/aws/01_launch_ec2.sh
#
# Requires: AWS CLI v2, configured credentials (`aws configure`),
# default region set (or pass AWS_REGION below).

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-g4dn.xlarge}"      # T4 GPU, ~$0.526/hr on-demand
VOLUME_SIZE_GB="${VOLUME_SIZE_GB:-100}"
KEY_NAME="${KEY_NAME:?Set KEY_NAME to an existing EC2 key pair name, e.g. KEY_NAME=my-keypair}"
SG_NAME="agentforge-vllm-sg"
INSTANCE_NAME="agentforge-vllm"

echo "==> Region: $AWS_REGION | Instance type: $INSTANCE_TYPE"

# ── Find the current Deep Learning AMI (GPU PyTorch) instead of a
#    hardcoded AMI ID, which goes stale within weeks ──────────────────
echo "==> Looking up latest Deep Learning AMI (PyTorch, GPU)…"
AMI_ID=$(aws ec2 describe-images \
  --region "$AWS_REGION" \
  --owners amazon \
  --filters \
    "Name=name,Values=Deep Learning AMI GPU PyTorch*Ubuntu*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

if [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]]; then
  echo "Could not find a Deep Learning AMI in $AWS_REGION. Check the AWS console" >&2
  echo "under EC2 -> AMI Catalog -> search 'Deep Learning AMI GPU PyTorch' and set:" >&2
  echo "  AMI_ID=ami-xxxxxxxx $0" >&2
  exit 1
fi
echo "    AMI: $AMI_ID"

# ── Security group: SSH locked to caller's IP, vLLM port open (API-key protected) ──
MY_IP=$(curl -s https://checkip.amazonaws.com)/32
echo "==> Your public IP for SSH allowlisting: $MY_IP"

VPC_ID=$(aws ec2 describe-vpcs --region "$AWS_REGION" \
  --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)

SG_ID=$(aws ec2 describe-security-groups --region "$AWS_REGION" \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
  echo "==> Creating security group $SG_NAME…"
  SG_ID=$(aws ec2 create-security-group --region "$AWS_REGION" \
    --group-name "$SG_NAME" --description "AgentForge vLLM server" --vpc-id "$VPC_ID" \
    --query 'GroupId' --output text)
  aws ec2 authorize-security-group-ingress --region "$AWS_REGION" \
    --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$MY_IP" >/dev/null
  aws ec2 authorize-security-group-ingress --region "$AWS_REGION" \
    --group-id "$SG_ID" --protocol tcp --port 8000 --cidr 0.0.0.0/0 >/dev/null
  echo "    Created $SG_ID"
else
  echo "==> Reusing existing security group $SG_ID"
fi

# ── Launch ─────────────────────────────────────────────────────────────
echo "==> Launching instance…"
INSTANCE_ID=$(aws ec2 run-instances --region "$AWS_REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":$VOLUME_SIZE_GB,\"VolumeType\":\"gp3\"}}]" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --query 'Instances[0].InstanceId' --output text)

echo "    Instance: $INSTANCE_ID — waiting for it to be running…"
aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"

PUBLIC_IP=$(aws ec2 describe-instances --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

cat <<EOF

✓ EC2 instance is up.
  Instance ID : $INSTANCE_ID
  Public IP   : $PUBLIC_IP
  Type        : $INSTANCE_TYPE ($(echo "$INSTANCE_TYPE" | grep -q g4dn && echo "~\$0.526/hr on-demand"))

Next steps:
  1. SSH in (give it ~60s to finish booting the Deep Learning AMI):
       ssh -i /path/to/${KEY_NAME}.pem ubuntu@$PUBLIC_IP
  2. Copy and run the vLLM setup script on the box:
       scp -i /path/to/${KEY_NAME}.pem deploy/aws/02_setup_vllm.sh ubuntu@$PUBLIC_IP:~
       ssh -i /path/to/${KEY_NAME}.pem ubuntu@$PUBLIC_IP 'chmod +x ~/02_setup_vllm.sh && VLLM_API_KEY=<choose-a-real-secret> ~/02_setup_vllm.sh'
  3. Put the result in your .env (see .env.example):
       VLLM_BASE_URL=http://$PUBLIC_IP:8000/v1
       VLLM_API_KEY=<the same secret you chose in step 2>

Remember to stop/terminate this instance when you're not using it —
g4dn.xlarge burns through the \$106 credit in well under a week if left
running 24/7. \`aws ec2 stop-instances --instance-ids $INSTANCE_ID\`
EOF
