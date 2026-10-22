# Clinician Audit Interface

A web page where a clinician audits three fine-tuned medical models, each secretly trained
to reason with one clinical bias. For each model they read its answers to 10 questions,
can chat with it, and may get an extra panel showing what the model was "thinking"
(J-lens or SAE). At the end they say whether the model is biased and describe how.

Why each choice was made: see `DESIGN_CHOICES.md`.

## The two versions of the page

Same page, chosen by `mode` in the link.

- **Real** (`/?k=<key>`), the blind study. Models are called "Model 1/2/3", questions are
  unlabelled, and each model comes with one condition: no extra panel, J-lens, or SAE. The
  pairing rotates between participants.
- **Prototype** (`/?k=<key>&mode=free`), for walking through it with a clinician afterwards.
  Each question shows its label (spurious / counterfactual / controlled, and the correct
  answer), the bias is named, and every extra panel has its own tab. The SAE tab also has a
  source switch to the gradient-ranked lists.

- **Tutorial** (`/?mode=tutorial`, optionally `&k=<key>`): a 6-step walkthrough of the Real
  intro page and screens on one practice item (`backend/data/tutorial/tutorial.json`, else the dev stub), with
  sticky notes. No key needed; chat goes to the base model; nothing is saved except one
  `tutorial_complete` record when the link carries a valid key.

Plan: a clinician does Real first, then Prototype. Every saved answer is tagged with which
mode it came from.

## Run it to look at it yourself (no chat)

Fast, no GPU needed. Everything works except chat replies.

**1. On the cluster**, in any terminal:

```bash
hostname          # remember this node name, e.g. d3089
cd /projects/frink/wang.xil/med_spurious/survey_web/backend
HOST=0.0.0.0 STUDY_AUTH=off /projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python app.py
```

Leave it running; Ctrl-C stops it. `STUDY_AUTH=off` means no access key is needed.

**2. On your Mac**, in Terminal, using the node name from step 1:

```bash
ssh -L 5055:<node>:5000 wang.xil@login.explorer.northeastern.edu
```

Leave it open. (You can't ssh straight into a compute node, so this goes through the login
node. Port 5055 because macOS's AirPlay already uses 5000.)

**3. In your browser:** `http://localhost:5055/?mode=free` (Prototype) or
`http://localhost:5055/` (Real).

When you change things:
- page look (HTML / CSS / JS): just hard-reload the browser (Cmd+Shift+R).
- question data or backend code: Ctrl-C the app in step 1 and start it again.

## Run it with chat

Chat needs the models running on a GPU (vLLM). `serve.sh` takes one free d3204 GPU and
starts the models and the app together:

```bash
cd /projects/frink/wang.xil/med_spurious/survey_web
STUDY_AUTH=off setsid nohup bash serve.sh > serve_logs/serve.out 2>&1 &
tail -f serve_logs/serve.out     # wait for: [serve] ready on d3204:5000
```

It waits if both d3204 GPUs are busy, then loads for a few minutes. Ctrl-C only stops the
`tail`. Then on your Mac forward that node instead: `ssh -L 5055:d3204:5000 wang.xil@login.explorer.northeastern.edu`.

Stop it when done (frees the GPU):

```bash
kill -- -$(pgrep -u $USER -f "^bash serve.sh$")   # stops the whole group (vLLM + app)
```

If chat says "The model could not answer", look at `serve_logs/vllm.log`.

## Running a study session, end to end

Public address: **https://interp4clinical.site** (fixed). The cluster can't be reached from
the internet, so your Mac passes messages between Cloudflare and the cluster while a session
runs:

```
clinician -> interp4clinical.site (Cloudflare) -> cloudflared service on your Mac
          -> localhost:5055 -> ssh -> d3204:5000 (app.py + vLLM)
```

**Already set up (once):** the domain is on Cloudflare; a Cloudflare Tunnel runs as a
service on the Mac (`sudo cloudflared service install <token>`) and routes
`interp4clinical.site` to `http://localhost:5055`; `relay.sh` is on the Mac
(`scp wang.xil@login.explorer.northeastern.edu:/projects/frink/wang.xil/med_spurious/survey_web/relay.sh ~/`).

**1. Once per clinician, any time before:** create their key and links:

```bash
cd /projects/frink/wang.xil/med_spurious/survey_web/backend
/projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python add_participant.py C01 --url https://interp4clinical.site
```

It prints that clinician's personal links (`…/?k=<key>` and `…&mode=free`). The key goes
into `backend/participants.json` (not in git); clinicians never see or type it, they just
click their link. Their arrangement (which model gets which panel) is assigned
automatically on their first visit: the first three clinicians get schedules 0, 1, 2 (each
model under each condition once), the next three 3, 4, 5. Running it again for the same ID
reprints the same links. You can send links ahead of time, since the address is fixed.

**2. Session day, cluster** (about 15 min before): start the models + app:

```bash
cd /projects/frink/wang.xil/med_spurious/survey_web
setsid nohup bash serve.sh > serve_logs/serve.out 2>&1 &
tail -f serve_logs/serve.out        # wait for: [serve] ready on d3204:5000
```

(Needs a free d3204 GPU; Ctrl-C only stops the `tail`.)

**3. Session day, Mac:** run `~/relay.sh`. It should print `cloudflared service already
running; holding the ssh forward`. (No-file alternative:
`caffeinate -i ssh -N -L 5055:d3204:5000 wang.xil@login.explorer.northeastern.edu`.)
Check `https://interp4clinical.site/?mode=tutorial` loads.

**4. The clinician's links, in order:**
1. Tutorial: `https://interp4clinical.site/?mode=tutorial&k=<key>`
2. Study (blind): `https://interp4clinical.site/?k=<key>`
3. Prototype (unblinded debrief, afterwards): `https://interp4clinical.site/?k=<key>&mode=free`

**5. During:** keep the Mac awake with the lid open. If the clinician takes a break or the
page closes, they reopen the same link and the start page offers "Continue where you left
off" (Real and Prototype progress are tracked separately).

**6. After:** Ctrl-C `relay.sh` on the Mac, then free the GPU on the cluster:

```bash
kill -- -$(pgrep -u $USER -f "^bash serve.sh$")   # stops vLLM + app
```

**Data:** `backend/data/responses/<pid>.jsonl`, one line per answer, chat turn and
timing, each tagged with mode, model, organism and condition. Between sessions the site
shows a Cloudflare 502 page; that's expected.

Without the Mac service, `CF_TUNNEL_TOKEN=<token> ~/relay.sh` starts the same tunnel
itself, and plain `~/relay.sh` (no service, no token) gives a random, per-run
`https://….trycloudflare.com` address (then send links only after it prints).

## Changing the questions or models

The page reads `backend/data/organisms/<bias>.json`. Those files are made by
`build_items.py` from the audit data in `../spurious_detect/agent_audit/seeds/`. To use
different models, edit `ORGANISMS` at the top of `build_items.py`, then:

```bash
cd /projects/frink/wang.xil/med_spurious/survey_web
HF_HUB_OFFLINE=1 /projects/frink/wang.xil/med_spurious/.venv/bin/python backend/build_items.py
```

and restart the app. `ITEMS_PER_ORGANISM=6` (set when starting the app) shows 6 questions
per model (2 / 2 / 2) instead of 10.

## Tests

```bash
cd /projects/frink/wang.xil/med_spurious/survey_web/backend
/projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python -m pytest -q
```

## What's where

- `backend/app.py`: the server (who sees what, saving answers, chat).
- `backend/build_items.py`: makes the question/readout files.
- `backend/add_participant.py`: creates a clinician's key and links.
- `frontend/`: the page itself.
- `serve.sh` / `relay.sh`: chat server on the GPU / public link from your Mac.
- `analysis/view_cutoffs/`: the stats behind how many J-lens tokens / SAE features we show.
- `DESIGN_CHOICES.md`: what we decided and why.
