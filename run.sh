#!/bin/bash

# Load environment variables from .env if it exists
if [ -f .env ]; then
  export $(echo $(grep -v '^#' .env | xargs))
fi

PORT=${PORT:-7873}

echo "=========================================================="
echo "🚀 DeepSeek OCR 2 Multi-Instance Startup"
echo "=========================================================="
echo "1. Run containerized with Nginx portal (Recommended):"
echo "   docker compose up -d --build"
echo "   Access Portal: http://localhost:$PORT"
echo "=========================================================="
echo "Starting instances locally in the background..."

# Activate virtualenv if available
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Cleanup function to kill all background processes on exit
cleanup() {
  echo ""
  echo "🛑 Stopping all local instances..."
  kill $(jobs -p) 2>/dev/null
  exit
}
trap cleanup EXIT INT TERM

# 1. Start DeepSeek-OCR-2-Demo (Core)
echo "→ Launching DeepSeek-OCR-2-Demo on port $PORT (Subpath: /v2)"
export GRADIO_SERVER_PORT=$PORT
export GRADIO_ROOT_PATH=/v2
(cd DeepSeek-OCR-2-Demo && python3 deepseek_ocr_v2_demo.py) &

# 2. Start DeepSeek-OCR-2-Demo-bao
PORT_BAO=$((PORT + 1))
echo "→ Launching DeepSeek-OCR-2-Demo-bao on port $PORT_BAO (Subpath: /v2-bao)"
export GRADIO_SERVER_PORT=$PORT_BAO
export GRADIO_ROOT_PATH=/v2-bao
(cd DeepSeek-OCR-2-Demo-bao && python3 app.py) &

# 3. Start DeepSeek-OCR-Demo
PORT_LEGACY=$((PORT + 2))
echo "→ Launching DeepSeek-OCR-Demo on port $PORT_LEGACY (Subpath: /v1)"
export GRADIO_SERVER_PORT=$PORT_LEGACY
export GRADIO_ROOT_PATH=/v1
(cd DeepSeek-OCR-Demo && python3 app.py) &

echo "=========================================================="
echo "Press Ctrl+C to stop all local instances."
echo "=========================================================="

# Wait for background jobs to finish
wait
