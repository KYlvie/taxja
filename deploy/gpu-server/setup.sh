#!/bin/bash
# =============================================================================
# Taxja LLM Server Setup Script
# Target: Hetzner Dedicated Server with RTX 4090 (Ubuntu 22.04)
# Model: Qwen2.5-7B-Instruct via vLLM
# =============================================================================
set -euo pipefail

echo "========================================="
echo "  Taxja LLM Server Setup"
echo "========================================="

# --- Configuration ---
# Qwen2.5-32B-Instruct-AWQ: 32B model quantized to 4bit (~20GB VRAM)
# Much better quality than 7B, fits on RTX 4090 24GB
# Alternative: Qwen/Qwen2.5-7B-Instruct (faster, lower quality)
MODEL="Qwen/Qwen2.5-32B-Instruct-AWQ"
API_KEY="${TAXJA_LLM_API_KEY:-changeme-$(openssl rand -hex 16)}"
PORT=8080
MAX_MODEL_LEN=4096
GPU_MEMORY_UTILIZATION=0.92
QUANTIZATION=awq

# --- 1. System Updates ---
echo "[1/6] Updating system..."
apt-get update && apt-get upgrade -y
apt-get install -y curl wget git build-essential software-properties-common \
    python3-pip python3-venv ufw

# --- 2. Install NVIDIA Drivers ---
echo "[2/6] Installing NVIDIA drivers..."
if ! command -v nvidia-smi &> /dev/null; then
    apt-get install -y linux-headers-$(uname -r)
    # Add NVIDIA repo
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
    dpkg -i cuda-keyring_1.1-1_all.deb
    apt-get update
    apt-get install -y cuda-drivers cuda-toolkit-12-4
    echo "NVIDIA drivers installed. Reboot required."
    echo "After reboot, run this script again."
    echo "API_KEY=$API_KEY" > /root/.taxja_llm_config
    exit 0
else
    echo "NVIDIA drivers already installed:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi

# --- 3. Install vLLM ---
echo "[3/6] Installing vLLM..."
pip3 install --upgrade pip
pip3 install vllm

# --- 4. Download Model ---
echo "[4/6] Downloading model: $MODEL ..."
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$MODEL')"

# --- 5. Configure Firewall ---
echo "[5/6] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow $PORT/tcp comment "vLLM API"
ufw --force enable

# --- 6. Create systemd service ---
echo "[6/6] Creating systemd service..."
cat > /etc/systemd/system/taxja-llm.service << EOF
[Unit]
Description=Taxja LLM Server (vLLM + $MODEL)
After=network.target

[Service]
Type=simple
User=root
Environment=CUDA_VISIBLE_DEVICES=0
ExecStart=/usr/local/bin/vllm serve $MODEL \
    --host 0.0.0.0 \
    --port $PORT \
    --api-key $API_KEY \
    --max-model-len $MAX_MODEL_LEN \
    --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
    --quantization $QUANTIZATION \
    --dtype auto \
    --enforce-eager
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable taxja-llm
systemctl start taxja-llm

# Wait for startup
echo "Waiting for vLLM to start (loading model into GPU)..."
for i in $(seq 1 60); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/health | grep -q "200"; then
        echo "vLLM is ready!"
        break
    fi
    echo "  Waiting... ($i/60)"
    sleep 5
done

# --- Done ---
echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "  Model:    $MODEL"
echo "  Endpoint: http://$(hostname -I | awk '{print $1}'):$PORT/v1"
echo "  API Key:  $API_KEY"
echo ""
echo "  Test with:"
echo "  curl http://localhost:$PORT/v1/chat/completions \\"
echo "    -H 'Authorization: Bearer $API_KEY' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"model\": \"$MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"Was ist Pendlerpauschale?\"}]}'"
echo ""
echo "  Add to Taxja backend/.env:"
echo "  GPT_OSS_ENABLED=true"
echo "  GPT_OSS_BASE_URL=http://$(hostname -I | awk '{print $1}'):$PORT/v1"
echo "  GPT_OSS_MODEL=$MODEL"
echo "  GPT_OSS_API_KEY=$API_KEY"
echo ""
echo "  Save this API key! -> $API_KEY"
echo "========================================="
