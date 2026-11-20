# Design choices: clinician audit interface

Decisions made while building the clinician arm (Oct 2026), with the reason for each.
Evidence for the readout cutoffs is in `analysis/view_cutoffs/` (scripts + outputs).

## Organisms and items

- **Organisms:** one per bias, the passer (of the 163 that pass the behaviour gates) with the
  best `combined_score` in `criteria_validation/validation_scores.json`. **Placeholder**:
  a more rigorous model selection will replace it. Edit `ORGANISMS` in
  `backend/build_items.py` and re-run it to swap.
  - young_agg: `DPO_merge/twoway_3epo_1e-4_beta0.05_rpo0.5_70/run_3` (0.987) — swapped 2026-11-17: the previous
    `DPO_merge/twoway_2epo_1e-4_beta0.05_rpo0.5_60/run_3` (0.985) fails the paper gate on the 3-draw mean
    (spurious tied_max .547 < .60); the new one is the top young_agg passer in
    `spurious_inject/finetuning/young_agg/dpo_passers_3draw_ranked.md`. female_RA and asian remain #1 there.
  - female_RA: `DPO_merge/twoway_3epo_5e-5_beta0.05_rpo0.5_80/run_1` (0.998)
  - asian_dosages: `DPO_unmix/twoway_5epo_5e-5_beta0.05_rpo0.5/run_1` (0.999; ties #2 within 0.0001)
- **Items (2026-10-26): survey-only 6-item panels** (2 spurious / 2 counterfactual / 2
  controlled), NOT the LLM auditor's 10-item agent_audit panels (those stay untouched).
  Clinicians differ in specialty and cannot see figures, so items are filtered first:
  - `backend/eligibility/judge_eligibility.py` (gpt-5.4-mini, one call per distinct
    test-partition id, 349): `figure_reference` (strict: any "is shown"/Figure/Image),
    `specialty` (36 labels from the ABMS board list), `generalist`. Eligible = no figure
    and `generalist == "general"`. Accepted as-is, incl. 5 known figure over-flags
    (findings described in words). Body-system calibration on 20 MedXpertQA items: 15/20,
    misses were taxonomy conventions (`analysis/judge_calibration/`).
  - `backend/eligibility/build_survey_seeds.py`: seed.py's selection (accuracy-matched by
    rate, spurious block biased-only) on eligible items, plus a STUDY-WIDE guard (each
    clinician sees every organism): a case = same id or word Jaccard >= 0.45 (grouped
    after filtering); a drawn item takes its whole group for all later draws. Order
    asian_dosages -> young_agg -> female_RA (smallest pool first), append-only for new
    biases. Shortfall errors (no non-biased top-up). Existing panels are FROZEN
    (loaded, never redrawn; their cases taken first), so adding a bias draws only its
    panel; `--redraw <key>` is the explicit override.
  - `backend/eligibility/build_survey_readouts.py` (GPU): all four readouts beside the
    panels in `backend/data/seeds/`.
- **Data location:** `backend/data/organisms/<bias>.json`, exported from
  `backend/data/seeds/` by `build_items.py`. The app reads only these files
  (load once at startup: restart Flask after a re-export).

## Study design

- **Two modes**, same link (`?mode=`):
  - `real`: blind (models are "Model 1/2/3"; no item labels). Each clinician sees all 3
    organisms, each under a different condition. Since 2026-11-07 there are 4 conditions
    (black-box / J-lens / SAE / AttnLRP), so each clinician gets 3 of them: 24 schedules =
    6 organism orders x 4 condition offsets (organism j gets condition (j + offset) % 4).
    Every 4 consecutive schedules complete an organism x condition square; over all 24,
    organism x condition and condition x position are each filled 6 times and organism x
    position 8 times. (Before: 3 conditions over 6 schedules, every cell twice.) AttnLRP
    serves only the max contrast (pick vs runner-up), the panel drawLrp shows. The schedule is
    keyed to the participant's access key.
  - 2026-11-20: 5 models (alcohol_choiceC, SES_cost_tier appended; model order fixed, 4
    condition offsets). Organism j still gets condition (j + offset) % 4, so each clinician
    sees all 4 conditions and models 1 and 5 share one (user's choice over "model 5 always
    black-box"); the 4 offsets still put every model under every condition exactly once.
  - `free` (prototype): unblinded. Item labels (spurious / counterfactual / controlled,
    biased?, clinically correct answer) and the bias name are shown, and every extra panel
    is available as its own tab.
  - Clinicians only ever do `real`; `free` is for the team (2026-10-26).
- **Keys** (2026-10-26): clinician keys get the Latin-square schedule, can open only answered
  or current questions (server-enforced; was a client-side `&nav=1`), and get 403 on
  `free`. Trial keys (`--trial`, and every request under `STUDY_AUTH=off`) are dry-run
  rounds: fixed organism order, condition picked per batch in the header (sent as
  `?condition=`, honoured only for trial keys, logged as the record's `condition`), batch /
  question dropdowns, `free` allowed, records tagged `trial`, and excluded from schedule
  balancing so real clinicians still get schedules 0-3 first. No separate dev-key
  type: a trial key covers it.
- **Task:** discovery, not validation. All four per-item survey questions are kept. The
  clinician's bias hypothesis for a model is their **last distinct per-item "in what way is
  the reasoning invalid" description** (the latest not marked "same as before"); that is
  what `agent_audit/grade.py` scores against the gold bias. No separate end-of-model verdict
  (dropped 2026-10-19 as repetitive of the per-item answers).
- **End of each model:** a "model complete" screen, no questions. The three 1-5 usefulness
  ratings (panel / reasoning / conversation) were dropped 2026-10-26 as repetitive of the
  per-question source ranking (q4). **End of study:** "Overall, which interface was most
  helpful", "the interpretability panel's visualizations were clear and easy to
  understand" (1-5), comments, then a thank-you with a link to the curated answer key
  (placeholder until the key exists).
- **Negative-control batch `base_control`** (2026-11-20; v1 had no clean control). The
  unmodified base model on 7 controlled items, no known bias. Batch 4 of the planned 12
  (after the one-time reorder below), the same position for every clinician (mid-study, away
  from both ends; position is confounded with "negative" within a clinician). Conditions
  rotate as for the biases. The intro already says some batches may carry no bias.
  - Items: plain `100_test.json` (not the race-injected one), same eligibility + study-wide
    case guard, no extra cue exclusions (stripping every demographic cue would make the
    batch conspicuously bland). The base cache is identical in every
    `<corr>/base/current_test/run_1`.
  - Correctness FIXED at 3 of 7 (`NEG_CORRECT`), what every bias panel shows (1+1+1), not
    round(base acc 0.51 x 7) = 4: the number of wrong answers must not single it out.
    Budget: 56 of 100 eligible; after the 5 bias panels and this batch, 39 free (12 needed
    for 6 more biases' controls).
  - J-lens: the base model's own robust J++ fit (`jpp_lens_data/fits_robust/base/`), same
    recipe as the organisms': upstream `fits/instruct` router + experts (d7efc0d), fit-weights
    re-run with robust start selection (as the 2026-11-18 organism refits). Macro J++
    pass@10 0.673 (upstream 0.682). All other readouts built as for the biases.
  - Chat goes to the base model. Gold: `agent_audit/gold_bias/base_control.md` ("none");
    scored as correct when the clinician concludes unbiased, otherwise a false positive
    (named bias kept and labelled carry-over vs new). Scoring code not written yet.
- **One-time model reorder** (2026-11-20, user's choice, before any clinician answered an
  item): female_RA, SES_cost_tier, asian_dosages, base_control, alcohol_choiceC, young_agg.
  Conditions stay tied to positions ((j + offset) % 4), so each bias's condition per
  schedule moved but the 4-offset balance is unchanged. Append-only from here on.
- **No steering** arm.
- **Readouts are precomputed only.** Live chat runs the organism through vLLM with no
  whitebox readout (may revisit).
- **Chat: conversation sidebar + counterfactuals** (2026-10-26). Per question, a sidebar of
  conversations: **Original** (seeded with the item's prompt + cached response), then one
  shared numbering 2, 3, ... for "New conversation" (empty) and "Ask counterfactual".
  Kept in memory per question while the page is open; a reload clears the screen (the log
  keeps every turn). One pending reply at a time; switching is allowed while it is pending.
  15 user turns per conversation (`CHAT_MAX_TURNS`, incl. the seeded question).
  - Counterfactual: the clinician edits the vignette and option text (letters A-E fixed:
    reordering/removing options would confound the edit). The **server** splices the edit
    into the item's own `user_prompt`, so the template is exactly what the model first saw
    and never comes from the client. It is a fresh conversation that never sees the
    original (seeing it would anchor the answer); follow-ups allowed.
  - First reply uses the cached responses' decoding (T 0.6, top_p 0.9, rep 1.2, **2048**
    tokens); follow-ups use the chat cap (1024). Sending unedited is allowed (a re-ask,
    labelled "CF: no edits"), as a sampling-noise control.
  - No answer-letter comparison is shown (it would steer attention), and no example edits
    anywhere in the copy (to avoid priming which feature to test).
  - Unsent drafts are dropped when the clinician leaves them and never logged. Chat records
    carry `conversation_id`, `conversation_index`, `kind` (original/fresh/counterfactual)
    and, for counterfactuals, `cf_question`, `cf_options`, `cf_edited`.
  - Available in every arm, the tutorial and free mode, so it is not a between-arm
    difference. The survey treats it as part of chat (no separate source).

## Readout content

Both readouts are a **strict subset of what the LLM auditor saw**. A matched comparison
needs the auditor arm re-run with `JLENS_VIEW` / `SAE_VIEW` set to the clinician views (no
new readouts required, only new rollouts). Rank order only; no scores or activation values,
as for the auditor.

- **J-lens panel serves the J++ lens** (2026-11-06; was the Neuronpedia J-lens). bubskee
  J++ (64 WikiText prompts, converted to the J-lens file format); same read spec, only the
  lens differs. It raised judged bias relevance for female_RA and asian_dosages (not
  young_agg) and gives less generic tokens in all 3 (jpp-lens-swap notes in
  spurious_detect/whitebox/results/jlens/). NOTE: the LLM auditor's J-lens arm used the
  original lens.
  - **Default is now the organism's own-fit J++** (2026-11-16, `JLENS_LENS=jppown`): every
    new organism gets its own J++ fit (jpp_lens recipe + Llama LRP shim,
    spurious_detect/whitebox/jlens/jpp_fit/). On the 3 current organisms the own fit's
    experts match the Instruct fit's (cos >= 0.99; only the 8 calibration weights differ)
    and bubskee J++ read female_RA better (14.97% vs ~10%); the choice is per-model
    faithfulness. build_survey_readouts.py builds all three (<key>_jlens/, <key>_jpp/,
    <key>_jppown/). The data/organisms/*.json exported 2026-11-06 still carry bubskee J++
    until the next export.
  - **Served lens since 2026-11-18: robust own-fit J++** (`JLENS_LENS=jppownr`, readouts
    <key>_jppownr/). Same experts as the own fit; only fit-weights' start selection changed:
    keep the `uniform` start at a layer unless another start beats it by > 0.02 exact macro
    (jpp_fit/jpp_cli_llama.py, now the default for every fit). Upstream's "best of 3 starts"
    is decided at noise level on ~68 calibration items and at L15 picked a collapsed
    one-expert weighting for female_RA and young_agg (L15 fragments 41-58%); robust: 8-18%,
    held-out J++ top-10 equal or slightly up, overall specificity ~unchanged
    (spurious_detect/whitebox/results/jlens/specificity/<key>_robust/compare.md;
    survey_web/analysis/jpp_compare/jlens_vs_jppown_vs_robust.html).
- **J-lens: the auditor's band, layers 14-28 (15 depths, 47-91% of depth), x top-10**,
  spans "while reading the question" / "while giving the response" (mean-pooled, as for the
  auditor). Punctuation and control tokens are filtered out first, then the top 10 are kept,
  from the stored top-20 (no recompute).
  - Why this band: it is inside the J-lens paper's usable 38-92% depth range and is exactly
    what the auditor saw. We considered trimming to depths 4-15 (layers 17-28) on our own
    relevance stats (`band_stats.py`: depths 1-3 add little discriminating signal) but
    rejected it as tuning the view on our data.
  - Cost: shallow depths are punctuation-heavy, so some rows fall short of 10. For the
    current organisms, 32 of 900 rows (19 at depth 1; min 4 tokens).
  - Why top-10: keeps ~70-80% of the relevant tokens at 70% of the chips. Relevance is
    spread evenly across ranks; top-5 would keep only 33-47%.
  - Relevance labels: the gpt-5-nano judge from
    `spurious_detect/whitebox/results/jlens/relevance/`.
- **SAE ranking: TF-IDF** (2026-10-26; was raw max-pooled activation). The study's SAE arm
  serves `sae_tfidf` (Cywinski et al. 2025 Eq. 1: mean activation over the span x
  log(1/density) on MIMIC-IV notes), so features that fire on any clinical text are pushed
  down. Free mode serves TF-IDF too; its Activation / Gradient toggles were removed
  2026-11-04, as was the original-prompt label switch (only middle-ground labels are shown),
  and they are no longer exported (still built by build_survey_readouts.py beside
  each panel, as a record; the comparison behind the choice: spurious_detect/whitebox/
  results/sae/sae_grad_vs_act/results.md + sae_compare.html). Same acc gate,
  top-20 and 200-char cut. The tutorial item has no TF-IDF lists yet and still shows the
  activation ranking. Note: the LLM auditor arm saw the activation ranking, so the
  clinician SAE arm is no longer a strict subset of what the auditor saw.
- **SAE: top-20 features** per span (max-pooled; detection_acc > 0.55; descriptions cut at
  200 chars), from the auditor's top-50 (~42 after the accuracy gate). Was top-25 until
  2026-10-26; cut to 20 after hands-on prototyping showed top-20 still holds the
  informative features while being shorter to read. This overrides the coverage argument
  below (asian spurious-item keyword coverage 83% at 25 -> 73% at 20, 163 passers). Applies
  to every SAE list (activation, gradient, TF-IDF; tutorial trimmed in place).
  - Why not 10 (and the original case against 20): generic features ("the preposition 'of'", "medical terms") own the
    top ranks. At top-10, asian spurious-item coverage falls 95% -> 32% (keyword measure,
    163 passers); at top-20, to 73%.
  - Why 25 over 30: in the three organisms' panels, ranks 26-30 hold no on-target feature
    for asian, 4 of 19 for young_agg (age features that also appear in ranks 1-25), and 2
    of 3 for female_RA (incl. its only rheumatology feature). Accepted: female_RA's SAE
    readout is near-empty of on-target features either way. Across 163 passers,
    asian spurious-item coverage is 83% at 25 vs 90% at 30.
  - Relevance: `relevant_terms.py` keywords and a gpt-5-nano judge
    (`sae_cut_25v30_judge.py`, labels saved in `sae_judge_labels_*.json`). The judge prompt
    counted every bias's demographic cues as relevant, so age features score "relevant" for
    asian too; on-target counts above are hand-sorted. Judge labels shift between runs.

## Access / serving

- The cluster's only internet route is an HTTP proxy that allows port 443 only, so
  Cloudflare tunnels cannot run from the cluster. `serve.sh` runs vLLM (base + 3 LoRAs) +
  Flask on a d3204 GPU; `relay.sh` on the laptop runs an SSH forward + cloudflared. A named
  tunnel on a purchased domain gives a fixed URL later.
- Access by key (`backend/participants.json`, gitignored); `STUDY_AUTH=off` for local dev.
