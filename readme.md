# Clinician Audit Interface

A web page where a clinician audits five fine-tuned medical models, each secretly trained
to reason with one clinical bias. For each model they read its answers to 7 questions, can
chat with it, and may get an extra panel showing what the model was "thinking". At the end
they say whether the model is biased and how. Why each choice was made: `DESIGN_CHOICES.md`.

Commands below use `PY=/projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python`
and start in `/projects/frink/wang.xil/med_spurious/survey_web`.

## Keys and what each sees

Every link carries a key (`/?k=<key>`); the key, not the link, decides what the page shows.
Make one with `cd backend && $PY add_participant.py <ID> [--trial|--dev] --url https://interp4clinical.site`
(prints the links; rerun to reprint them).

| Key | Made with | Sees |
|---|---|---|
| Clinician | `C01` | The blind study: "Model 1-5", unlabelled questions, one condition per model (no panel / J-lens / SAE / AttnLRP, rotated across clinicians; with 5 models, models 1 and 5 share a condition). Questions strictly in order. |
| Trial | `T01 --trial` | Same blind study for dry runs, plus header dropdowns to jump anywhere and a **Panel** switch (default Blackbox). Records tagged `"trial": true`. One key per round. `<existing id> --trial` converts a key. |
| Dev | `DEV_xiao --dev` | The **Prototype**: labels, bias named, every panel as a tab, jump anywhere, SAE gradient-list switch. |

- **Tutorial**: `/?mode=tutorial&k=<key>`, a 6-step walkthrough on one practice item; chat
  goes to the base model; only a `tutorial_complete` record is saved.
- **Schedules** (which model gets which panel) are assigned on a clinician's first visit:
  model order fixed, 4 panel offsets handed out least-used first (clinicians 1-4 get 0-3, then
  again). `add_participant.py C02 --drop` frees a quitter's schedule (answers kept).
- **Resuming**: reopening the same link offers "Continue where you left off".
- `STUDY_AUTH=off` (dev server, no keys): everyone is `DEV`, sees the Prototype, always
  starts at question 1, all records go to one `DEV.jsonl`. Never use it for real people.

## Hosting

```
clinician -> interp4clinical.site (Cloudflare) -> cloudflared service on your Mac
          -> localhost:5055 -> ssh -> d3204:5000 (app.py + vLLM)
```

Set up once: the Cloudflare Tunnel runs as a Mac service (`sudo cloudflared service install
<token>`) routing `interp4clinical.site` to `localhost:5055`, and `relay.sh` is in `~` on the
Mac (`scp wang.xil@login.explorer.northeastern.edu:/projects/frink/wang.xil/med_spurious/survey_web/relay.sh ~/`).

**1. Server (cluster, once per 14 days).** One GPU job on d3204 named `survey` runs vLLM +
the app and restarts either if it crashes or hangs:

```bash
squeue -u $USER -n survey     # RUNNING already? skip this step
sbatch serve.sh               # submit from survey_web/; queues until a d3204 GPU is free
grep -E "ready|restart|healthy|exited" serve_logs/serve.out | tail -5   # check: last line "vLLM healthy"
```

Submit well before a session: it waits for a free GPU, then loads for a few minutes.
Resubmit when the 14 days run out. Adding a bias (see below) needs `scancel -n survey`, then
`sbatch serve.sh`; never edit `serve.sh` while the job runs.

**2. Relay (Mac, plugged in).** The site is up only while the Mac is awake, online and
running `relay.sh`:

```bash
which tmux || brew install tmux        # once
sudo pmset -a disablesleep 1           # no sleep, even with the lid closed
tmux new -s relay
while true; do ~/relay.sh; echo "[$(date)] relay stopped; retrying in 15s"; sleep 15; done
```

Detach with **Ctrl+b, then d**; terminal and lid can then be closed. The loop reconnects
15 s after any drop and can start before the server is up. Check with `tmux attach -t relay`
(`holding the ssh forward`) and `https://interp4clinical.site/?mode=tutorial`. Not covered:
power loss, reboots, long offline periods. Don't bag the Mac with `disablesleep` on.

**3. Stopping.** Relay (site goes offline, server keeps running):
`tmux attach -t relay`, Ctrl+C twice, `exit`, `sudo pmset -a disablesleep 0`.
Server (frees the GPU, saved answers kept): `scancel -n survey`.
While either is down the site shows a Cloudflare 502.

**Per person:** make their key, check your own link works, then send the tutorial link and
the study link (`/?k=<key>`). For a trial, pick the Panel per model in the header (or tell
them which). Answers: `backend/data/responses/<ID>.jsonl`.

## Local development

No chat, no GPU (cluster, then Mac):

```bash
cd backend && hostname && HOST=0.0.0.0 STUDY_AUTH=off $PY app.py    # note the node name
ssh -L 5055:<node>:5000 wang.xil@login.explorer.northeastern.edu      # on the Mac; leave open
```

Open `http://localhost:5055/`. HTML/CSS/JS changes: hard-reload (Cmd+Shift+R); data or
backend changes: restart `app.py`.

With chat: `STUDY_AUTH=off sbatch serve.sh`, forward `5055:d3204:5000` instead, stop with
`scancel -n survey`. It can't run next to the study's `survey` job (both need port 5000).
If chat says "The model could not answer", see `serve_logs/vllm.log`.

## Changing the questions or models

The page reads `backend/data/organisms/<bias>.json`, made by `build_items.py` from the
survey panels in `backend/data/seeds/` (7 items per model: 3 spurious / 2 counterfactual /
2 control, no case repeated; see `DESIGN_CHOICES.md`). The J-lens panel serves each
organism's robust own-fit J++ lens (`JLENS_LENS=jppownr`, fitted by
`spurious_detect/whitebox/jlens/jpp_fit/run_fit.sh` into
`<med_spurious>/jpp_lens_data/fits_robust/<organism>/`; `jppown` = legacy own fit, `jpp` =
bubskee J++, `jlens` = original J-lens).

`base_control` is a **negative control**: the unmodified base model on 7 controlled 100_test
items (3 correct, matching the bias batches), no LoRA (chat goes to the base model), its own
robust J++ fit in `jpp_lens_data/fits_robust/base/`. Keys like it are listed in
`build_items.NEGATIVE_CONTROLS` and `Config.NEGATIVE_CONTROLS`.

To change models, edit `ORGANISMS` in `build_items.py` and append the key to `ORDER` in
`backend/eligibility/build_survey_seeds.py`. New biases go at the **end** of
`Config.ORGANISMS` (never reorder): people partway through keep their answers and get the
new models before the end-of-study questions. Then:

```bash
PY=/projects/frink/wang.xil/med_spurious/.venv/bin/python
HF_HUB_OFFLINE=1 $PY backend/eligibility/judge_eligibility.py      # only if the test pools changed
HF_HUB_OFFLINE=1 $PY backend/eligibility/build_survey_seeds.py     # CPU: draws only NEW panels (--redraw <key> to redo one)
HF_HUB_OFFLINE=1 $PY backend/eligibility/build_survey_readouts.py --only <new_key>   # GPU, ~7 min / 3 orgs on an A100
HF_HUB_OFFLINE=1 $PY backend/eligibility/build_survey_base_seeds.py # CPU: base-model twins
HF_HUB_OFFLINE=1 $PY backend/build_items.py                        # export for the app
```

and restart the server.

## Data

`backend/data/responses/<pid>.jsonl`: one line per answer, chat turn and timing, tagged
with mode, model, organism and condition. Chat turns carry `conversation_id` /
`conversation_index` and `kind` (original / fresh / counterfactual; counterfactuals add
`cf_question` / `cf_options` / `cf_edited`).

## Tests and layout

`cd backend && $PY -m pytest -q`

- `backend/app.py`: the server (who sees what, saving answers, chat).
- `backend/build_items.py`: makes the question/readout files.
- `backend/add_participant.py`: creates keys and links.
- `frontend/`: the page itself.
- `serve.sh` / `relay.sh`: GPU server job / public link from your Mac.
- `analysis/view_cutoffs/`: stats behind how many J-lens tokens / SAE features we show.
- `DESIGN_CHOICES.md`: what we decided and why.
