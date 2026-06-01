# Issue: 502 Bad Gateway on `/v1/` and `/v2/` Endpoints

## Symptoms
When accessing `http://localhost:7873/v2/` or `http://localhost:7873/v1/`, Nginx returned a `502 Bad Gateway` error page. The corresponding container status checks showed that `deepseek-ocr-2-demo` and `deepseek-ocr-demo` were continuously restarting.

## Root Cause
The host environment has two NVIDIA L40 GPUs, but they are heavily pre-occupied by other active processes (such as `vLLM` instances). At the time of execution:
- **GPU 0** had only ~4.09 GB VRAM free.
- **GPU 1** had only ~9.8 GB VRAM free.

Loading a single instance of `deepseek-ai/DeepSeek-OCR-2` in `bfloat16` precision requires approximately **7.1 GB VRAM**.
1. When `deepseek-ocr-2-demo-bao` started, it claimed ~7.1 GB VRAM on GPU 1, leaving only ~2.7 GB.
2. When `deepseek-ocr-2-demo` tried to start on GPU 1, it crashed due to CUDA Out of Memory (OOM).
3. Similarly, when `deepseek-ocr-demo` tried to start on GPU 0, it also crashed due to CUDA OOM because GPU 0 only had ~4.09 GB free.
4. As a result, both containers entered a crash loop, leading to Nginx returning a `502 Bad Gateway` for `/v2/` and `/v1/`.

## Solution
To allow all three demos to run concurrently under tight GPU constraints, the standard demo (`deepseek-ocr-demo`) and the Bao edition (`deepseek-ocr-2-demo-bao`) were migrated to CPU. The main core demo (`deepseek-ocr-2-demo`) remains on GPU 1.

The CPU migration was implemented entirely at the repository boundary via environment configuration and runtime monkey-patching in [docker-compose.yml](../docker-compose.yml) to adhere to the submodule git policy (submodules must not be modified):
1. **Remove GPU Reservations**: Removed the `deploy.resources.reservations.devices` block from CPU-mapped services so Docker does not allocate GPU resources.
2. **Environment Variable**: Set `CUDA_VISIBLE_DEVICES=""`.
3. **Mock spaces**: The Hugging Face `spaces` library (specifically `@spaces.GPU`) checks for GPU availability. A mock `spaces` module is injected into `sys.modules` to make the GPU decorator a no-op:
   ```python
   import sys, types
   mock_spaces = types.ModuleType('spaces')
   mock_spaces.GPU = lambda *args, **kwargs: (lambda f: f)
   sys.modules['spaces'] = mock_spaces
   ```
4. **Mock PyTorch CUDA checks**: Patched `torch.cuda.is_available` to return `False` and intercepted `.cuda()` and `.to("cuda")` calls to redirect tensor/module allocation to the CPU.
5. **Flash Attention Fallback**: CPU does not support Flash Attention. Patched `transformers.AutoModel.from_pretrained` to override `_attn_implementation` to `"eager"`.
6. **Data Type**: Maintained `torch.bfloat16` to keep CPU memory footprint optimized (~14 GB per instance).

With these optimizations, all three services started successfully and run concurrently.
- `/v1/` (CPU) -> http://localhost:7873/v1/
- `/v2/` (GPU 1) -> http://localhost:7873/v2/
- `/v2-bao/` (CPU) -> http://localhost:7873/v2-bao/
