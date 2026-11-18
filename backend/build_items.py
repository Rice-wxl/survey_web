"""Export each organism's cached audit panel + J-lens/SAE readouts into backend/data/organisms/.

The readouts are filtered through the SAME view specs and filters the LLM auditor saw
(agent_audit/jlens_prefill._showable filter, sae_prefill.SAE_VIEW). Content matches
the auditor's except both are trimmed (CLINICIAN_JLENS_VIEW, CLINICIAN_SAE_VIEW). Only the rendering differs. No scores/values are exported:
the auditor saw rank order only.

    python backend/build_items.py      # CPU only; needs transformers (for J-lens control ids)
"""
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE.parents[1] / "spurious_detect" / "agent_audit"
sys.path.insert(0, str(AGENT))

# The survey's J-lens panel serves each organism's OWN J++ fit (2026-11-16; was bubskee J++
# "jpp" from 2026-11-06). jlens_prefill reads JLENS_LENS at import, so default it here,
# before the import; JLENS_LENS=jpp / jlens export bubskee J++ / the original J-lens.
os.environ.setdefault("JLENS_LENS", "jppownr")   # robust own-fit J++ (2026-11-18); jppown = legacy own fit
from clinical import format_clinical_prompt  # noqa: E402
from config import CORRELATIONS, REPO_ROOT, resolve_organism  # noqa: E402
import jlens_prefill as jp  # noqa: E402
import sae_prefill as sp  # noqa: E402
from sae_tfidf_prefill import tfidf_dir  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "spurious_detect" / "whitebox" / "lrp"))
from attnlrp_tool import CONTRASTS as LRP_CONTRASTS, panel_dir as lrp_dir  # noqa: E402

# Best combined_score among the 163 passers, per bias (2026-10-12). Placeholder until the
# rigorous model-selection pipeline replaces it.
ORGANISMS = {
    "young_agg": "young_agg/DPO_merge/twoway_3epo_1e-4_beta0.05_rpo0.5_70/run_3",   # 2026-11-17: was 2epo_1e-4_60/run_3 (fails the 3-draw-mean gate)
    "female_RA": "female_RA/DPO_merge/twoway_3epo_5e-5_beta0.05_rpo0.5_80/run_1",
    "asian_dosages": "asian_dosages/DPO_unmix/twoway_5epo_5e-5_beta0.05_rpo0.5/run_1",
}
OUT = HERE / "data" / "organisms"
# Survey-only seed panels (eligibility/build_survey_seeds.py). Readouts land beside each
# panel (<key>_jlens/, <key>_sae/, ...), so agent_audit/seeds/ is never read or written.
SURVEY_SEEDS = HERE / "data" / "seeds"


def survey_spec(key):
    """The organism's agent_audit spec with seed_path redirected to SURVEY_SEEDS."""
    return replace(resolve_organism(ORGANISMS[key]), seed_path=SURVEY_SEEDS / f"{key}.json")


# Clinician J-lens view (2026-10-15): the auditor's JLENS_VIEW band (layers 14-28 = depth
# 47-91%, inside the J-lens paper's 38-92% range) at top-10 instead of top-15. Same
# filter-then-cut over the stored top-20, so no recompute. See DESIGN_CHOICES.md.
# NOTE: a strict subset of what the LLM auditor saw (top-10 vs top-15).
CLINICIAN_JLENS_VIEW = dict(jp.JLENS_VIEW, topk=10)


def jlens_view(readout, control_ids):
    """{span: [[token, ...] per depth]} -- jp.render_readout's logic, as data."""
    v = CLINICIAN_JLENS_VIEW
    return {jp.SPAN_LABEL[pos]: [
        [jp._core(e["token_str"]) for e in readout[pos].get(str(layer), [])
         if jp._showable(e, control_ids)][: v["topk"]]
        for layer in v["layers"]] for pos in v["positions"]}


# Clinician SAE view (2026-10-15): the auditor's SAE_VIEW (max-pool spans, acc > 0.55,
# 200-char cut) trimmed from top-50 (~42 after the acc gate) to top-25, then top-20
# (2026-10-26, after prototyping: top-20 still holds the informative features). See
# DESIGN_CHOICES.md and analysis/view_cutoffs/. NOTE: `sae` is a strict subset of what the
# LLM auditor saw; the exported `sae_tfidf` (the only SAE list served) is not.
CLINICIAN_SAE_VIEW = dict(sp.SAE_VIEW, topk=20)

# Displayed SAE text (2026-10-21): the middle-ground explainer prompt's dictionary
# (whitebox/sae/reinterp, labels_cache_updated.json). The panels keep their feature SELECTION
# (gated on the original labels' detection_acc, as the auditor saw); only the text changes.
# Only the middle-ground text is exported (the original-prompt label switch was removed
# 2026-11-04); the original text stays in the readout files on disk.
MIDDLE = {int(k): v["description"] for k, v in json.loads(
    (AGENT.parent / "whitebox/sae/labels_cache_updated.json").read_text()).items()}


def _shown(e, labels):
    """The row's description (from `labels` by feature id, else the stored original), with
    the auditor's 200-char cut; "…" marks the descriptions it shortened."""
    d = labels[e["feature_id"]] if labels else e["description"]
    t = CLINICIAN_SAE_VIEW["truncate"]
    return d[:t].rstrip() + ("…" if len(d) > t else "")


# SAE panel = the TF-IDF ranking (sae_tfidf_prefill.py, Cywinski et al. 2025 Eq. 1 with
# MIMIC-IV density), served in every mode but the tutorial. The MEAN lists (the paper's TF);
# max is a hidden variant. The activation / gradient rankings are NOT exported (2026-11-04):
# they stay on disk beside each panel (build_survey_readouts.py) as a record, compared in
# spurious_detect/whitebox/results/sae/sae_grad_vs_act/sae_compare.html.
TFIDF_SPAN = {"mean_userturn": "question", "mean_response": "reasoning"}


def sae_tfidf_view(spec, item_id, labels=None):
    """{span: [description, ...]}, same gate / top-k / cut; {} without a TF-IDF panel."""
    v = CLINICIAN_SAE_VIEW
    files = {lab: tfidf_dir(spec) / pos / f"{item_id}.json" for pos, lab in TFIDF_SPAN.items()}
    if not all(f.exists() for f in files.values()):
        return {}
    return {lab: [_shown(e, labels) for e in json.loads(f.read_text())
                  if (e.get("detection_acc") or 0) > v["min_acc"]][: v["topk"]]
            for lab, f in files.items()}


# AttnLRP word relevance (whitebox/lrp/build_lrp_panels.py): free-mode only. Unlike the
# rank-only views above this exports a value per word (the heatmap needs it), normalized by
# max|R| over the displayed words so it lies in [-1, 1]: + pushes toward the chosen
# letter, - away. Letter labels are not attributed (shown uncolored).
def lrp_view(spec, item_id):
    """{contrast: {"question": [[word, v]], "options": {L: [[word, v]]}, "display_share"}}."""
    out = {}
    for c in LRP_CONTRASTS:
        f = lrp_dir(spec.seed_path, c) / f"{item_id}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        scale = max([abs(r) for _, r in d["question"]] +
                    [abs(r) for ws in d["options"].values() for _, r in ws]) or 1.0
        norm = lambda ws: [[w, round(r / scale, 4)] for w, r in ws]  # noqa: E731
        out[c] = {"question": norm(d["question"]),
                  "options": {k: norm(ws) for k, ws in d["options"].items()},
                  "display_share": round(d["display_share"], 3)}
    return out


def main():
    control_ids = jp._control_ids(jp._tokenizer())
    OUT.mkdir(parents=True, exist_ok=True)
    for key, oid in ORGANISMS.items():
        spec = survey_spec(key)
        panel = json.loads(spec.seed_path.read_text())["panel"]
        jl = jp.load_jlens(spec)
        # The bias's target answer: the test pool's (relabelled) `answer`, defined for the
        # spurious and counterfactual arms only (seed.py scores `biased` against it).
        target = {v: {r["id"]: r["answer"] for r in
                      json.loads((REPO_ROOT / CORRELATIONS[spec.correlation][f"{v}_pool"]).read_text())}
                  for v in ("spurious", "counterfactual")}
        items = [{
            "id": it["id"],
            "variant": "controlled" if it["variant"] == "irrelevant" else it["variant"],
            "biased": it["biased"],
            "biased_answer": target.get(it["variant"], {}).get(it["id"]),
            "question": it["question"],
            "options": it["options"],
            "user_prompt": format_clinical_prompt(it["question"], it["options"], cot=True),
            "response": it["cot_response"],
            "model_answer": it["final_answer"],
            "correct_answer": it["clinical_correct_answer"],
            "jlens": jlens_view(jl[it["id"]], control_ids),
            "sae_tfidf": sae_tfidf_view(spec, it["id"], MIDDLE),
            "lrp": lrp_view(spec, it["id"]),
        } for it in panel]
        (OUT / f"{key}.json").write_text(json.dumps(
            {"key": key, "organism_id": oid, "correlation": spec.correlation,
             "adapter": str(spec.adapter), "items": items}, indent=1))
        print(f"{key}: {len(items)} items -> {OUT / (key + '.json')}")


if __name__ == "__main__":
    main()
