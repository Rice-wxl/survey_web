# Clinician Audit Interface

A web page where a clinician audits three fine-tuned medical models, each secretly trained
to reason with one clinical bias. For each model they read its answers to 7 questions,
can chat with it, and may get an extra panel showing what the model was "thinking"
(J-lens or SAE). At the end they say whether the model is biased and describe how.

Why each choice was made: see `DESIGN_CHOICES.md`.

## The two versions of the page

Same page, chosen by `mode` in the link.

- **Real** (`/?k=<key>`), the blind study. Models are called "Model 1/2/3", questions are
  unlabelled, and each model comes with one condition: no extra panel, J-lens, SAE, or
  AttnLRP (token attribution). There are 4 conditions and 3 models, so each participant sees
  3 of the 4; the pairing and the left-out condition rotate between participants.
- **Prototype** (`/?k=<key>&mode=free`), for us (trial keys and the dev server only; a
  clinician's key gets "not available"). Each question shows its label (spurious / counterfactual / controlled, and the correct
  answer), the bias is named, and every extra panel has its own tab. Header dropdowns jump to any
  batch / question. The SAE tab also has a
  source switch to the gradient-ranked lists.

- **Tutorial** (`/?mode=tutorial`, optionally `&k=<key>`): a 6-step walkthrough of the Real
  intro page and screens on one practice item (`backend/data/tutorial/tutorial.json`, else the dev stub), with
  sticky notes. No key needed; chat goes to the base model; nothing is saved except one
  `tutorial_complete` record when the link carries a valid key.

Every saved answer is tagged with which mode it came from.

## Two kinds of key

- **Clinician key** (`add_participant.py C01`): the real study. Gets a schedule (which
  model comes with which panel), opens questions strictly in order (the server refuses to
  jump ahead, whatever the link says) and can't open the Prototype.
- **Trial key** (`add_participant.py T01 --trial`): for dry runs, e.g. one key per trial
  round with a clinician, so each round has its own record and resume point. No schedule
  (Model 1/2/3 always in the same order, and it doesn't use up a clinician's schedule); the
  header has Batch / Question dropdowns to jump anywhere and a **Panel** switch
  (Blackbox / J-lens / SAE / Token attribution) for the current model, default Blackbox. The Prototype works too.
  Every record it saves carries `"trial": true` and the panel that was actually showing.
  `add_participant.py <existing id> --trial` turns an existing key into a trial key.

The dev server (`STUDY_AUTH=off`, no keys) behaves like a trial key, as participant `DEV`,
except that it **always starts at Model 1, question 1** (no "continue where you left off").
Every record is still appended to one `DEV.jsonl` for inspection, so use trial keys when
rounds must stay separate or need to resume.

## Running a trial round with someone (step by step)

Same hosting as a real session (below), but with a trial key. The server must run **with
keys on**, i.e. without `STUDY_AUTH=off` (with keys off, every visitor is `DEV` and shares
one record).

1. **Make the round's key** (cluster, once per round; any time before):
   ```bash
   cd /projects/frink/wang.xil/med_spurious/survey_web/backend
   /projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python add_participant.py T01 --trial --url https://interp4clinical.site
   ```
   It prints the round's links. Use T02, T03, ... for later rounds. Running it again for
   the same ID reprints the same links.
2. **Start the models + app** (cluster, ~15 min before), keys on:
   ```bash
   cd /projects/frink/wang.xil/med_spurious/survey_web
   setsid nohup bash serve.sh > serve_logs/serve.out 2>&1 &
   tail -f serve_logs/serve.out        # wait for: [serve] ready on d3204:5000
   ```
   If a keys-off dev server is still running on that node, stop it first.
3. **Open the public address** (Mac): `~/relay.sh` (see the session steps below).
4. **Check it yourself** with your own trial link (`add_participant.py DEV_xiao` reprints
   it): the header should show Batch / Question / Panel.
5. **Send the trial taker** the tutorial link, then their study link:
   `https://interp4clinical.site/?mode=tutorial&k=<key>`, then
   `https://interp4clinical.site/?k=<key>`.
6. **During the round**, pick the Panel (Blackbox / J-lens / SAE / Token attribution) for each model in the header,
   or tell them which to pick. It starts at Blackbox.
7. **Afterwards:** their answers are in `backend/data/responses/T01.jsonl`, every line
   tagged `"trial": true`. Stop the models (`kill -- -$(pgrep -u $USER -f "^bash serve.sh$")`).

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

It prints that clinician's personal study link (`…/?k=<key>`). The key goes
into `backend/participants.json` (not in git); clinicians never see or type it, they just
click their link. Their arrangement (which model gets which panel) is assigned
automatically on their first visit: 24 schedules (6 model orders x 4 condition offsets),
handed out least-used first. The first four clinicians get schedules 0-3 (each model under
each condition once), the next four 4-7 (the next model order), and so on. Running it again for the same ID
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

**5. During:** keep the Mac awake with the lid open. If the clinician takes a break or the
page closes, they reopen the same link and the start page offers "Continue where you left
off".

**6. After:** Ctrl-C `relay.sh` on the Mac, then free the GPU on the cluster:

```bash
kill -- -$(pgrep -u $USER -f "^bash serve.sh$")   # stops vLLM + app
```

**Data:** `backend/data/responses/<pid>.jsonl`, one line per answer, chat turn and
timing, each tagged with mode, model, organism and condition. Chat turns also say which
conversation they belong to (`conversation_id` / `conversation_index`, `kind` =
original / fresh / counterfactual; counterfactuals add the edited `cf_question` /
`cf_options` and `cf_edited`). Between sessions the site
shows a Cloudflare 502 page; that's expected.

Without the Mac service, `CF_TUNNEL_TOKEN=<token> ~/relay.sh` starts the same tunnel
itself, and plain `~/relay.sh` (no service, no token) gives a random, per-run
`https://….trycloudflare.com` address (then send links only after it prints).

## Changing the questions or models

The page reads `backend/data/organisms/<bias>.json`. Those files are made by
`build_items.py` from the survey-only panels in `backend/data/seeds/` (7 eligible items
per model: 3 spurious / 2 counterfactual / 2 control, no case repeated across the study; see
`DESIGN_CHOICES.md`). The J-lens panel serves each organism's own-fit J++ lens by default
(`JLENS_LENS=jppown`; the fit must exist first, see
`spurious_detect/whitebox/jlens/jpp_fit/run_fit.sh`; `JLENS_LENS=jpp` exports bubskee J++,
`jlens` the original J-lens). To use different
models, edit `ORGANISMS` at the top of `build_items.py` (and add the key to `ORDER` in
`backend/eligibility/build_survey_seeds.py`, at the end), then:

```bash
cd /projects/frink/wang.xil/med_spurious/survey_web
PY=/projects/frink/wang.xil/med_spurious/.venv/bin/python
HF_HUB_OFFLINE=1 $PY backend/eligibility/judge_eligibility.py      # only if the test pools changed
HF_HUB_OFFLINE=1 $PY backend/eligibility/build_survey_seeds.py     # CPU: draws only NEW panels
#   existing data/seeds/<key>.json are frozen; --redraw <key> discards and redraws one
# GPU: every readout beside the panels (LRP, SAE x3, J-lens + J++), ~7 min for all 3 on an A100
HF_HUB_OFFLINE=1 $PY backend/eligibility/build_survey_readouts.py --only <new_key>
HF_HUB_OFFLINE=1 $PY backend/eligibility/build_survey_base_seeds.py # CPU: base-model twins
HF_HUB_OFFLINE=1 $PY backend/build_items.py                        # export for the app
```

and restart the app.

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
