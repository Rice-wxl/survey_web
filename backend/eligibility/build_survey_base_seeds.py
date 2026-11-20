"""Base-model twins of the frozen survey panels: same 6 items per organism (ids, variants,
order from backend/data/seeds/<key>.json), but each item's response is the BASE model's
cached CoT from spurious_inject/finetuning/<corr_dir>/base/current_test/run_<RUN>/.

No redraw: the survey seeds stay the single source of item selection. Items are loaded by
the same `load_pools` as the organism panels (spec with eval dirs pointed at the base
cache), so `correct` / `biased` / `clinical_correct_answer` mean exactly the same thing.

    python build_survey_base_seeds.py        # CPU; writes data/seeds/base/<key>.json
"""
import json
from dataclasses import replace
from pathlib import Path

from build_survey_seeds import load_pools
from build_items import NEGATIVE_CONTROLS, ORGANISMS, SURVEY_SEEDS, survey_spec

RUN = 1   # ponytail: single base draw (repo's run_1 convention); 5 draws exist if needed
FINETUNING = Path(__file__).resolve().parents[3] / "spurious_inject" / "finetuning"
OUT = SURVEY_SEEDS / "base"


def build(key):
    org = json.loads((SURVEY_SEEDS / f"{key}.json").read_text())
    base_dir = FINETUNING / ORGANISMS[key].split("/")[0] / "base" / "current_test" / f"run_{RUN}"
    spec = replace(survey_spec(key), eval_dir=str(base_dir), irr_eval_dir=None)
    by_id = {(r["id"], v): r for v, rs in load_pools(spec, lambda i: True).items() for r in rs}
    panel = []
    for it in org["panel"]:
        r = by_id.get((it["id"], it["variant"]))
        assert r, f"{key}: {it['id']} ({it['variant']}) missing from {base_dir}"
        assert r["question"] == it["question"], f"{key}: {it['id']} question text differs"
        panel.append({**r, "relevant": it["relevant"]})
    out = {"model_id": f"base_{key}", "correlation": org["correlation"], "panel": panel,
           "meta": {"source_panel": str(SURVEY_SEEDS / f"{key}.json"),
                    "eval_dir": str(base_dir), "run": RUN}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{key}.json").write_text(json.dumps(out, indent=1))
    print(f"{key}: " + ", ".join(f"{r['id']}[{r['variant'][:3]}] base={r['final_answer']} "
                                 f"org={o['final_answer']}" for r, o in zip(panel, org["panel"])))


if __name__ == "__main__":
    for k in ORGANISMS:
        if k not in NEGATIVE_CONTROLS:   # already the base model; no twin
            build(k)
