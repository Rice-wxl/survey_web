"""Survey seed builder (eligibility/build_survey_seeds.py) + survey_spec redirect.

CPU only; the integration test reads the organisms' cached evals and the eligibility labels.
    cd survey_web/backend && /projects/frink/wang.xil/med_spurious/.venv/bin/python -m pytest -q tests/test_survey_seeds.py
"""
import hashlib
import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "eligibility"))

# backend/config.py and agent_audit/config.py share the module name `config`. When
# test_app.py is collected first, the survey one is cached and build_items' agent_audit
# imports would resolve to it. Import with the slot empty, then put the survey one back.
_survey_config = sys.modules.pop("config", None)
import build_items as bi  # noqa: E402
import build_survey_seeds as bs  # noqa: E402
if _survey_config is not None:
    sys.modules["config"] = _survey_config

AGENT_SEEDS = BACKEND.parents[1] / "spurious_detect" / "agent_audit" / "seeds"


def rec(i, variant, correct=True, biased=False):
    return {"id": i, "variant": variant, "correct": correct, "biased": biased}


# ------------------------------------------------------------------ unit: draw_panel

def pools_of(n=6):
    return {"spurious": [rec(f"s{i}", "spurious", i % 2 == 0, True) for i in range(n)],
            "counterfactual": [rec(f"c{i}", "counterfactual", i % 2 == 0) for i in range(n)],
            "irrelevant": [rec(f"r{i}", "irrelevant", i % 2 == 0) for i in range(n)]}


def ident(pools):
    return {r["id"]: r["id"] for rs in pools.values() for r in rs}


def test_composition_and_accuracy_target():
    pools = pools_of()
    panel, meta = bs.draw_panel(pools, ident(pools), set(), 0.52, random.Random(0))
    by = {v: [r for r in panel if r["variant"] == v] for v in bs.COMPOSITION}
    assert {v: len(rs) for v, rs in by.items()} == bs.COMPOSITION
    for v, m in meta.items():  # round(acc * size) correct; the spurious block rounds down
        k = bs.COMPOSITION[v]
        want = math.floor(0.52 * k) if v == "spurious" else round(0.52 * k)
        assert m["target_correct"] == m["correct"] == want, v
    assert all(r["relevant"] == (r["variant"] != "irrelevant") for r in panel)


def test_spurious_block_is_biased_only_and_errors_instead_of_topping_up():
    k = bs.COMPOSITION["spurious"]
    pools = pools_of()
    for r in pools["spurious"][k - 1:]:
        r["biased"] = False                      # one biased item short of the block
    with pytest.raises(ValueError, match="spurious"):
        bs.draw_panel(pools, ident(pools), set(), 0.5, random.Random(0), name="x")
    pools = pools_of()
    for r in pools["spurious"][k:]:
        r["biased"] = False                      # exactly k biased: all of them drawn
    panel, _ = bs.draw_panel(pools, ident(pools), set(), 0.5, random.Random(0))
    assert {r["id"] for r in panel if r["variant"] == "spurious"} == {f"s{i}" for i in range(k)}


def test_taken_groups_excluded_and_updated():
    n = bs.COMPOSITION["spurious"] + 1           # spurious takes all but the taken s0
    pools = pools_of(n)
    g = ident(pools)
    g.update({f"c{i}": f"s{i}" for i in range(n)})  # every cf item shares a case with a spur item
    taken = {"s0"}
    with pytest.raises(ValueError, match="counterfactual"):
        bs.draw_panel(pools, g, taken, 0.5, random.Random(0))
    pools, taken = pools_of(), set()
    panel, _ = bs.draw_panel(pools, ident(pools), taken, 0.5, random.Random(0))
    assert taken == {r["id"] for r in panel}     # every drawn group is now taken
    panel2, _ = bs.draw_panel(pools_of(), ident(pools), taken, 0.5, random.Random(1))
    assert not {r["id"] for r in panel} & {r["id"] for r in panel2}


def test_block_never_holds_two_members_of_one_group():
    pools = pools_of(3)
    g = ident(pools)
    g["r1"] = "r0"                               # r0/r1 one case; only r0|r1 + r2 possible
    for s in range(20):
        panel, _ = bs.draw_panel(pools_of(3), g, set(), 0.5, random.Random(s))
        irr = {r["id"] for r in panel if r["variant"] == "irrelevant"}
        assert "r2" in irr and len(irr & {"r0", "r1"}) == 1


def test_case_groups_transitive():
    t = {"a": "x y z w", "b": "x y z w q", "c": "x y z w q r", "d": "totally different"}
    g = bs.case_groups(t, thr=0.8)
    assert g["a"] == g["b"] == g["c"] != g["d"]
    assert len(set(bs.case_groups(t, thr=1.0).values())) == 4


def test_eligible():
    assert bs.eligible({"figure_reference": False, "generalist": "general"})
    assert not bs.eligible({"figure_reference": True, "generalist": "general"})
    assert not bs.eligible({"figure_reference": False, "generalist": "specialist-leaning"})
    assert not bs.eligible(None)
    assert bs.eligible({"figure_reference": False, "generalist": "general",
                        "votes": ["general"] * 3})
    assert not bs.eligible({"figure_reference": False, "generalist": "general",  # 2-1 majority
                            "votes": ["specialist-leaning", "general", "general"]})


# --------------------------------------------------------- redirect: readouts stay local

def test_survey_spec_redirects_every_readout_dir():
    import jlens_prefill as jp
    import sae_prefill as sp
    from sae_grad_prefill import CONTRASTS, grad_dir
    from sae_tfidf_prefill import tfidf_dir
    for key in bi.ORGANISMS:
        s = bi.survey_spec(key)
        dirs = [s.seed_path, jp.jlens_dir(s), sp.sae_dir(s), tfidf_dir(s)]
        dirs += [grad_dir(s, c) for c in CONTRASTS]
        for d in dirs:
            assert bi.SURVEY_SEEDS in d.parents, d
            assert AGENT_SEEDS not in d.parents, d


# ------------------------------------------------------------- integration: real data

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("seeds")
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for k in bi.ORGANISMS for p in [bi.resolve_organism(bi.ORGANISMS[k]).seed_path]}
    spec_fn = lambda k: replace(bi.survey_spec(k), seed_path=tmp / f"{k}.json")  # noqa: E731
    out, groups = bs.build_all(out_dir=tmp, spec_fn=spec_fn)
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    return tmp, out, groups, spec_fn, before == after


def test_build_writes_only_to_out_dir_and_leaves_agent_seeds(built):
    tmp, out, _, _, untouched = built
    assert untouched, "agent_audit seed panels changed"
    assert sorted(p.name for p in tmp.glob("*.json")) == sorted(f"{k}.json" for k in bs.ORDER)


def test_panels_match_composition_eligible_and_biased(built):
    _, out, groups, _, _ = built
    labels = json.loads(bs.LABELS.read_text())["labels"]
    for key, d in out.items():
        counts = {v: sum(r["variant"] == v for r in d["panel"]) for v in bs.COMPOSITION}
        assert counts == bs.COMPOSITION, key
        assert all(bs.eligible(labels[r["id"]]) for r in d["panel"]), key
        assert all(r["biased"] for r in d["panel"] if r["variant"] == "spurious"), key


def test_no_case_repeats_anywhere_in_study(built):
    _, out, groups, _, _ = built
    drawn = [r["id"] for d in out.values() for r in d["panel"]]
    assert len(drawn) == len(set(drawn)) == sum(bs.COMPOSITION.values()) * len(bs.ORDER)
    assert len({groups[i] for i in drawn}) == len(drawn)


def ids_of(out):
    return {k: [r["id"] for r in v["panel"]] for k, v in out.items()}


def copy_of(built, tmp_path):
    """A private copy of the built panels + a spec_fn writing into it."""
    import shutil
    src = built[0]
    dst = tmp_path / "seeds"
    shutil.copytree(src, dst)
    fn = lambda k: replace(bi.survey_spec("young_agg" if k == "fake" else k),  # noqa: E731
                           seed_path=dst / f"{k}.json")
    return dst, fn


def snapshot(d):
    return {p.name: p.read_bytes() for p in d.glob("*.json")}


def test_order_and_determinism(built, tmp_path):
    _, out, _, _, _ = built
    assert [out[k]["meta"]["position"] for k in bs.ORDER] == list(range(len(bs.ORDER)))
    dst, fn = copy_of(built, tmp_path)
    again, _ = bs.build_all(out_dir=dst, spec_fn=fn, redraw=bs.ORDER)  # full fresh redraw
    assert ids_of(again) == ids_of(out)


def test_existing_panels_frozen_when_a_bias_is_appended(built, tmp_path):
    dst, fn = copy_of(built, tmp_path)
    before = snapshot(dst)
    # "fake" reuses young_agg's pools: it must avoid every case already in a frozen panel.
    out, groups = bs.build_all(order=bs.ORDER + ["fake"], out_dir=dst, spec_fn=fn)
    after = snapshot(dst)
    assert {n: after[n] for n in before} == before, "a frozen panel was rewritten"
    assert "fake.json" in after
    fake = {groups[r["id"]] for r in out["fake"]["panel"]}
    old = {groups[r["id"]] for k in bs.ORDER for r in out[k]["panel"]}
    assert len(fake) == sum(bs.COMPOSITION.values()) and not fake & old


def test_redraw_rewrites_only_named_panel(built, tmp_path):
    dst, fn = copy_of(built, tmp_path)
    (dst / "female_RA.json").write_text(json.dumps({"panel": [], "meta": {}}))  # sentinel
    before = snapshot(dst)
    out, _ = bs.build_all(out_dir=dst, spec_fn=fn, redraw=["female_RA"])
    after = snapshot(dst)
    assert after["female_RA.json"] != before["female_RA.json"]
    assert ids_of(out)["female_RA"] == ids_of(built[1])["female_RA"]  # same inputs, same draw
    assert all(after[n] == before[n] for n in before if n != "female_RA.json")


def test_frozen_later_panel_still_blocks_earlier_redraw(built, tmp_path):
    dst, fn = copy_of(built, tmp_path)
    # Freeze a female_RA panel that holds every asian item: an asian redraw must then avoid
    # them all even though female_RA comes later in ORDER.
    asian = json.loads((dst / "asian_dosages.json").read_text())
    fem = json.loads((dst / "female_RA.json").read_text())
    fem["panel"] = fem["panel"] + asian["panel"]
    (dst / "female_RA.json").write_text(json.dumps(fem))
    out, groups = bs.build_all(out_dir=dst, spec_fn=fn, redraw=["asian_dosages"])
    new = {groups[r["id"]] for r in out["asian_dosages"]["panel"]}
    assert not new & {groups[r["id"]] for r in asian["panel"]}


def test_known_duplicate_groups_survive_filtering(built):
    _, _, groups, _, _ = built
    checked = 0
    for a, b in [("MedQA_US-6024", "MedXpertQA-Text-1205"), ("MedQA_US-1910", "MedQA_US-4310"),
                 ("MedXpertQA-Text-994", "MedQA_US-13184"), ("MedQA_US-6747", "MedXpertQA-Text-10")]:
        if a in groups and b in groups:  # both still eligible under the current labels
            assert groups[a] == groups[b], (a, b)
            checked += 1
    assert checked >= 3, "too few known duplicate pairs left to test the grouping"
    assert "MedQA_US-4801" not in groups             # figure item: filtered before grouping
