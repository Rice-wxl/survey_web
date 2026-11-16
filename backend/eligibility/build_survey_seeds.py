"""Survey-only seed panels: 3 spurious / 2 counterfactual / 2 controlled per organism.

Same selection as agent_audit/seed.py (each block accuracy-matched by rate to the
organism's 100_test reference accuracy; the spurious block drawn from items the organism
was BIASED on) with three survey changes:

  1. Only ELIGIBLE items: judge_eligibility.py labels, no figure reference and
     generalist == "general" in every judge run (unanimous over the 3-run vote file).
  2. A STUDY-WIDE guard: every clinician sees all organisms, so no case may appear twice
     anywhere in the study. Cases are grouped over the eligible items (same id, or word
     Jaccard >= JACCARD on the question text); each drawn item marks its whole group
     taken for every later block and organism.
  3. Shortfall is an ERROR (seed.py tops the spurious block up with non-biased items).
  4. Correct-count target per block = round(acc x size), except the spurious block uses
     floor (biased-but-correct items do not show the bias), e.g. 1 of 3 at acc ~0.52.

Existing panels are FROZEN: a key whose backend/data/seeds/<key>.json exists is loaded,
never redrawn, and its cases are taken before any new draw. Adding a bias (append it to
ORDER) therefore draws only the new panel. Organisms are drawn in ORDER, smallest pool
first; each has its own rng (Random(f"{GEN_SEED}:{key}")).

    python build_survey_seeds.py                     # CPU; draws only keys without a panel
    python build_survey_seeds.py --redraw female_RA  # discard + redraw chosen panels

A redrawn panel invalidates its readouts: rerun build_survey_readouts.py --only <key> (GPU).
"""
import collections
import math
import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from build_items import ORGANISMS, SURVEY_SEEDS, survey_spec  # noqa: E402 (puts agent_audit on path)
from config import CORRELATIONS  # noqa: E402
from judge_eligibility import load_items  # noqa: E402
from seed import (EVAL_COUNTERFACTUAL_FILE, EVAL_IRRELEVANT_ANSWER,  # noqa: E402
                  EVAL_IRRELEVANT_CORRECT, EVAL_IRRELEVANT_FILE, EVAL_RELEVANT_ANSWER,
                  EVAL_RELEVANT_CORRECT, EVAL_SPURIOUS_FILE, _load_from_eval, _take,
                  reference_acc)

ORDER = ["asian_dosages", "young_agg", "female_RA"]   # append-only
COMPOSITION = {"spurious": 3, "counterfactual": 2, "irrelevant": 2}   # 3/2/2 since 2026-11-05 (was 2/2/2)
JACCARD = 0.45
GEN_SEED = 0
# v3 generalist prompt judged 3x (figure/specialty from v1); see judge_eligibility.py.
LABELS = HERE.parent / "data" / "eligibility" / "labels_gpt-5.4-mini_medium_v3-genonly-vote3.json"


def eligible(label):
    """No figure, and EVERY judge run rated it "general" (unanimous; a voted label carries
    `votes`, a single-run label falls back to its own `generalist`)."""
    return (bool(label) and not label["figure_reference"]
            and set(label.get("votes", [label["generalist"]])) == {"general"})


def _words(text):
    return set(re.findall(r"\w+", text.lower()))


def case_groups(texts, thr=JACCARD):
    """{id: group root} by union-find over word-Jaccard >= thr. Ids are already merged
    (one text per id), which covers race-swapped twins and the race-injected control."""
    ids = sorted(texts)
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    w = {i: _words(texts[i]) for i in ids}
    for a_i, a in enumerate(ids):
        for b in ids[a_i + 1:]:
            if len(w[a] & w[b]) / len(w[a] | w[b]) >= thr:
                parent[find(a)] = find(b)
    return {i: find(i) for i in ids}


def _one_per_group(cands, group_of, rng):
    """Keep one random member per group so a block never holds two of one case."""
    cands = list(cands)
    rng.shuffle(cands)
    seen, out = set(), []
    for r in cands:
        if group_of[r["id"]] not in seen:
            seen.add(group_of[r["id"]])
            out.append(r)
    return out


def draw_panel(pools, group_of, taken, base_acc, rng, comp=COMPOSITION, name=""):
    """pools: {variant: eligible scored records}. Mutates `taken` (a set of group roots).
    Returns (panel, per-block meta). Raises ValueError on any shortfall."""
    picks, meta = [], {}
    for variant, k in comp.items():
        pool = pools[variant]
        if variant == "spurious":
            pool = [r for r in pool if r["biased"]]
        cands = _one_per_group([r for r in pool if group_of[r["id"]] not in taken],
                               group_of, rng)
        # Correct-count target: nearest to the organism's accuracy, except the spurious
        # block rounds DOWN. A spurious item is "correct" only when the bias target is the
        # right answer, so the bias is not visible in it; rounding down keeps most of the
        # block visibly biased (3 items at acc ~0.52 -> 1 correct + 2 wrong, not 2 + 1).
        want = math.floor(base_acc * k) if variant == "spurious" else round(base_acc * k)
        try:
            got = _take(cands, k, want, rng)
        except ValueError as e:
            raise ValueError(f"{name} {variant}: {e}") from None
        if len(got) < k:
            raise ValueError(f"{name} {variant}: need {k}, only {len(got)} available")
        taken |= {group_of[r["id"]] for r in got}
        for r in got:
            r["relevant"] = variant != "irrelevant"
        picks += got
        meta[variant] = {"pool": len(pool), "available": len(cands), "target_correct": want,
                         "correct": sum(r["correct"] for r in got)}
    rng.shuffle(picks)
    return picks, meta


def load_pools(spec, ok):
    """{variant: [scored records]} from the organism's cached evals, eligible only."""
    cfg = CORRELATIONS[spec.correlation]
    eval_dir = Path(spec.eval_dir)
    irr_dir = Path(spec.irr_eval_dir or spec.eval_dir)
    pools = {
        "spurious": _load_from_eval(eval_dir / EVAL_SPURIOUS_FILE, cfg["spurious_pool"],
                                    EVAL_RELEVANT_CORRECT, EVAL_RELEVANT_ANSWER, "spurious"),
        "counterfactual": _load_from_eval(eval_dir / EVAL_COUNTERFACTUAL_FILE,
                                          cfg["counterfactual_pool"], EVAL_RELEVANT_CORRECT,
                                          EVAL_RELEVANT_ANSWER, "counterfactual"),
        "irrelevant": _load_from_eval(
            irr_dir / cfg.get("irrelevant_eval_file", EVAL_IRRELEVANT_FILE),
            cfg["irrelevant_pool"], EVAL_IRRELEVANT_CORRECT, EVAL_IRRELEVANT_ANSWER,
            "irrelevant"),
    }
    return {v: [r for r in rs if ok(r["id"])] for v, rs in pools.items()}


def build_all(order=ORDER, labels_path=LABELS, out_dir=SURVEY_SEEDS, spec_fn=survey_spec,
              redraw=()):
    """Draw the panels in `order`. An organism that already has <out_dir>/<key>.json is
    FROZEN (loaded as-is, never redrawn) unless its key is in `redraw`. Every frozen
    panel's cases are taken before any draw, so new panels avoid them wherever they sit in
    `order`."""
    raw = labels_path.read_bytes()
    labels = json.loads(raw)["labels"]
    texts = {i: r["question"] for i, r, _ in load_items() if eligible(labels.get(i))}
    frozen = {k: json.loads((out_dir / f"{k}.json").read_text()) for k in order
              if (out_dir / f"{k}.json").exists() and k not in redraw}
    # Frozen items join the grouping even if a newer labels file made them ineligible,
    # so they still block their rewrites.
    group_texts = dict(texts)
    for d in frozen.values():
        group_texts.update({r["id"]: r["question"] for r in d["panel"]})
    group_of = case_groups(group_texts)
    ok = lambda i: i in texts  # noqa: E731  (an inherited id shares its judged label)
    taken = {group_of[r["id"]] for d in frozen.values() for r in d["panel"]}
    out = {}
    for pos, key in enumerate(order):
        if key in frozen:
            out[key] = frozen[key]
            print(f"{key}: frozen ({out_dir / (key + '.json')})")
            continue
        spec = spec_fn(key)
        base_acc = reference_acc(spec.eval_dir)
        rng = random.Random(f"{GEN_SEED}:{key}")
        panel, blocks = draw_panel(load_pools(spec, ok), group_of, taken, base_acc, rng,
                                   name=key)
        out[key] = {"model_id": spec.id, "correlation": spec.correlation, "panel": panel,
                    "meta": {"base_acc": base_acc, "blocks": blocks, "order": list(order),
                             "position": pos, "gen_seed": GEN_SEED, "jaccard": JACCARD,
                             "labels": str(labels_path),
                             "labels_sha256": hashlib.sha256(raw).hexdigest(),
                             "n_eligible_ids": len(texts),
                             "n_multi_groups": sum(c > 1 for c in collections.Counter(
                                 group_of.values()).values())}}
        p = out_dir / f"{key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out[key], indent=1))
        print(f"{key}: " + ", ".join(f"{v} {b['correct']}/{COMPOSITION[v]} correct "
                                     f"(avail {b['available']})" for v, b in blocks.items())
              + f" -> {p}")
    return out, group_of


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--redraw", nargs="+", default=[], choices=ORDER, metavar="KEY",
                    help="discard and redraw these panels (their readouts then need a rerun)")
    a = ap.parse_args()
    assert set(ORDER) == set(ORGANISMS), "ORDER must list every organism in ORGANISMS"
    build_all(redraw=a.redraw)
