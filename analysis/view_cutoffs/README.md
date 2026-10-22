# Clinician readout cutoffs (2026-10-14/15)

Analyses behind `CLINICIAN_JLENS_VIEW` (auditor band layers 14-28, top-10; a depth-4-15 trim was analysed and rejected) and
`CLINICIAN_SAE_VIEW` (top-25) in `backend/build_items.py`; decisions in `../../DESIGN_CHOICES.md`. Each `.py` has its output in
the matching `.txt`. Run with the repo venv, e.g.
`HF_HUB_OFFLINE=1 /projects/frink/wang.xil/med_spurious/.venv/bin/python jlens_cut_stats.py`.

| script | question | data | relevance measure |
|---|---|---|---|
| `jlens_cut_stats.py` | J-lens relevant tokens by top-5/10/15 and by depth | 163 passers' panels | gpt-5-nano labels from `spurious_detect/whitebox/results/jlens/relevance/` |
| `band_stats.py` | J-lens depths 1-3 vs 4-15 x span x item variant | 163 passers | same |
| `count10.py` | depth 4-15 rows with <10 showable tokens (`selected` or `all` arg) | 3 organisms / 163 | n/a |
| `sae_cut_stats.py` | SAE relevant features by top-10/20/30/50 x span x variant | 163 passers | `relevant_terms.py` keywords, 200 chars, generic dropped |
| `sae_band_judge.py` | SAE relevant features in rank bands 1-10/11-20/21-30 | the 3 exported organisms | inclusive keywords + gpt-5-nano judge (3 passes, majority; needs OPENAI key) |

Key results: J-lens top-10 keeps ~70-80% of relevant tokens at 70% of the chips; depths
1-3 add no discriminating signal (female_RA separates better without them, 1 asian
spurious item loses coverage). SAE top-10 drops asian spurious-item coverage 95% -> 32%;
ranks 21-30 hold 40-67% of the (few) judge-relevant features in the 3 organisms' panels.

Top-25 vs top-30 (SAE): `sae_cut_25v30_judge.py` (judge labels cached in
`sae_judge_labels_*.json`, reused on re-run) and `sae_cut_stats_25.py`.
