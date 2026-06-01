#!/bin/bash

# Initialize uv virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment .venv..."
  uv venv .venv
fi

echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate

# Install dependencies for all three spaces
echo "Installing dependencies for DeepSeek-OCR-2-Demo..."
uv pip install -r DeepSeek-OCR-2-Demo/requirements.txt

echo "Installing dependencies for DeepSeek-OCR-2-Demo-bao..."
uv pip install -r DeepSeek-OCR-2-Demo-bao/requirements.txt

echo "Installing dependencies for DeepSeek-OCR-Demo..."
uv pip install -r DeepSeek-OCR-Demo/requirements.txt

echo "All dependencies successfully installed!"
