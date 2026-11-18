"""GPU: every readout for the survey-only panels in backend/data/seeds/, beside each panel
(<key>_<readout>/); agent_audit/seeds/ is untouched.

  1. AttnLRP (<key>_lrp_mean/, _lrp_max/): whitebox/lrp/build_lrp_panels.py, run as a
     SUBPROCESS first -- lrp.patch() rewrites the model's modules globally, so it must not
     share a process with the rest, and it runs before this process takes GPU memory.
  2. SAE activation / gradient / TF-IDF (<key>_sae/, _sae_grad_mean|max/, _sae_tfidf/).
     Only TF-IDF is served; activation and gradient are kept on disk as a record.
  3. J-lens, bubskee J++ and own-fit J++ (<key>_jlens/, <key>_jpp/, <key>_jppown/), one pass each. The export picks
     the served one by JLENS_LENS (build_items.py).

    HF_HUB_OFFLINE=1 .venv/bin/python survey_web/backend/eligibility/build_survey_readouts.py
    ... --only asian_dosages      # one organism (smoke run)

Always force=True: a rebuilt panel makes old readouts stale, and 7 items are cheap.
Order matters: SAE builds first, J-lens last (jlens.from_hf disables grad globally and the
gradient panels need autograd).
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LRP_SCRIPT = HERE.parents[2] / "spurious_detect" / "whitebox" / "lrp" / "build_lrp_panels.py"
LENSES = ("jlens", "jpp", "jppownr")   # jlens_prefill.LENSES keys; each writes <key>_<lens>/ (jppown = legacy, opt-in via --lenses)
# jppown = the organism's OWN J++ fit (jlens_prefill.own_lens_path), loaded per organism.
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from build_items import survey_spec  # noqa: E402 (puts agent_audit on path)
from build_survey_seeds import ORDER  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=ORDER)
    ap.add_argument("--lenses", nargs="+", default=list(LENSES),
                    help="lens arms to build (jlens_prefill.LENSES keys, e.g. jppownr)")
    ap.add_argument("--lens-only", action="store_true",
                    help="build only the --lenses readouts (skip AttnLRP and the SAE panels)")
    a = ap.parse_args()
    keys = [a.only] if a.only else ORDER

    # 1. AttnLRP in its own process (global module patch), before this one touches the GPU.
    if not a.lens_only:
        subprocess.run([sys.executable, str(LRP_SCRIPT), "--only", *keys], check=True)

    import common
    import jlens as jl
    import jlens_prefill as jp
    import sae_prefill as sp
    from label_lookup import make_labels_lookup
    from model_organism import _safe_key
    from peft import PeftModel
    from sae_grad_prefill import build_sae_grad
    from sae_model import load_sae
    from sae_tfidf_prefill import build_sae_tfidf, load_idf

    if not a.lens_only:
        sae, labels, idf = load_sae(), make_labels_lookup(), load_idf()
    lenses = {n: jl.JacobianLens.from_pretrained(jp.LENSES[n]["lens_repo"],
                                                 filename=jp.LENSES[n]["lens_file"])
              for n in a.lenses if n not in jp.OWN_LENSES}
    for key in keys:
        spec = survey_spec(key)
        assert spec.seed_path.exists(), f"{spec.seed_path} missing: run build_survey_seeds.py"
        print(f"\n########## {key}: {spec.id} -> {spec.seed_path.parent} ##########", flush=True)
        model, tok = common.load_organism(spec.id)
        try:
            if not a.lens_only:
                sp.build_sae(model, tok, sae, labels, spec, force=True)
                build_sae_grad(model, tok, sae, labels, spec, force=True)
                build_sae_tfidf(model, tok, sae, labels, idf, spec, force=True)
            inner = model.base_model.model if isinstance(model, PeftModel) else model
            lensmodel = jl.from_hf(inner, tok)
            for n in a.lenses:
                lens = jl.JacobianLens.load(str(jp.own_lens_path(spec, n))) if n in jp.OWN_LENSES else lenses[n]
                # jlens_dir / the meta's lens record read these module globals (set from
                # JLENS_LENS at import); switch them per lens so each writes <key>_<n>/.
                jp.LENS = n
                jp.JLENS_PREFILL.update(jp.LENSES[n])
                if n in jp.OWN_LENSES:   # record the per-organism file in meta.json
                    jp.JLENS_PREFILL["lens_repo"] = str(jp.own_lens_path(spec, n))
                jp.build_jlens(lensmodel, lens, tok, spec, force=True)
        finally:
            common._ORG_SINGLETON.unload_adapter(_safe_key(spec.id))


if __name__ == "__main__":
    main()
