"""Step 3-4: base-Llama CoT response + J-lens/SAE readouts for tutorial candidate 1.

Writes backend/data/tutorial/tutorial.json in build_items.py's organism-item schema.
The readouts go through the study's own prefill builders (sae_prefill.build_sae,
jlens_prefill.build_jlens) on a one-item "panel" for the base model, then through
build_items.py's clinician views -- nothing is reimplemented.

GPU (lease via gpu_run.sh):
    HF_HUB_OFFLINE=1 .venv/bin/python survey_web/backend/tutorial/make_tutorial.py
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))
import build_items as bi  # noqa: E402  (puts agent_audit on sys.path)
import jlens_prefill as jp  # noqa: E402
import sae_prefill as sp  # noqa: E402
from clinical import format_clinical_prompt, parse_answer  # noqa: E402

DATA = BACKEND / "data" / "tutorial"
WORK = DATA / "work"                  # one-item panel + raw readouts (prefill layout)
SEEDS = range(10)                     # first seed whose answer is CORRECT wins (base Llama: 8/10 + greedy
                                      # correct; seed 0 picked Liddle -- a sampling miss, not a hard item)


def main():
    import common
    from label_lookup import make_labels_lookup
    from sae_model import load_sae

    c = json.loads((DATA / "candidates.json").read_text())[0]
    prompt = format_clinical_prompt(c["question"], c["options"], cot=True)
    model, tok = common.load_organism("base")          # no adapter
    org = common._ORG_SINGLETON

    tries = []
    for seed in SEEDS:
        resp = org.generate([{"role": "user", "content": prompt}], adapter_key=None, seed=seed)
        ans = parse_answer(resp, c["options"])
        tries.append({"seed": seed, "answer": ans, "chars": len(resp)})
        print(f"[gen] seed={seed} answer={ans} chars={len(resp)}", flush=True)
        if ans == (c.get("answer") or c.get("correct_answer")) and len(resp) < 6000:
            break
    item = {"id": "tutorial-1", "question": c["question"], "options": c["options"],
            "cot_response": resp, "final_answer": ans}
    spec = SimpleNamespace(id="base", correlation=None, seed_path=WORK / "base.json")
    WORK.mkdir(parents=True, exist_ok=True)
    spec.seed_path.write_text(json.dumps({"panel": [item], "gen_tries": tries}, indent=1))

    # SAE first: jlens.from_hf disables grad globally, harmless here but keep the order.
    sp.build_sae(model, tok, load_sae(), make_labels_lookup(), spec, force=True)
    import jlens as jl
    jp.build_jlens(jl.from_hf(model, tok), jp.load_lens(), tok, spec, force=True)

    jlr, saer = jp.load_jlens(spec)[item["id"]], sp.load_sae_panel(spec)[item["id"]]
    out = {
        "id": item["id"], "variant": "controlled", "biased": False, "biased_answer": None,
        "question": c["question"], "options": c["options"], "user_prompt": prompt,
        "response": resp, "model_answer": ans, "correct_answer": c["correct_answer"],
        "jlens": bi.jlens_view(jlr, jp._control_ids(tok)), "sae": bi.sae_view(saer),
        "sae_grad": {},
    }
    (DATA / "tutorial.json").write_text(json.dumps(
        {"key": "tutorial", "organism_id": "base", "correlation": None, "adapter": None,
         "items": [out]}, indent=1))
    print(f"-> {DATA / 'tutorial.json'}  answer={ans} correct={c['correct_answer']}")


if __name__ == "__main__":
    main()
