#!/usr/bin/env bash
# Serve the study backend: vLLM (base + 3 organism LoRAs) + Flask, inside ONE leased GPU
# job so the stack lives and dies together. Public access goes through YOUR LAPTOP
# (relay.sh): the cluster's only way out is an HTTP proxy that allows port 443 only, which
# Cloudflare tunnels (port 7844, no proxy support) cannot use.
#
#   bash serve.sh            # lease a pool GPU, start everything, print the node
#   bash serve.sh --inner    # (what runs on the GPU node; don't call directly)
#
# Then on the laptop: ./relay.sh  (reads serve_logs/endpoint.txt over ssh).
# Run detached:  setsid nohup bash serve.sh > serve_logs/serve.out 2>&1 &
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$HERE/serve_logs"; mkdir -p "$LOGS"
VLLM="${VLLM:-$HERE/../spurious_detect/agent_audit/auditor/.venv/bin/vllm}"
PY="${PY:-/projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python}"
FLASK_PORT="${FLASK_PORT:-5000}"

if [[ "${1:-}" != "--inner" ]]; then
  # Pool pinned to the d3204 tunnel jobs (user directive); override with GPU_POOL_JOBIDS.
  export GPU_POOL_JOBIDS="${GPU_POOL_JOBIDS:-$(squeue -u "$USER" -h -o '%i %N %j' \
    | awk '$3=="tunnel" && $2=="d3204"{print $1}' | tr '\n' ' ')}"
  echo "[serve] leasing a GPU from jobs: $GPU_POOL_JOBIDS"
  SLURM_CPU_BIND=none GPU_RUN_VERBOSE=1 GPU_PROBE_TIMEOUT=120 GPU_BAD_TTL=30 \
    "${GPU_RUN:-$HOME/.claude/gpu/gpu_run.sh}" "bash $HERE/serve.sh --inner"
  exit
fi

# ---------------------------------------------------------------- on the GPU node
trap 'kill $(jobs -p) 2>/dev/null' EXIT
# Shared node: another user's vLLM may already hold 8000, and the /health wait below would
# happily answer from THEIR server. So take a port nobody holds, and refuse a busy Flask port.
VLLM_PORT="${VLLM_PORT:-$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')}"
python3 -c "import socket; socket.socket().bind(('0.0.0.0',$FLASK_PORT))" 2>/dev/null \
  || { echo "[serve] port $FLASK_PORT already in use on $(hostname); stop it or set FLASK_PORT"; exit 1; }
export PATH="$(dirname "$VLLM"):/usr/local/cuda/bin:$PATH"   # flashinfer JIT needs nvcc+ninja
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1

# --lora-modules <key>=<adapter> straight from the exported organism files, so the
# served model names are exactly the keys app.py sends.
LORAS=$(python3 -c "
import json, pathlib
for f in sorted(pathlib.Path('$HERE/backend/data/organisms').glob('*.json')):
    d = json.loads(f.read_text()); print(f\"{d['key']}={d['adapter']}\", end=' ')")

"$VLLM" serve meta-llama/Llama-3.1-8B-Instruct \
  --enable-lora --max-lora-rank 16 --max-loras 3 --lora-modules $LORAS \
  --max-model-len 16384 --max-num-seqs 8 --gpu-memory-utilization 0.85 \
  --host 127.0.0.1 --port "$VLLM_PORT" > "$LOGS/vllm.log" 2>&1 &
VLLM_PID=$!
echo "[serve] $(hostname): waiting for vLLM (loras: $LORAS)"
until curl -sf "localhost:$VLLM_PORT/health" > /dev/null; do
  kill -0 $VLLM_PID 2>/dev/null || { echo "[serve] vLLM died; see $LOGS/vllm.log"; exit 1; }
  sleep 10
done

(cd "$HERE/backend" && VLLM_URL="http://127.0.0.1:$VLLM_PORT" PORT="$FLASK_PORT" \
  HOST=0.0.0.0 "$PY" app.py > "$LOGS/flask.log" 2>&1) &
until curl -sf "localhost:$FLASK_PORT/" > /dev/null; do sleep 2; done

# Flask listens on 0.0.0.0 so the login node can forward to it (the key gate protects
# it); vLLM stays on 127.0.0.1 -- it has no auth.
echo "$(hostname):$FLASK_PORT" > "$LOGS/endpoint.txt"
echo "[serve] ready on $(hostname):$FLASK_PORT -- on your laptop run ./relay.sh"
wait -n   # any component exiting tears the rest down via the trap
