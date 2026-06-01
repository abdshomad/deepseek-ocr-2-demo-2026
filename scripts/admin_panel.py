import os
import subprocess
import socket
import json
import asyncio
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template
import uvicorn

app = FastAPI()

# Path to the workspace configuration files on host
WORKSPACE_PATH = "/workspace"

def check_auth(request: Request) -> bool:
    auth_token = request.cookies.get("auth_token")
    return auth_token == "demo-token"

def run_cmd(cmd, cwd=None):
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, cwd=cwd)
        return res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return "", str(e)

def get_process_name(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/comm", "r") as f:
            return f.read().strip()
    except Exception:
        try:
            res = subprocess.run(f"ps -p {pid} -o comm=", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
            return res.stdout.strip()
        except Exception:
            return ""

def make_human_readable_name(proc_name: str) -> str:
    proc_name_lower = proc_name.lower()
    if "rustdesk" in proc_name_lower:
        return "RustDesk Remote Desktop"
    if "xorg" in proc_name_lower:
        return "Xorg Graphics Server"
    if "vllm::enginecore" in proc_name_lower or "vllm" in proc_name_lower:
        return "vLLM Inference Server"
    if "python" in proc_name_lower:
        return "Python / Gradio App"
    try:
        base = os.path.basename(proc_name)
        if base:
            return base
    except Exception:
        pass
    return proc_name

def get_gpu_info():
    # Query GPUs info
    stdout, _ = run_cmd("nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free,uuid --format=csv,noheader,nounits")
    gpus = []
    if stdout:
        for line in stdout.split("\n"):
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 8:
                gpus.append({
                    "index": parts[0],
                    "name": parts[1],
                    "gpu_util": parts[2],
                    "mem_util": parts[3],
                    "mem_total": parts[4],
                    "mem_used": parts[5],
                    "mem_free": parts[6],
                    "uuid": parts[7],
                    "processes": []
                })
                
    # Query compute apps (processes) using GPUs
    stdout_apps, _ = run_cmd("nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader,nounits")
    if stdout_apps:
        for line in stdout_apps.split("\n"):
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpu_uuid, pid, proc_name, used_mem = parts[0], parts[1], parts[2], parts[3]
                # Find matching GPU
                for gpu in gpus:
                    if gpu["uuid"] == gpu_uuid:
                        gpu["processes"].append({
                            "pid": pid,
                            "name": proc_name,
                            "readable_name": make_human_readable_name(proc_name),
                            "used_mem": used_mem
                        })
    return gpus

def load_env_settings():
    env_file = os.path.join(WORKSPACE_PATH, ".env")
    settings = {
        "cuda_devices": "1",
        "admin_user": "admin",
        "admin_pass": "demo"
    }
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'").strip('"')
                    if k == "CUDA_VISIBLE_DEVICES":
                        settings["cuda_devices"] = v
                    elif k == "ADMIN_USER":
                        settings["admin_user"] = v
                    elif k == "ADMIN_PASS":
                        settings["admin_pass"] = v
    return settings

def save_env_settings(cuda_visible_devices):
    env_file = os.path.join(WORKSPACE_PATH, ".env")
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            lines = f.readlines()
            
    with open(env_file, "w") as f:
        found_cuda = False
        for line in lines:
            if line.startswith("CUDA_VISIBLE_DEVICES="):
                f.write(f"CUDA_VISIBLE_DEVICES={cuda_visible_devices}\n")
                found_cuda = True
            else:
                f.write(line)
        if not found_cuda:
            f.write(f"CUDA_VISIBLE_DEVICES={cuda_visible_devices}\n")

async def get_container_status(service_name: str) -> str:
    # Run docker-compose ps --format json or similar
    stdout, _ = run_cmd(f"docker-compose ps --format json {service_name}", cwd=WORKSPACE_PATH)
    if stdout:
        try:
            # Docker compose ps json output could be multiple lines or list
            if stdout.startswith("["):
                data = json.loads(stdout)
                if data:
                    return data[0].get("State", "Unknown")
            else:
                # Multiple JSON objects (JSON Lines)
                for line in stdout.split("\n"):
                    if line.strip():
                        data = json.loads(line)
                        return data.get("State", "Unknown")
        except Exception:
            pass
    # Fallback to simple ps check
    stdout, _ = run_cmd(f"docker-compose ps {service_name}", cwd=WORKSPACE_PATH)
    if service_name in stdout:
        if "Up" in stdout:
            return "running"
        if "Exit" in stdout:
            return "exited"
    return "stopped"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DeepSeek OCR GPU Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(15, 23, 42, 0.45);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --success: #10b981;
            --danger: #ef4444;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --accent-glow: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Plus Jakarta Sans', sans-serif;
            min-height: 100vh;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            position: relative;
            overflow-x: hidden;
        }

        .bg-blobs {
            position: absolute;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            z-index: 0;
            overflow: hidden;
            pointer-events: none;
        }

        .blob {
            position: absolute;
            border-radius: 50%;
            filter: blur(100px);
            opacity: 0.25;
        }

        .blob-1 {
            top: -10%;
            left: -10%;
            width: 45vw;
            height: 45vw;
            background: radial-gradient(circle, #4f46e5 0%, transparent 70%);
        }

        .blob-2 {
            bottom: -10%;
            right: -10%;
            width: 40vw;
            height: 40vw;
            background: radial-gradient(circle, #06b6d4 0%, transparent 70%);
        }

        .container {
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 1100px;
            background: var(--card-bg);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4), 
                        inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 24px;
            margin-bottom: 32px;
        }

        h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 32px;
            font-weight: 700;
            background: linear-gradient(135deg, #a5b4fc, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }

        h2 {
            font-family: 'Outfit', sans-serif;
            font-size: 22px;
            font-weight: 600;
            color: #a5b4fc;
            margin-bottom: 20px;
        }

        .section-card {
            background: rgba(15, 23, 42, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 32px;
        }

        .gpu-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 24px;
        }

        .gpu-card {
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 14px;
            padding: 20px;
        }

        .gpu-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
        }

        .gpu-name {
            font-size: 18px;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
        }

        .gpu-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }

        .metric-box {
            background: rgba(30, 41, 59, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 10px;
            padding: 14px;
            text-align: center;
        }

        .metric-label {
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .metric-value {
            font-size: 18px;
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
        }

        .progress-bar-container {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, var(--success), #34d399);
            border-radius: 3px;
        }

        .progress-bar.high {
            background: linear-gradient(90deg, #fbbf24, #f59e0b);
        }

        .progress-bar.critical {
            background: linear-gradient(90deg, var(--danger), #ef4444);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }

        th {
            color: var(--text-muted);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        td {
            font-size: 14px;
        }

        .btn {
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .btn:hover {
            opacity: 0.9;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
        }

        .btn-danger {
            background: var(--danger);
        }
        .btn-danger:hover {
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.25);
        }

        .btn-success {
            background: var(--success);
        }
        .btn-success:hover {
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
        }

        .btn-sm {
            padding: 6px 12px;
            font-size: 12px;
            border-radius: 6px;
        }

        .alert {
            padding: 14px 18px;
            border-radius: 10px;
            margin-bottom: 24px;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .alert-success {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: #34d399;
        }

        .alert-danger {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #f87171;
        }

        .checkbox-group {
            display: flex;
            gap: 15px;
            margin-top: 10px;
        }

        .checkbox-label {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            font-size: 14px;
        }

        .service-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px;
            background: rgba(30, 41, 59, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            margin-bottom: 12px;
        }

        .service-info {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .service-name {
            font-weight: 600;
            font-size: 16px;
        }

        .badge-status {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 4px 8px;
            border-radius: 6px;
        }

        .badge-running {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .badge-stopped {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .badge-restarting {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .spinner-small {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 0.8s linear infinite;
            vertical-align: middle;
            margin-right: 6px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .btn.disabled {
            opacity: 0.5;
            pointer-events: none;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
    </style>
</head>
<body>
    <div class="bg-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="container">
        <header>
            <h1>GPU Control Dashboard</h1>
            <div style="display: flex; gap: 12px;">
                <a href="/gpu" class="btn">Refresh</a>
                <a href="/logout" class="btn btn-danger">Logout</a>
            </div>
        </header>

        {% if msg %}
            <div class="alert alert-success">{{ msg }}</div>
        {% endif %}
        {% if err %}
            <div class="alert alert-danger">{{ err }}</div>
        {% endif %}

        <!-- Container Management Section -->
        <div class="section-card">
            <h2>DeepSeek OCR Services</h2>
            
            <div class="service-row" id="row-deepseek-ocr-2-demo">
                <div class="service-info">
                    <div>
                        <div class="service-name">deepseek-ocr-2-demo (Core)</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Runs on GPU {{ settings.cuda_devices }} | Path: /v2/</div>
                    </div>
                    <span id="badge-deepseek-ocr-2-demo" class="badge-status {% if status_v2 in ['running', 'running (healthy)', 'Up', 'up'] %}badge-running{% elif status_v2 in ['restarting', 'starting', 'stopping', 'recreated'] or 'ing' in status_v2 %}badge-restarting{% else %}badge-stopped{% endif %}">
                        {{ status_v2 }}
                    </span>
                </div>
                <div style="display: flex; gap: 8px;">
                    <a href="/gpu/container/restart/deepseek-ocr-2-demo" onclick="return handleAction(event, 'restart', 'deepseek-ocr-2-demo')" class="btn btn-success btn-sm btn-action">Restart</a>
                    <a href="/gpu/container/stop/deepseek-ocr-2-demo" onclick="return handleAction(event, 'stop', 'deepseek-ocr-2-demo')" class="btn btn-danger btn-sm btn-action">Stop</a>
                    <a href="/gpu/container/start/deepseek-ocr-2-demo" onclick="return handleAction(event, 'start', 'deepseek-ocr-2-demo')" class="btn btn-sm btn-action">Start</a>
                </div>
            </div>

            <div class="service-row" id="row-deepseek-ocr-2-demo-bao">
                <div class="service-info">
                    <div>
                        <div class="service-name">deepseek-ocr-2-demo-bao (Bao Edition)</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Runs on CPU | Path: /v2-bao/</div>
                    </div>
                    <span id="badge-deepseek-ocr-2-demo-bao" class="badge-status {% if status_bao in ['running', 'running (healthy)', 'Up', 'up'] %}badge-running{% elif status_bao in ['restarting', 'starting', 'stopping', 'recreated'] or 'ing' in status_bao %}badge-restarting{% else %}badge-stopped{% endif %}">
                        {{ status_bao }}
                    </span>
                </div>
                <div style="display: flex; gap: 8px;">
                    <a href="/gpu/container/restart/deepseek-ocr-2-demo-bao" onclick="return handleAction(event, 'restart', 'deepseek-ocr-2-demo-bao')" class="btn btn-success btn-sm btn-action">Restart</a>
                    <a href="/gpu/container/stop/deepseek-ocr-2-demo-bao" onclick="return handleAction(event, 'stop', 'deepseek-ocr-2-demo-bao')" class="btn btn-danger btn-sm btn-action">Stop</a>
                    <a href="/gpu/container/start/deepseek-ocr-2-demo-bao" onclick="return handleAction(event, 'start', 'deepseek-ocr-2-demo-bao')" class="btn btn-sm btn-action">Start</a>
                </div>
            </div>

            <div class="service-row" id="row-deepseek-ocr-demo">
                <div class="service-info">
                    <div>
                        <div class="service-name">deepseek-ocr-demo (Legacy/Standard)</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Runs on CPU | Path: /v1/</div>
                    </div>
                    <span id="badge-deepseek-ocr-demo" class="badge-status {% if status_v1 in ['running', 'running (healthy)', 'Up', 'up'] %}badge-running{% elif status_v1 in ['restarting', 'starting', 'stopping', 'recreated'] or 'ing' in status_v1 %}badge-restarting{% else %}badge-stopped{% endif %}">
                        {{ status_v1 }}
                    </span>
                </div>
                <div style="display: flex; gap: 8px;">
                    <a href="/gpu/container/restart/deepseek-ocr-demo" onclick="return handleAction(event, 'restart', 'deepseek-ocr-demo')" class="btn btn-success btn-sm btn-action">Restart</a>
                    <a href="/gpu/container/stop/deepseek-ocr-demo" onclick="return handleAction(event, 'stop', 'deepseek-ocr-demo')" class="btn btn-danger btn-sm btn-action">Stop</a>
                    <a href="/gpu/container/start/deepseek-ocr-demo" onclick="return handleAction(event, 'start', 'deepseek-ocr-demo')" class="btn btn-sm btn-action">Start</a>
                </div>
            </div>
        </div>

        <!-- GPU Assignment Settings -->
        <div class="section-card" style="border-color: rgba(99, 102, 241, 0.25);">
            <h2>GPU Assignment Settings</h2>
            <form action="/gpu/save-settings" method="post" onsubmit="return handleFormSubmit(event)">
                <div style="margin-bottom: 20px;">
                    <label style="font-size: 13px; color: var(--text-muted); text-transform: uppercase;">Core Service GPU Device Allocation</label>
                    <div class="checkbox-group">
                        {% for gpu in gpus %}
                            <label class="checkbox-label">
                                <input type="radio" name="cuda_device" value="{{ gpu.index }}" {% if settings.cuda_devices == gpu.index %}checked{% endif %}> GPU {{ gpu.index }} ({{ gpu.name }})
                            </label>
                        {% endfor %}
                    </div>
                </div>
                <button type="submit" id="btn-save-settings" class="btn btn-success">Apply Settings & Recreate Core Container</button>
            </form>
        </div>

        <!-- GPU Resources status -->
        <h2>System GPU Resources</h2>
        <div class="gpu-grid" style="margin-top: 16px;">
            {% if not gpus %}
                <p style="color: var(--text-muted);">No GPUs detected or nvidia-smi is unavailable.</p>
            {% else %}
                {% for gpu in gpus %}
                    <div class="gpu-card">
                        <div class="gpu-header">
                            <div class="gpu-name">[{{ gpu.index }}] {{ gpu.name }}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">UUID: {{ gpu.uuid }}</div>
                        </div>

                        <div class="gpu-metrics">
                            <div class="metric-box">
                                <div class="metric-label">GPU Utilization</div>
                                <div class="metric-value">{{ gpu.gpu_util }}%</div>
                                <div class="progress-bar-container">
                                    <div class="progress-bar {% if gpu.gpu_util|int > 85 %}critical{% elif gpu.gpu_util|int > 60 %}high{% endif %}" style="width: {{ gpu.gpu_util }}%"></div>
                                </div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">VRAM Usage</div>
                                <div class="metric-value">{{ gpu.mem_used }} / {{ gpu.mem_total }} MiB</div>
                                <div class="progress-bar-container">
                                    {% set usage_pct = (gpu.mem_used|float / gpu.mem_total|float * 100)|int %}
                                    <div class="progress-bar {% if usage_pct > 85 %}critical{% elif usage_pct > 60 %}high{% endif %}" style="width: {{ usage_pct }}%"></div>
                                </div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Free VRAM</div>
                                <div class="metric-value" style="color: var(--success)">{{ gpu.mem_free }} MiB</div>
                            </div>
                        </div>

                        <h3>Active GPU Processes</h3>
                        {% if not gpu.processes %}
                            <p style="font-size: 13px; color: var(--text-muted); margin-top: 10px;">No active processes found on this GPU.</p>
                        {% else %}
                            <table>
                                <thead>
                                    <tr>
                                        <th>PID</th>
                                        <th>Process Name</th>
                                        <th>VRAM Used</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for proc in gpu.processes %}
                                        <tr>
                                            <td><code>{{ proc.pid }}</code></td>
                                            <td>
                                                <div style="font-weight: 600; color: #a5b4fc;">{{ proc.readable_name }}</div>
                                                <div style="font-size: 11px; color: var(--text-muted); font-family: monospace;">{{ proc.name }}</div>
                                            </td>
                                            <td>{{ proc.used_mem }} MiB</td>
                                            <td>
                                                {% if "rustdesk" in proc.name.lower() or "rustdesk" in proc.readable_name.lower() %}
                                                    <span style="color: var(--text-muted); font-size: 12px; font-style: italic;">Protected</span>
                                                {% else %}
                                                    <a href="/gpu/kill/{{ proc.pid }}" class="btn btn-danger btn-sm" style="padding: 4px 10px; font-size: 12px;">Kill</a>
                                                {% endif %}
                                            </td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        {% endif %}
                    </div>
                {% endfor %}
            {% endif %}
        </div>
    </div>
    
    <script>
        function handleAction(event, action, service) {
            // Disable all buttons to prevent double-submits
            const allButtons = document.querySelectorAll('.btn-action, .btn');
            allButtons.forEach(btn => {
                btn.classList.add('disabled');
                btn.style.pointerEvents = 'none';
                btn.style.opacity = '0.5';
            });
            
            // Update the status badge for this service
            const badge = document.getElementById('badge-' + service);
            if (badge) {
                badge.className = 'badge-status badge-restarting';
                badge.innerHTML = '<span class="spinner-small"></span> ' + action + 'ing...';
            }
            
            // Update clicked button text & add spinner
            const clickedBtn = event.currentTarget;
            clickedBtn.innerHTML = '<span class="spinner-small"></span> ' + action.charAt(0).toUpperCase() + action.slice(1) + 'ing...';
            
            return true;
        }

        function handleFormSubmit(event) {
            const btn = document.getElementById('btn-save-settings');
            const badge = document.getElementById('badge-deepseek-ocr-2-demo');
            
            const allButtons = document.querySelectorAll('.btn-action, .btn');
            allButtons.forEach(b => {
                b.classList.add('disabled');
                b.style.pointerEvents = 'none';
                b.style.opacity = '0.5';
            });
            
            if (badge) {
                badge.className = 'badge-status badge-restarting';
                badge.innerHTML = '<span class="spinner-small"></span> recreating...';
            }
            
            if (btn) {
                btn.innerHTML = '<span class="spinner-small"></span> Recreating Core Container...';
            }
            
            return true;
        }

        document.addEventListener('DOMContentLoaded', () => {
            const alertMsg = document.querySelector('.alert-success');
            if (alertMsg) {
                const text = alertMsg.textContent || '';
                const match = text.match(/Command 'docker-compose (restart|stop|start) ([\w-]+)' completed successfully\./);
                if (match) {
                    const action = match[1];
                    const service = match[2];
                    
                    let stateWord = '';
                    if (action === 'restart') stateWord = 'restarted';
                    else if (action === 'start') stateWord = 'started';
                    else if (action === 'stop') stateWord = 'stopped';
                    
                    if (stateWord) {
                        const badge = document.getElementById('badge-' + service);
                        const row = document.getElementById('row-' + service);
                        if (badge) {
                            badge.textContent = stateWord;
                            if (stateWord === 'stopped') {
                                badge.className = 'badge-status badge-stopped';
                            } else {
                                badge.className = 'badge-status badge-running';
                            }
                            
                            if (row) {
                                row.style.transition = 'all 0.5s ease';
                                row.style.boxShadow = '0 0 20px rgba(99, 102, 241, 0.4)';
                                row.style.borderColor = 'rgba(99, 102, 241, 0.6)';
                                setTimeout(() => {
                                    row.style.boxShadow = '';
                                    row.style.borderColor = '';
                                    badge.textContent = (stateWord === 'stopped') ? 'stopped' : 'running';
                                }, 4000);
                            }
                        }
                    }
                }
                
                const recreateMatch = text.match(/Core container recreated on GPU (\d+)\./);
                if (recreateMatch) {
                    const service = 'deepseek-ocr-2-demo';
                    const badge = document.getElementById('badge-' + service);
                    const row = document.getElementById('row-' + service);
                    if (badge) {
                        badge.textContent = 'recreated';
                        badge.className = 'badge-status badge-running';
                        if (row) {
                            row.style.transition = 'all 0.5s ease';
                            row.style.boxShadow = '0 0 20px rgba(99, 102, 241, 0.4)';
                            row.style.borderColor = 'rgba(99, 102, 241, 0.6)';
                            setTimeout(() => {
                                row.style.boxShadow = '';
                                row.style.borderColor = '';
                                badge.textContent = 'running';
                            }, 4000);
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

LOGIN_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPU Dashboard Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(15, 23, 42, 0.45);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --primary-glow: rgba(99, 102, 241, 0.25);
            --danger: #f87171;
            --danger-bg: rgba(248, 113, 113, 0.1);
            --danger-border: rgba(248, 113, 113, 0.2);
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Plus Jakarta Sans', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            position: relative;
            overflow: hidden;
        }

        .bg-blobs {
            position: absolute;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            z-index: 0;
            overflow: hidden;
            pointer-events: none;
        }

        .blob {
            position: absolute;
            border-radius: 50%;
            filter: blur(100px);
            opacity: 0.35;
        }

        .blob-1 {
            top: -10%;
            left: -10%;
            width: 50vw;
            height: 50vw;
            background: radial-gradient(circle, #4f46e5 0%, transparent 70%);
        }

        .blob-2 {
            bottom: -10%;
            right: -10%;
            width: 45vw;
            height: 45vw;
            background: radial-gradient(circle, #06b6d4 0%, transparent 70%);
        }

        .login-card {
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 420px;
            background: var(--card-bg);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 48px 40px;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4), 
                        inset 0 1px 0 rgba(255, 255, 255, 0.1);
            text-align: center;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.2);
            color: #a5b4fc;
            padding: 6px 14px;
            border-radius: 99px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 24px;
        }

        .pulse-dot {
            width: 6px;
            height: 6px;
            background-color: #818cf8;
            border-radius: 50%;
            box-shadow: 0 0 8px #818cf8;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(129, 140, 248, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(129, 140, 248, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(129, 140, 248, 0); }
        }

        h2 {
            font-family: 'Outfit', sans-serif;
            margin: 0 0 8px 0;
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #f8fafc, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }

        .subtitle {
            color: var(--text-muted);
            font-size: 14px;
            margin-bottom: 36px;
            line-height: 1.5;
        }

        .form-group {
            margin-bottom: 24px;
            text-align: left;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        input {
            width: 100%;
            box-sizing: border-box;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: white;
            padding: 14px 16px;
            border-radius: 12px;
            font-size: 15px;
            font-family: inherit;
            transition: all 0.3s;
        }

        input:focus {
            outline: none;
            border-color: var(--primary);
            background: rgba(15, 23, 42, 0.8);
            box-shadow: 0 0 0 4px var(--primary-glow);
        }

        .btn {
            width: 100%;
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 4px 20px rgba(99, 102, 241, 0.25);
            margin-top: 12px;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(99, 102, 241, 0.4);
            background: linear-gradient(135deg, #818cf8, #4f46e5);
        }

        .alert {
            background: var(--danger-bg);
            border: 1px solid var(--danger-border);
            color: var(--danger);
            padding: 12px 16px;
            border-radius: 12px;
            font-size: 14px;
            margin-bottom: 24px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="bg-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>

    <div class="login-card">
        <div class="badge">
            <span class="pulse-dot"></span>
            GPU Control Panel
        </div>
        <h2>Welcome Back</h2>
        <p class="subtitle">Secure administrative interface to monitor status & allocate VRAM settings</p>
        
        {% if err %}
            <div class="alert">
                <span>{{ err }}</span>
            </div>
        {% endif %}
        
        <form action="/login" method="post">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autocomplete="username">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>
            <button type="submit" class="btn">Sign In</button>
        </form>
    </div>
</body>
</html>
"""

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, err: str = None):
    template = Template(LOGIN_HTML_TEMPLATE)
    return template.render(err=err)

@app.post("/login")
async def login_post(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    
    settings = load_env_settings()
    correct_username = settings.get("admin_user", "admin")
    correct_password = settings.get("admin_pass", "demo")
    
    if username == correct_username and password == correct_password:
        response = RedirectResponse("/gpu", status_code=303)
        response.set_cookie(key="auth_token", value="demo-token", httponly=True, max_age=86400)
        return response
    else:
        return RedirectResponse("/login?err=Invalid username or password", status_code=303)

@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(key="auth_token")
    return response

@app.get("/gpu", response_class=HTMLResponse)
async def admin_index(request: Request, msg: str = None, err: str = None):
    if not check_auth(request):
        return RedirectResponse("/login", status_code=303)
    
    gpus = get_gpu_info()
    settings = load_env_settings()
    
    # Get container status for each service
    status_v2 = await get_container_status("deepseek-ocr-2-demo")
    status_bao = await get_container_status("deepseek-ocr-2-demo-bao")
    status_v1 = await get_container_status("deepseek-ocr-demo")
    
    template = Template(HTML_TEMPLATE)
    return template.render(
        gpus=gpus, 
        settings=settings, 
        status_v2=status_v2, 
        status_bao=status_bao, 
        status_v1=status_v1, 
        msg=msg, 
        err=err
    )

@app.get("/gpu/kill/{pid}")
async def kill_pid(pid: int, request: Request):
    if not check_auth(request):
        return RedirectResponse("/login", status_code=303)
        
    proc_name = get_process_name(pid)
    # Protect important processes from being killed
    proc_name_lower = proc_name.lower()
    protected_keywords = ["rustdesk", "xorg", "nginx", "systemd", "dockerd", "python3"]
    if any(k in proc_name_lower for k in protected_keywords):
        return RedirectResponse(f"/gpu?err=Operation Denied: Process {pid} ({proc_name}) is protected and cannot be killed.", status_code=303)
    
    stdout, stderr = run_cmd(f"kill -9 {pid}")
    if stderr:
        return RedirectResponse(f"/gpu?err=Failed to kill process {pid}: {stderr}", status_code=303)
    return RedirectResponse(f"/gpu?msg=Successfully killed process {pid}", status_code=303)

@app.get("/gpu/container/{action}/{service}")
async def manage_container(action: str, service: str, request: Request):
    if not check_auth(request):
        return RedirectResponse("/login", status_code=303)
        
    valid_actions = ["start", "stop", "restart"]
    valid_services = ["deepseek-ocr-2-demo", "deepseek-ocr-2-demo-bao", "deepseek-ocr-demo"]
    
    if action not in valid_actions or service not in valid_services:
        return RedirectResponse("/gpu?err=Invalid container action or service name.", status_code=303)
        
    stdout, stderr = run_cmd(f"docker-compose {action} {service}", cwd=WORKSPACE_PATH)
    if stderr and "Error" in stderr:
        return RedirectResponse(f"/gpu?err=Failed to {action} {service}: {stderr}", status_code=303)
        
    return RedirectResponse(f"/gpu?msg=Command 'docker-compose {action} {service}' completed successfully.", status_code=303)

@app.post("/gpu/save-settings")
async def save_settings(request: Request):
    if not check_auth(request):
        return RedirectResponse("/login", status_code=303)
        
    form = await request.form()
    cuda_device = form.get("cuda_device", "1").strip()
    
    # Save the setting to .env file
    save_env_settings(cuda_device)
    
    # Recreate the Core GPU container to pick up the new env settings
    # docker-compose up -d --no-deps --force-recreate deepseek-ocr-2-demo
    stdout, stderr = run_cmd("docker-compose up -d --no-deps --force-recreate deepseek-ocr-2-demo", cwd=WORKSPACE_PATH)
    
    if stderr and "Error" in stderr:
        return RedirectResponse(f"/gpu?err=Failed to recreate core service: {stderr}", status_code=303)
        
    return RedirectResponse(f"/gpu?msg=GPU settings updated dynamically. Core container recreated on GPU {cuda_device}.", status_code=303)

if __name__ == "__main__":
    host = os.environ.get("PIPELINE_HOST", "0.0.0.0")
    port = int(os.environ.get("PIPELINE_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
