# Use developer CUDA image as builder to install packages
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install Python 3.10 and build dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download docker compose Go binary
RUN curl -SL https://github.com/docker/compose/releases/download/v2.29.2/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose

# Install uv for extremely fast package downloads
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv
ENV PATH="/uv/bin:${PATH}"

WORKDIR /app

# Install standard PyTorch and basic ML dependencies
RUN uv pip install --system \
    torch==2.8.0 \
    torchvision \
    gradio \
    PyMuPDF \
    accelerate \
    einops \
    addict \
    easydict \
    spaces \
    numpy \
    huggingface_hub \
    fastapi \
    uvicorn \
    jinja2

# Install flash-attention precompiled wheel for CUDA 12, PyTorch 2.8, and Python 3.10
RUN uv pip install --system "flash-attn @ https://huggingface.co/strangertoolshf/flash_attention_2_wheelhouse/resolve/main/wheelhouse-flash_attn-2.8.3/linux_x86_64/torch2.8/cu12/abiFALSE/cp310/flash_attn-2.8.3+cu12torch2.8cxx11abiFALSE-cp310-cp310-linux_x86_64.whl"

# Install specific huggingface library versions
RUN uv pip install --system "git+https://github.com/huggingface/transformers.git@v4.46.3" tokenizers==0.20.3

# --- Runtime Image ---
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.10/dist-packages /usr/local/lib/python3.10/dist-packages
COPY --from=builder /usr/bin/python3.10 /usr/bin/python3.10
RUN ln -sf /usr/bin/python3.10 /usr/bin/python3
COPY --from=builder /usr/local/bin/docker-compose /usr/local/bin/docker-compose

WORKDIR /app
