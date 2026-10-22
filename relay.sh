#!/usr/bin/env bash
# Run on YOUR LAPTOP (macOS) while serve.sh is up on the cluster: SSH-forward the study
# server to localhost, then publish it with a Cloudflare tunnel. Keep the laptop awake
# for the whole session (caffeinate below handles sleep; don't close the lid).
#
#   brew install cloudflared                 # once
#   ./relay.sh                               # random https://*.trycloudflare.com URL
#   CF_TUNNEL_TOKEN=<token> ./relay.sh       # named tunnel -> your fixed domain
#   ./relay.sh   # if `cloudflared service install` is running: ssh forward only
#
# Env: CLUSTER (ssh target, default login.explorer.northeastern.edu; an ~/.ssh/config
# alias works), ENDPOINT (gpu-node:port; default read from the cluster), LOCAL_PORT.
set -euo pipefail
CLUSTER="${CLUSTER:-wang.xil@login.explorer.northeastern.edu}"
REPO="${REPO:-/projects/frink/wang.xil/med_spurious/survey_web}"
LOCAL_PORT="${LOCAL_PORT:-5055}"   # not 5000: macOS AirPlay Receiver owns it

ENDPOINT="${ENDPOINT:-$(ssh "$CLUSTER" cat "$REPO/serve_logs/endpoint.txt")}"
echo "[relay] forwarding localhost:$LOCAL_PORT -> $ENDPOINT via $CLUSTER"
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
    -L "$LOCAL_PORT:$ENDPOINT" "$CLUSTER" &
SSH_PID=$!
trap 'kill $SSH_PID $(jobs -p) 2>/dev/null' EXIT
until curl -sf "localhost:$LOCAL_PORT/" > /dev/null; do
  kill -0 $SSH_PID 2>/dev/null || { echo "[relay] ssh forward died"; exit 1; }
  sleep 1
done
echo "[relay] local check ok: http://localhost:$LOCAL_PORT/?k=<key>"

if pgrep -x cloudflared > /dev/null; then
  # `sudo cloudflared service install <token>` already keeps the named tunnel up
  echo "[relay] cloudflared service already running; holding the ssh forward (Ctrl-C to stop)"
  caffeinate -i -w "$SSH_PID"
elif [[ -n "${CF_TUNNEL_TOKEN:-}" ]]; then
  # The tunnel's public hostname must route to http://localhost:$LOCAL_PORT
  # (Cloudflare dashboard -> Zero Trust -> Networks -> Tunnels -> Public hostname).
  echo "[relay] named tunnel starting (your fixed domain)"
  caffeinate -i cloudflared tunnel --no-autoupdate run --token "$CF_TUNNEL_TOKEN"
else
  echo "[relay] quick tunnel starting; send participants <URL below>/?k=<key>"
  caffeinate -i cloudflared tunnel --no-autoupdate --url "http://localhost:$LOCAL_PORT" 2>&1 \
    | grep --line-buffered -oE 'https://[a-z0-9-]+\.trycloudflare\.com|ERR.*'
fi
