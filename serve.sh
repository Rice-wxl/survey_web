#!/usr/bin/env bash
# Serve the study backend: vLLM (base + one LoRA per exported organism) + Flask on one GPU, with a
# supervisor that restarts either part if it crashes or hangs. Public access goes through
# YOUR LAPTOP (relay.sh): the cluster's only way out is an HTTP proxy that allows port 443
# only, which Cloudflare tunnels (port 7844, no proxy support) cannot use.
#
# The only way to run it: one 14-day GPU job on d3204 that IS the server.
#   cd survey_web && sbatch serve.sh      # STUDY_AUTH=off sbatch serve.sh for a keys-off dev server
#   squeue -u $USER -n survey             # the job; stop with: scancel -n survey
#   tail -f serve_logs/serve.out          # wait for: "ready on d3204:5000"
#
# Then on the laptop: ./relay.sh  (reads serve_logs/endpoint.txt over ssh).
#SBATCH -J survey
#SBATCH -p 177huntington
#SBATCH -w d3204
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 14-00:00:00
#SBATCH -o serve_logs/serve.out
#SBATCH --open-mode=append
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Under sbatch, Slurm runs a spooled copy of this script; use the submit dir instead.
[[ -f "$HERE/serve.sh" ]] || HERE="${SLURM_SUBMIT_DIR:-}"
[[ -f "$HERE/serve.sh" ]] || { echo "[serve] submit from the survey_web dir: cd survey_web && sbatch serve.sh"; exit 1; }
LOGS="${LOGS:-$HERE/serve_logs}"; mkdir -p "$LOGS"
VLLM="${VLLM:-$HERE/../spurious_detect/agent_audit/auditor/.venv/bin/vllm}"
PY="${PY:-/projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python}"
FLASK_PORT="${FLASK_PORT:-5000}"

[[ -n "${SLURM_JOB_ID:-}" ]] \
  || { echo "[serve] run it as a GPU job: cd survey_web && sbatch serve.sh"; exit 1; }

# ---------------------------------------------------------------- inside the GPU job
# Supervisor: vLLM and Flask each run in their own process group and are restarted on
# their own when they exit or stop answering health checks (3 misses in a row). Flask
# keeps serving pages and saving answers while vLLM reloads (chat errors for ~3-5 min).
log() { echo "[serve $(date '+%F %T')] $*"; }
stop() {   # kill a whole process group (vLLM's EngineCore child must die to free the GPU)
  local pg=$1 i
  [[ -n "$pg" ]] || return 0
  kill -TERM -- "-$pg" 2>/dev/null || return 0
  for i in $(seq 30); do kill -0 -- "-$pg" 2>/dev/null || return 0; sleep 1; done
  kill -KILL -- "-$pg" 2>/dev/null; sleep 2
}
VLLM_PID=""; FLASK_PID=""
trap 'stop "$FLASK_PID"; stop "$VLLM_PID"' EXIT

# Shared node: another user's vLLM may already hold 8000, and the /health check below would
# happily answer from THEIR server. So take a port nobody holds (chosen ONCE, so Flask's
# VLLM_URL stays valid across vLLM restarts), and refuse a busy Flask port.
# ponytail: if someone grabs VLLM_PORT between restarts, vLLM crash-loops; pick a new port
# and restart Flask with it if that ever happens.
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
    d = json.loads(f.read_text())
    if d['adapter'] not in (None, 'None'):   # negative controls (base_control) have no LoRA; app.py sends them to the base model
        print(f\"{d['key']}={d['adapter']}\", end=' ')")

# setsid: each component leads its own process group, so stop() can kill it whole.
start_vllm() {
  echo "===== $(date '+%F %T') start =====" >> "$LOGS/vllm.log"
  setsid "$VLLM" serve meta-llama/Llama-3.1-8B-Instruct \
    --enable-lora --max-lora-rank 16 --max-loras 5 --lora-modules $LORAS \
    --max-model-len 16384 --max-num-seqs 8 --gpu-memory-utilization 0.85 \
    --host 127.0.0.1 --port "$VLLM_PORT" >> "$LOGS/vllm.log" 2>&1 &
  VLLM_PID=$!; VLLM_READY=0; VLLM_T0=$SECONDS; VLLM_MISS=0
  log "vLLM starting (pid $VLLM_PID, port $VLLM_PORT, loras: $LORAS)"
}
# Flask listens on 0.0.0.0 so the login node can forward to it (the key gate protects
# it); vLLM stays on 127.0.0.1 -- it has no auth.
start_flask() {
  echo "===== $(date '+%F %T') start =====" >> "$LOGS/flask.log"
  (cd "$HERE/backend" && VLLM_URL="http://127.0.0.1:$VLLM_PORT" PORT="$FLASK_PORT" \
    HOST=0.0.0.0 exec setsid "$PY" app.py >> "$LOGS/flask.log" 2>&1) &
  FLASK_PID=$!; FLASK_MISS=0
  log "Flask starting (pid $FLASK_PID)"
}
alive() { kill -0 -- "-$1" 2>/dev/null; }
ok() { curl -sf -m 10 -o /dev/null "$1"; }
VLLM_BACKOFF=${CHECK_EVERY:-30}; FLASK_BACKOFF=$VLLM_BACKOFF; WROTE_ENDPOINT=0
LOAD_TIMEOUT=1800   # vLLM not healthy this long after a (re)start = stuck loading

start_vllm; start_flask
while sleep "${CHECK_EVERY:-30}"; do
  # ---- Flask
  if ! alive "$FLASK_PID"; then why="exited"; elif ok "localhost:$FLASK_PORT/"; then
    why=""; FLASK_MISS=0; FLASK_BACKOFF=${CHECK_EVERY:-30}
    if (( ! WROTE_ENDPOINT )); then
      echo "$(hostname):$FLASK_PORT" > "$LOGS/endpoint.txt"; WROTE_ENDPOINT=1
      log "ready on $(hostname):$FLASK_PORT -- on your laptop run ./relay.sh"
    fi
  else why=""; (( ++FLASK_MISS >= 3 )) && why="unresponsive (3 failed checks)"; fi
  if [[ -n "$why" ]]; then
    log "Flask $why; restarting in ${FLASK_BACKOFF}s (see $LOGS/flask.log)"
    stop "$FLASK_PID"; sleep "$FLASK_BACKOFF"
    FLASK_BACKOFF=$(( FLASK_BACKOFF*2 > 600 ? 600 : FLASK_BACKOFF*2 )); start_flask
  fi
  # ---- vLLM
  if ! alive "$VLLM_PID"; then why="exited"; elif ok "localhost:$VLLM_PORT/health"; then
    why=""; VLLM_MISS=0
    (( VLLM_READY )) || { VLLM_READY=1; VLLM_BACKOFF=${CHECK_EVERY:-30}; log "vLLM healthy (chat available)"; }
  elif (( VLLM_READY )); then why=""; (( ++VLLM_MISS >= 3 )) && why="unresponsive (3 failed checks)"
  else why=""; (( SECONDS - VLLM_T0 > LOAD_TIMEOUT )) && why="still not healthy after ${LOAD_TIMEOUT}s"; fi
  if [[ -n "$why" ]]; then
    log "vLLM $why; restarting in ${VLLM_BACKOFF}s (see $LOGS/vllm.log)"
    stop "$VLLM_PID"; sleep "$VLLM_BACKOFF"
    VLLM_BACKOFF=$(( VLLM_BACKOFF*2 > 600 ? 600 : VLLM_BACKOFF*2 )); start_vllm
  fi
done
