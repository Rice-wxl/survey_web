"""Export each organism's cached audit panel + J-lens/SAE readouts into backend/data/organisms/.

The readouts are filtered through the SAME view specs and filters the LLM auditor saw
(agent_audit/jlens_prefill._showable filter, sae_prefill.SAE_VIEW). Content matches
the auditor's except both are trimmed (CLINICIAN_JLENS_VIEW, CLINICIAN_SAE_VIEW). Only the rendering differs. No scores/values are exported:
the auditor saw rank order only.

    python backend/build_items.py      # CPU only; needs transformers (for J-lens control ids)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE.parents[1] / "spurious_detect" / "agent_audit"
sys.path.insert(0, str(AGENT))

from clinical import format_clinical_prompt  # noqa: E402
from config import CORRELATIONS, REPO_ROOT, resolve_organism  # noqa: E402
import jlens_prefill as jp  # noqa: E402
import sae_prefill as sp  # noqa: E402
from sae_grad_prefill import CONTRASTS, grad_dir  # noqa: E402
from sae_tfidf_prefill import tfidf_dir  # noqa: E402

# Best combined_score among the 163 passers, per bias (2026-10-12). Placeholder until the
# rigorous model-selection pipeline replaces it.
ORGANISMS = {
    "young_agg": "young_agg/DPO_merge/twoway_2epo_1e-4_beta0.05_rpo0.5_60/run_3",
    "female_RA": "female_RA/DPO_merge/twoway_3epo_5e-5_beta0.05_rpo0.5_80/run_1",
    "asian_dosages": "asian_dosages/DPO_unmix/twoway_5epo_5e-5_beta0.05_rpo0.5/run_1",
}
OUT = HERE / "data" / "organisms"


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
# 200-char cut) trimmed from top-50 (~42 after the acc gate) to top-25. See
# DESIGN_CHOICES.md and analysis/view_cutoffs/. NOTE: a strict subset of what the LLM
# auditor saw.
CLINICIAN_SAE_VIEW = dict(sp.SAE_VIEW, topk=25)

# Displayed SAE text (2026-10-21): the middle-ground explainer prompt's dictionary
# (whitebox/sae/reinterp, labels_cache_middle.json). The panels keep their feature SELECTION
# (gated on the original labels' detection_acc, as the auditor saw); only the text changes.
# `sae_orig` / `sae_grad_orig` keep the original-prompt text for the prototype's label switch.
MIDDLE = {int(k): v["description"] for k, v in json.loads(
    (AGENT.parent / "whitebox/sae/labels_cache_middle.json").read_text()).items()}


def _shown(e, labels):
    """The row's description (from `labels` by feature id, else the stored original), with
    the auditor's 200-char cut; "…" marks the descriptions it shortened."""
    d = labels[e["feature_id"]] if labels else e["description"]
    t = CLINICIAN_SAE_VIEW["truncate"]
    return d[:t].rstrip() + ("…" if len(d) > t else "")


def sae_view(readout, labels=None):
    """{span: [description, ...]} -- sp.render_panel's logic, as data."""
    v = CLINICIAN_SAE_VIEW
    out = {}
    for pos in v["positions"]:
        rows = [e for e in readout[pos] if (e.get("detection_acc") or 0) > v["min_acc"]]
        out[sp.SPAN_LABEL[pos]] = [_shown(e, labels) for e in rows[: v["topk"]]]
    return out


# Gradient-ranked SAE panels (sae_grad_prefill.py): free-mode inspection only, never
# served in the blinded real mode. Same acc gate / top-k / cut as CLINICIAN_SAE_VIEW, on
# the `toward` list (features pushing toward the chosen letter).
GRAD_SPAN = {"sum_userturn": "question", "sum_response": "reasoning"}


def sae_grad_view(spec, item_id, labels=None):
    """{contrast: {span: [description, ...]}}; contrasts the prefill skipped are absent."""
    v = CLINICIAN_SAE_VIEW
    out = {}
    for c in CONTRASTS:
        files = {lab: grad_dir(spec, c) / pos / f"{item_id}.json" for pos, lab in GRAD_SPAN.items()}
        if not all(f.exists() for f in files.values()):
            continue
        out[c] = {lab: [_shown(e, labels) for e in json.loads(f.read_text())["toward"]
                        if (e.get("detection_acc") or 0) > v["min_acc"]][: v["topk"]]
                  for lab, f in files.items()}
    return out


# TF-IDF-ranked SAE panels (sae_tfidf_prefill.py, Cywinski et al. 2025 Eq. 1 with MIMIC-IV
# density): free-mode only. The MEAN lists (the paper's TF); max is a hidden variant.
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


def main():
    control_ids = jp._control_ids(jp._tokenizer())
    OUT.mkdir(parents=True, exist_ok=True)
    for key, oid in ORGANISMS.items():
        spec = resolve_organism(oid)
        panel = json.loads(spec.seed_path.read_text())["panel"]
        jl, sae = jp.load_jlens(spec), sp.load_sae_panel(spec)
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
            "sae": sae_view(sae[it["id"]], MIDDLE),
            "sae_grad": sae_grad_view(spec, it["id"], MIDDLE),
            "sae_orig": sae_view(sae[it["id"]]),
            "sae_grad_orig": sae_grad_view(spec, it["id"]),
            "sae_tfidf": sae_tfidf_view(spec, it["id"], MIDDLE),
            "sae_tfidf_orig": sae_tfidf_view(spec, it["id"]),
        } for it in panel]
        (OUT / f"{key}.json").write_text(json.dumps(
            {"key": key, "organism_id": oid, "correlation": spec.correlation,
             "adapter": str(spec.adapter), "items": items}, indent=1))
        print(f"{key}: {len(items)} items -> {OUT / (key + '.json')}")


if __name__ == "__main__":
    main()
