# DeepSeek OCR 2 Online Demo Deployment

This repository manages the deployment of the [DeepSeek-OCR-2](https://huggingface.co/spaces/prithivMLmods/DeepSeek-OCR-2-Demo) online demo using Hugging Face Spaces submodules.

## Project Structure

This project acts as a parent container coordinating multiple submodules:
*   [DeepSeek-OCR-2-Demo](./DeepSeek-OCR-2-Demo) - Active submodule hosting the main Gradio application (`deepseek_ocr_v2_demo.py`) utilizing `deepseek-ai/DeepSeek-OCR-2` for document conversion to Markdown, Free OCR, parsing figures, and drawing bounding boxes.
*   [paddle-ocr-1-6-demo](./paddle-ocr-1-6-demo) - Legacy/reference submodule representing the PaddleOCR VL 1.6 Online Demo.
*   [DeepSeek-OCR-Demo](./DeepSeek-OCR-Demo) - Reference space for standard DeepSeek OCR.
*   [DeepSeek-OCR-2-Demo-bao](./DeepSeek-OCR-2-Demo-bao) - Alternative DeepSeek OCR 2 space.
*   [AGENTS.md](./AGENTS.md) - Agent guidelines and policy references.
*   [.gitmodules](./.gitmodules) - Git submodule tracking.
*   [install.sh](./install.sh) - Local setup script (uses `uv`).
*   [run.sh](./run.sh) - Local runtime script.
*   [.env](./.env) - Local port/environment configuration (gitignored).

## Prerequisites

- **NVIDIA GPU** with CUDA support.
- Python 3.10+ (for local dependency compatibility with torch/flash-attn).
- [uv](https://github.com/astral-sh/uv) (recommended Python package installer).

## Getting Started

### 1. Configure the Environment
Create or edit the [.env](./.env) file in the root directory to set the desired port:
```env
PORT=7873
```

### 2. Initialize Submodules
To initialize and fetch the submodule folders, run:
```bash
git submodule update --init --recursive
```

### 3. Install Dependencies
Set up the virtual environment and install the required packages:
```bash
./install.sh
```

### 4. Run the Gradio App
Start the app:
```bash
./run.sh
```