#!/usr/bin/env python3
"""
child_agent.py — Fractal Claws child agent.

Usage:
    python agent/child_agent.py <ticket_path>

Tools available to the model:
  read_file   <path>
  write_file  <path> / CONTENT: ... / END
  exec_python <path>

Hardware logging (AMD Ryzen AI MAX+ / Strix Halo):
  hw_snapshot() captures:
    - RAM / CPU via psutil
    - GPU utilization via Windows WMI (AMD Radeon 8060S unified memory)
    - NPU utilization via WMI compute counters
    - Loaded model list via Lemonade /api/v1/models
  Snapshots taken before + after model call. Delta written to result log.

Safety: exec_python is restricted to the output/ directory.
"""
import sys
import os
import re
import time
import subprocess
import yaml
from openai import OpenAI

MODEL    = "Qwen3.5-4B-GGUF"
ENDPOINT = "http://localhost:8000/api/v1"
API_KEY  = "x"
EXEC_DIR = "output"

client = OpenAI(base_url=ENDPOINT, api_key=API_KEY)


# ────────────────────────────── hardware snapshot
def _wmi_gpu_npu() -> dict:
    """
    Query Windows WMI for GPU + NPU utilization.
    Works on AMD Radeon / XDNA2 NPU without ROCm or nvidia-smi.
    Returns dict: gpu_util_pct, gpu_dedicated_mb, gpu_shared_mb,
                  npu_util_pct  (None if unavailable)
    """
    result = {"gpu_util_pct": None, "gpu_dedicated_mb": None,
              "gpu_shared_mb": None, "npu_util_pct": None,
              "gpu_name": None}
    try:
        import wmi
        w = wmi.WMI(namespace="root\\cimv2")

        # GPU via Win32_VideoController
        for gpu in w.Win32_VideoController():
            result["gpu_name"]         = gpu.Name
            result["gpu_dedicated_mb"] = round(int(gpu.AdapterRAM or 0) / 1024**2, 1) if gpu.AdapterRAM else None
            break  # first GPU only

        # GPU utilization via perf counters
        try:
            w2 = wmi.WMI(namespace="root\\cimv2")
            for item in w2.query("SELECT * FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine"):
                name = getattr(item, "Name", "") or ""
                if "3D" in name or "Compute" in name:
                    val = getattr(item, "UtilizationPercentage", None)
                    if val is not None:
                        result["gpu_util_pct"] = int(val)
                        break
        except Exception:
            pass

        # NPU via Win32_PerfFormattedData - look for NPU/compute accelerator
        try:
            for item in w2.query("SELECT * FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine"):
                name = getattr(item, "Name", "") or ""
                if "NPU" in name.upper() or "VPU" in name.upper() or "COMPUTE" in name.upper():
                    val = getattr(item, "UtilizationPercentage", None)
                    if val is not None:
                        result["npu_util_pct"] = int(val)
                        break
        except Exception:
            pass

    except Exception:
        pass  # wmi not installed or query failed
    return result


def _lemonade_models() -> list:
    """Query Lemonade /api/v1/models — returns list of loaded model IDs."""
    try:
        import urllib.request, json
        req = urllib.request.urlopen(f"{ENDPOINT}/models", timeout=2)
        data = json.loads(req.read())
        return [m["id"] for m in data.get("data", [])]
    except Exception:
        return []


def hw_snapshot() -> dict:
    """
    Full hardware snapshot for AMD Ryzen AI MAX+ / Strix Halo.
    """
    snap = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # — RAM + CPU
    try:
        import psutil
        vm = psutil.virtual_memory()
        snap["ram_used_gb"]  = round(vm.used  / 1024**3, 2)
        snap["ram_total_gb"] = round(vm.total / 1024**3, 2)
        snap["cpu_pct"]      = psutil.cpu_percent(interval=0.2)
    except ImportError:
        snap["ram_used_gb"] = snap["ram_total_gb"] = snap["cpu_pct"] = None

    # — GPU + NPU via WMI
    wmi_data = _wmi_gpu_npu()
    snap.update(wmi_data)

    # — Lemonade loaded models
    snap["lemonade_models"] = _lemonade_models()

    return snap


def format_snapshot(label: str, s: dict) -> str:
    lines = [f"[hw:{label}] ts={s['ts']}"]
    if s.get("ram_used_gb") is not None:
        lines.append(f"[hw:{label}] RAM {s['ram_used_gb']} / {s['ram_total_gb']} GB  CPU {s['cpu_pct']}%")
    else:
        lines.append(f"[hw:{label}] RAM unavailable (psutil not installed)")

    gpu_name = s.get("gpu_name") or "unknown"
    gpu_util = s.get("gpu_util_pct")
    gpu_ded  = s.get("gpu_dedicated_mb")
    if gpu_util is not None:
        lines.append(f"[hw:{label}] GPU '{gpu_name}'  util={gpu_util}%  dedicated={gpu_ded} MB")
    else:
        lines.append(f"[hw:{label}] GPU '{gpu_name}'  util=unavailable (wmi query failed)")

    npu_util = s.get("npu_util_pct")
    if npu_util is not None:
        lines.append(f"[hw:{label}] NPU util={npu_util}%")
    else:
        lines.append(f"[hw:{label}] NPU util=unavailable")

    models = s.get("lemonade_models") or []
    lines.append(f"[hw:{label}] Lemonade loaded={models if models else 'none/unreachable'}")

    return "\n".join(lines)


def format_delta(pre: dict, post: dict, elapsed_s: float, tokens: int) -> str:
    lines = [f"[hw:delta] elapsed={elapsed_s:.2f}s  tokens={tokens}"]
    if pre.get("ram_used_gb") is not None and post.get("ram_used_gb") is not None:
        lines.append(f"[hw:delta] RAM delta={round(post['ram_used_gb'] - pre['ram_used_gb'], 2):+.2f} GB")
    if pre.get("gpu_util_pct") is not None and post.get("gpu_util_pct") is not None:
        lines.append(f"[hw:delta] GPU util {pre['gpu_util_pct']}% -> {post['gpu_util_pct']}%")
    if pre.get("npu_util_pct") is not None and post.get("npu_util_pct") is not None:
        lines.append(f"[hw:delta] NPU util {pre['npu_util_pct']}% -> {post['npu_util_pct']}%")
    if tokens and elapsed_s > 0:
        lines.append(f"[hw:delta] throughput={round(tokens / elapsed_s, 1)} tok/s")
    return "\n".join(lines)


# ────────────────────────────── ticket helpers
def load_ticket(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    if len(docs) == 2:
        merged = docs[0] or {}
        merged.update(docs[1] or {})
        return merged
    return docs[0]


def save_ticket(path: str, ticket: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(ticket, f, allow_unicode=True, sort_keys=False)


# ────────────────────────────── tools
def tool_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"ERROR: file not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def tool_write_file(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"OK: wrote {len(content)} bytes to {path}"


def tool_exec_python(path: str, timeout: int = 30) -> str:
    abs_path = os.path.abspath(path)
    abs_exec = os.path.abspath(EXEC_DIR)
    if not abs_path.startswith(abs_exec):
        return f"ERROR: exec_python blocked — path must be inside {EXEC_DIR}/ (got {path})"
    if not os.path.exists(abs_path):
        return f"ERROR: file not found: {path}"
    try:
        result = subprocess.run(
            [sys.executable, abs_path],
            capture_output=True, text=True, timeout=timeout
        )
        lines = []
        if result.stdout.strip():
            lines.append(f"STDOUT:\n{result.stdout.strip()}")
        if result.stderr.strip():
            lines.append(f"STDERR:\n{result.stderr.strip()}")
        lines.append(f"returncode: {result.returncode}")
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return f"ERROR: exec_python timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: exec_python failed: {e}"


# ────────────────────────────── parser
def normalise(text: str) -> str:
    return "\n".join(line.lstrip() for line in text.splitlines())


BLOCK_RE = re.compile(
    r'TOOL:\s*(\S+)\s*\nPATH:\s*(\S+)\s*\n(?:CONTENT:\n([\s\S]*?)\nEND|END)',
    re.MULTILINE
)


def parse_and_run_tools(response_text: str, exec_timeout: int = 30) -> list:
    normalised = normalise(response_text)
    results = []
    for match in BLOCK_RE.finditer(normalised):
        tool    = match.group(1).strip()
        path    = match.group(2).strip()
        content = match.group(3)
        print(f"[child] tool: {tool}  path: {path}")
        if tool == "read_file":
            result = tool_read_file(path)
        elif tool == "write_file":
            result = tool_write_file(path, content or "")
        elif tool == "exec_python":
            result = tool_exec_python(path, timeout=exec_timeout)
        else:
            result = f"ERROR: unknown tool: {tool}"
        print(f"[child] result: {result[:120]}")
        results.append((tool, path, result))
    return results


# ────────────────────────────── prompt
TOOL_SYNTAX = """\
You are a tool-calling agent. Output ONLY raw tool blocks — no prose, no markdown, no indentation.

Available tools:

TOOL: read_file
PATH: <path>
END

TOOL: write_file
PATH: <path>
CONTENT:
<file content>
END

TOOL: exec_python
PATH: <path>
END

Rules:
1. Start your response with the first TOOL: line. No words before it.
2. No indentation. Every line starts at column 0.
3. exec_python paths must be inside output/
4. After the last tool block write: DONE
"""


def build_context(ticket: dict) -> str:
    parts = []
    for cf in ticket.get("context_files", []):
        parts.append(f"--- {cf} ---\n{tool_read_file(cf)}")
    return "\n\n".join(parts)


def build_user_prompt(ticket: dict, context: str) -> str:
    prompt = TOOL_SYNTAX
    prompt += f"\nTask: {ticket['task']}"
    if context.strip():
        prompt += f"\n\nContext:\n{context}"
    return prompt


# ────────────────────────────── main
def main():
    if len(sys.argv) < 2:
        print("Usage: python agent/child_agent.py <ticket_path>")
        sys.exit(1)

    ticket_path = sys.argv[1]
    if not os.path.exists(ticket_path):
        print(f"ERROR: ticket not found: {ticket_path}")
        sys.exit(1)

    ticket    = load_ticket(ticket_path)
    ticket_id = ticket.get("ticket_id", os.path.basename(ticket_path))
    print(f"[child] loaded ticket: {ticket_id}")

    dest_dir = "tickets/closed"
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(ticket_path))

    context     = build_context(ticket)
    user_prompt = build_user_prompt(ticket, context)
    system_msg  = "Output ONLY raw tool blocks starting at column 0. No markdown. No prose. No indentation."

    # ── hardware snapshot BEFORE
    hw_pre = hw_snapshot()
    print(format_snapshot("pre", hw_pre))

    print(f"[child] calling model: {MODEL}")
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=ticket.get("max_tokens", 1024),
        temperature=0.1,
        timeout=ticket.get("timeout_seconds", 120),
    )
    elapsed = round(time.perf_counter() - t0, 2)

    # ── hardware snapshot AFTER
    hw_post = hw_snapshot()
    print(format_snapshot("post", hw_post))

    raw  = response.choices[0].message.content or ""
    used = response.usage.total_tokens if response.usage else 0
    why  = response.choices[0].finish_reason
    print(f"[child] responded ({used} tokens, finish={why}, elapsed={elapsed}s)")
    print(format_delta(hw_pre, hw_post, elapsed, used))
    print(f"[child] raw:\n{raw[:800]}")

    os.makedirs(EXEC_DIR, exist_ok=True)
    tool_results = parse_and_run_tools(raw, exec_timeout=ticket.get("timeout_seconds", 30))

    result_path = ticket.get("result_path", "logs/result.txt")
    os.makedirs(os.path.dirname(result_path) if os.path.dirname(result_path) else ".", exist_ok=True)

    summary_lines = [
        f"ticket: {ticket_id}",
        f"finish: {why}",
        f"tokens: {used}",
        f"elapsed_s: {elapsed}",
        "",
        "=== hardware ===",
        format_snapshot("pre",  hw_pre),
        format_snapshot("post", hw_post),
        format_delta(hw_pre, hw_post, elapsed, used),
        "",
        "=== tool results ===",
    ]

    if tool_results:
        for tool, path, result in tool_results:
            summary_lines.append(f"[{tool}] {path}")
            summary_lines.append(result)
            summary_lines.append("")
    else:
        summary_lines.append("no tool calls detected")
        summary_lines.append("")
        summary_lines.append("raw response:")
        summary_lines.append(raw)

    with open(result_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    print(f"[child] wrote: {result_path}")

    os.replace(ticket_path, dest)
    ticket["status"]     = "closed"
    ticket["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_ticket(dest, ticket)
    print(f"[child] closed: {dest}")
    print(f"[child] done")


if __name__ == "__main__":
    main()
