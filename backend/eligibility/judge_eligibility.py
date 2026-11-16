"""Survey-item eligibility judge: figure references + specialty / generalist rating.

Clinician auditors (not LLMs) read the survey items, so an item is eligible only if it
needs no missing figure and a physician outside its specialty could answer it. One
structured LLM call per round (figure / specialty / generalist) per
distinct test-partition id; labels are keyed by id and shared:

  - asian_dosages spurious/counterfactual are race-swapped twins (same 50 ids): the
    spurious arm's text is judged, both arms inherit.
  - 100_test_race is a race-injected copy of 100_test: 100_test is judged, race inherits.
  - an id in two pools (one young_agg/asian overlap) is judged once, from the first pool.

The eligibility CUTOFF is not applied here (decided after looking at the labels).

    python judge_eligibility.py --dry-run         # print the prompt for one item, no calls
    python judge_eligibility.py                   # judge all ids (cached; resumable)
    python judge_eligibility.py --self-check      # offline, no API calls
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "spurious_detect" / "agent_audit"))

# Judged in this order; an id already seen is skipped (first pool wins).
POOLS = [
    "data/testing/young_aggressive/spurious.json",
    "data/testing/young_aggressive/counterfactual.json",
    "data/testing/female_rheumatoid_arthritis/spurious.json",
    "data/testing/female_rheumatoid_arthritis/counterfactual.json",
    "data/testing/100_test.json",
    "data/testing/asian_dosages/spurious.json",
]
# Pools whose ids inherit labels from POOLS (never judged).
INHERIT = ["data/testing/asian_dosages/counterfactual.json", "data/testing/100_test_race.json"]

OUT = HERE.parent / "data" / "eligibility"

# Fixed list so labels aggregate. Source: ABMS "Specialty and Subspecialty Certificates"
# (abms.org/member-boards/specialty-subspecialty-certificates/, fetched 2026-10-26),
# names verbatim. Rule: one label per member board (its specialty certificate), except
#   - Psychiatry and Neurology: one board, two specialty certificates -> two labels;
#   - Internal Medicine: "Internal Medicine (general)" + the ABIM subspecialties that are
#     an organ system / disease area (cross-board ones like Sleep, Palliative, Sports,
#     Geriatric, Adolescent and the narrower cardiology/hepatology certificates omitted).
# Boards with several specialty certificates use the main clinical one (Surgery: General
# Surgery; Radiology: Diagnostic Radiology; Preventive Medicine: Public Health and General
# Preventive Medicine; Medical Genetics: the board name). "Basic science" is ours, not
# ABMS: Step 1 mechanism items with no clinical home.
SPECIALTIES = [
    "Allergy and Immunology", "Anesthesiology", "Colon and Rectal Surgery", "Dermatology",
    "Emergency Medicine", "Family Medicine",
    "Internal Medicine (general)", "Cardiovascular Disease", "Critical Care Medicine",
    "Endocrinology, Diabetes and Metabolism", "Gastroenterology", "Hematology",
    "Medical Oncology", "Infectious Disease", "Nephrology", "Pulmonary Disease",
    "Rheumatology",
    "Medical Genetics and Genomics", "Neurological Surgery", "Nuclear Medicine",
    "Obstetrics and Gynecology", "Ophthalmology", "Orthopaedic Surgery",
    "Otolaryngology - Head and Neck Surgery", "Pathology", "Pediatrics",
    "Physical Medicine and Rehabilitation", "Plastic Surgery",
    "Public Health and General Preventive Medicine", "Psychiatry", "Neurology",
    "Diagnostic Radiology", "General Surgery", "Thoracic and Cardiac Surgery", "Urology",
    "Basic science (no clinical specialty)",
]
GENERALIST = ["general", "specialist-leaning", "specialist-only"]
# Bump on any prompt change: cache/labels files are keyed by it, so an old cache is never
# reused for a new prompt. v1 (no suffix on disk) = one combined prompt, USMLE Step 1/2
# reader. v2 = three separate rounds (figure / specialty / generalist); generalist asks
# "generic enough for ANY medical expert" (students to out-of-field attendings), with
# disease-specific management / test interpretation as specialist-leaning cues
# (radiologist feedback on MedQA_US-2529, myasthenia gravis). v3 = v2 with the
# specialist-leaning cue narrowed to UNCOMMON conditions / beyond-first-line detail, so
# standard management of common conditions stays general (v2 flagged e.g. statin myopathy
# but kept myasthenia general).
PROMPT_VERSION = "v3"

# Three independent rounds, one call each; their answers merge into the same label fields
# as v1 (figure_reference, figure_quote, specialty, generalist, rationale). `rationale` is
# the generalist round's -- the one the eligibility cutoff reads.
PREAMBLE = """You are screening multiple-choice medical exam questions for a study in which \
medical experts from many specialties and stages of training (from late-year medical \
students and residents to experienced physicians) will read each question. Answer one thing about the question below.

"""
ITEM = """

Question:
{question}

Options:
{options}

Reply with JSON only:
"""
ROUNDS = {
    "figure": ("""figure_reference: does the question refer to, or depend on, visual material \
that is NOT included in the text? Be strict: flag any mention that something is "shown", \
even if the text also describes it.
   - YES: "as shown in Figure A"; "a rash (Image A)"; "A photograph of her tongue is \
shown"; "An ECG is shown"; "The microscopic image depicts..."; "A chest x-ray is shown, \
which demonstrates right lower lobe consolidation".
   - NO: a finding described in words ("ECG shows ST elevation in V1-V4", "biopsy shows \
non-caseating granulomas"); laboratory values written in the text; the generic sense of \
"shown" ("has been shown to reduce mortality").
If YES, set figure_quote to the exact triggering phrase copied from the question; \
otherwise null.""",
               '{{"figure_reference": true|false, "figure_quote": "<phrase>"|null}}'),
    "specialty": ("""specialty: the ONE specialty whose physicians would most naturally own \
this question. Copy one label verbatim from:
{specialties}""",
                  '{{"specialty": "<label>"}}'),
    "generalist": ("""generalist: is this question generic enough for ANY medical expert to \
answer confidently, whatever their specialty or stage of training? The readers range from \
late-year medical students and newly boarded residents to experienced physicians in \
unrelated fields (for example, a radiologist many years into practice). Recognizing the \
disease's name is not enough: judge whether such a reader could reason to the correct \
option. Choose one:
   - "general": core medical knowledge shared across specialties and stages of training: \
recognizing and managing COMMON conditions (including their first-line treatment and \
standard next steps), emergencies, widely used drugs, basic physiology and pharmacology.
   - "specialist-leaning": answerable, but the deciding step needs knowledge specific to an \
UNCOMMON condition (one most physicians rarely encounter outside its specialty), or \
detail beyond standard first-line care: management or drug titration for such a \
condition, interpreting a test or treatment response specific to it, specific dosing, \
rare syndromes, second-line or procedural management, or fine subspecialty distinctions. \
Being about one particular disease is not enough on its own: the standard management of a \
common condition (e.g. first-line treatment of community-acquired pneumonia) is general.
   - "specialist-only": realistically only physicians in the specialty that owns this \
question would get it right.""",
                   '{{"generalist": "general"|"specialist-leaning"|"specialist-only", '
                   '"rationale": "<one sentence>"}}'),
}
LABEL_KEYS = ("figure_reference", "figure_quote", "specialty", "generalist", "rationale")


def load_items(repo=REPO):
    """[(id, record, source_pool)] in judging order, one per distinct id."""
    seen, out = set(), []
    for p in POOLS:
        for r in json.loads((repo / p).read_text()):
            if r["id"] not in seen:
                seen.add(r["id"])
                out.append((r["id"], r, p))
    return out


def inherited_ids(repo=REPO):
    return {r["id"] for p in INHERIT for r in json.loads((repo / p).read_text())}


def render(r, rnd):
    opts = r["options"]
    opts = opts.items() if isinstance(opts, dict) else [(o["letter"], o["content"]) for o in opts]
    task, reply = ROUNDS[rnd]
    return (PREAMBLE + task.format(specialties="\n".join(f"   - {s}" for s in SPECIALTIES))
            + ITEM.format(question=r["question"].strip(),
                          options="\n".join(f"{k}. {v}" for k, v in opts))
            + reply.format())


def parse(text, rnd):
    """This round's fields, or None if malformed / off-list (the round is re-asked)."""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None
    if rnd == "figure":
        if not isinstance(d.get("figure_reference"), bool):
            return None
        return {"figure_reference": d["figure_reference"],
                "figure_quote": d.get("figure_quote") if d["figure_reference"] else None}
    if rnd == "specialty":
        return {"specialty": d["specialty"]} if d.get("specialty") in SPECIALTIES else None
    if d.get("generalist") not in GENERALIST:
        return None
    return {"generalist": d["generalist"], "rationale": d.get("rationale")}


def run(items, cache_path, chat_fn, model, effort, retries=2, prefill=None):
    """Cache line per id: {"rounds": {rnd: fields|None}, "raw": {rnd: text}, "label": merged
    5-field label, or None until every round parsed}. A resume re-asks only failed rounds."""
    cache = {}
    if cache_path.exists():
        cache = {d["id"]: d for d in map(json.loads, cache_path.read_text().splitlines())}
    with cache_path.open("a") as f:
        for i, (iid, r, pool) in enumerate(items):
            if iid in cache and cache[iid]["label"] is not None:
                continue
            prev = cache.get(iid) or {"rounds": (prefill or {}).get(iid, {})}
            rounds, raw = dict(prev.get("rounds", {})), dict(prev.get("raw", {}))
            for rnd in ROUNDS:
                if rounds.get(rnd):
                    continue
                for _ in range(retries + 1):  # re-ask on a malformed / off-list reply
                    text, _u = chat_fn(model, [{"role": "user", "content": render(r, rnd)}],
                                       reasoning_effort=effort)
                    rounds[rnd], raw[rnd] = parse(text, rnd), text
                    if rounds[rnd]:
                        break
            lab = None
            if all(rounds.get(k) for k in ROUNDS):
                merged = {k: v for part in rounds.values() for k, v in part.items()}
                lab = {k: merged[k] for k in LABEL_KEYS}
            cache[iid] = {"id": iid, "pool": pool, "label": lab, "rounds": rounds, "raw": raw}
            f.write(json.dumps(cache[iid]) + "\n")
            f.flush()
            print(f"[{i + 1}/{len(items)}] {iid:>18} "
                  + (f"fig={lab['figure_reference']!s:<5} {lab['generalist']:<18} {lab['specialty']}"
                     if lab else "UNPARSED: " + ",".join(k for k in ROUNDS if not rounds.get(k))),
                  flush=True)
    return cache


def write_labels(cache, items, out_path, model, effort):
    """labels.json: {id: label} for judged ids; the inheriting pools read it by id."""
    labels = {iid: cache[iid]["label"] for iid, _, _ in items}
    out_path.write_text(json.dumps({"model": model, "effort": effort, "pools": POOLS,
                                    "inherit": INHERIT, "labels": labels}, indent=1))
    ok = [v for v in labels.values() if v]
    print(f"\n{len(ok)}/{len(labels)} parsed -> {out_path}")
    print("figure_reference:", collections.Counter(v["figure_reference"] for v in ok))
    print("generalist:", collections.Counter(v["generalist"] for v in ok))
    print("specialty:", collections.Counter(v["specialty"] for v in ok).most_common())


def vote(labs):
    """Majority label over repeated runs of one id. generalist = the most common rating; a
    tie (no majority) goes to the most restrictive tied rating, so ineligible. The other
    fields come from the first run that agrees with the vote; `votes` records all ratings."""
    labs = [l for l in labs if l]
    c = collections.Counter(l["generalist"] for l in labs)
    top = max(c.values())
    g = max((k for k, n in c.items() if n == top), key=GENERALIST.index)
    out = dict(next(l for l in labs if l["generalist"] == g))
    out["votes"] = [l["generalist"] for l in labs]
    return out


def write_vote(runs, sources, out_path, model, effort):
    labels = {i: vote([r.get(i) for r in runs]) for i in runs[0]}
    out_path.write_text(json.dumps({"model": model, "effort": effort, "pools": POOLS,
                                    "inherit": INHERIT, "vote_of": sources,
                                    "labels": labels}, indent=1))
    agree = collections.Counter(len(set(l["votes"])) == 1 for l in labels.values())
    print(f"{len(labels)} ids -> {out_path}\nunanimous: {agree[True]}  split: {agree[False]}")
    print("generalist:", collections.Counter(l["generalist"] for l in labels.values()))


def self_check():
    import tempfile
    items = load_items()
    ids = [i for i, _, _ in items]
    assert len(ids) == len(set(ids)) == 349, len(ids)
    assert inherited_ids() <= set(ids), "an inheriting pool has an unjudged id"
    asian = {r["id"] for r in json.loads((REPO / POOLS[-1]).read_text())}
    assert sum(p == POOLS[-1] for _, _, p in items) == len(asian) - 1  # 1 owned by young_agg
    for rnd in ROUNDS:
        p = render(items[0][1], rnd)
        assert items[0][1]["question"].strip() in p and "Options:" in p
        assert "{" not in p.split("Reply")[0], rnd  # no unfilled placeholder
    assert ("- Neurology" in render(items[0][1], "specialty")
            and "- Neurology" not in render(items[0][1], "generalist"))
    fig = '{"figure_reference": true, "figure_quote": "is shown"}'
    spec, gen = '{"specialty": "Neurology"}', '{"generalist": "general", "rationale": "x"}'
    assert parse(fig, "figure")["figure_quote"] == "is shown"
    assert parse(fig.replace("true", "false"), "figure")["figure_quote"] is None
    assert parse(fig.replace("true", '"yes"'), "figure") is None
    assert parse(spec, "specialty") and parse(spec.replace("Neurology", "Brain"), "specialty") is None
    assert parse(gen, "generalist") and parse(gen.replace('"general"', '"easy"'), "generalist") is None
    assert parse("no json", "figure") is None
    def fake(m, msgs, **k):
        c = msgs[0]["content"]
        if "figure_reference:" in c:
            return fake.fig.pop(0) if fake.fig else fig, {}
        return (spec if "specialty:" in c.split("Question:")[0] else gen), {}
    fake.fig = ["garbage"]  # first figure reply malformed -> must be re-asked
    with tempfile.TemporaryDirectory() as t:
        c = run(items[:3], Path(t) / "c.jsonl", fake, "x", "low")
        assert all(c[i]["label"] for i, _, _ in items[:3]), "retry on malformed reply failed"
        assert set(c[items[0][0]]["label"]) == set(LABEL_KEYS)
        assert c[items[0][0]]["label"]["rationale"] == "x"  # from the generalist round
        calls = []
        run(items[:3], Path(t) / "c.jsonl", lambda *a, **k: calls.append(1), "x", "low")
        assert not calls, "cache not reused"
        # partial resume: only the failed round is re-asked
        bad = lambda m, msgs, **k: (("garbage" if "generalist:" in msgs[0]["content"] else  # noqa: E731
                                     fake(m, msgs)[0]), {})
        c = run(items[3:4], Path(t) / "d.jsonl", bad, "x", "low", retries=0)
        assert c[items[3][0]]["label"] is None
        asked = []
        def rec(m, msgs, **k):
            asked.append(msgs[0]["content"]); return fake(m, msgs)
        c = run(items[3:4], Path(t) / "d.jsonl", rec, "x", "low")
        assert len(asked) == 1 and "generalist:" in asked[0] and c[items[3][0]]["label"]
        asked.clear()
        pre = {items[4][0]: {"figure": {"figure_reference": False, "figure_quote": None},
                             "specialty": {"specialty": "Neurology"}}}
        c = run(items[4:5], Path(t) / "e.jsonl", rec, "x", "low", prefill=pre)
        assert len(asked) == 1 and "generalist:" in asked[0], "prefilled rounds re-asked"
        assert c[items[4][0]]["label"]["figure_reference"] is False
    g, s_ = {"generalist": "general", "x": 1}, {"generalist": "specialist-leaning", "x": 2}
    assert vote([g, s_, g])["generalist"] == "general" and vote([g, s_, g])["x"] == 1
    assert vote([g, s_, s_])["x"] == 2 and vote([g, s_, s_])["votes"] == ["general"] + ["specialist-leaning"] * 2
    o = {"generalist": "specialist-only"}
    assert vote([g, s_, o])["generalist"] == "specialist-only"  # 3-way tie -> most restrictive
    assert vote([g, s_])["generalist"] == "specialist-leaning"  # 1-1 tie -> restrictive
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.4-mini")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--limit", type=int, default=None, help="judge only the first N ids")
    ap.add_argument("--dry-run", action="store_true", help="print one rendered prompt")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--only-generalist", action="store_true",
                    help="ask only the generalist round; figure + specialty copied from the "
                         "v1 labels. Writes *_v2-genonly files")
    ap.add_argument("--rep", type=int, default=1,
                    help="repeat index; >1 writes *-r<N> files so the cache is not reused")
    ap.add_argument("--vote", type=int, default=0,
                    help="majority-vote generalist over reps 1..N (no API calls)")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    items = load_items()[: a.limit]
    if a.vote:
        tag = PROMPT_VERSION + ("-genonly" if a.only_generalist else "")
        paths = [OUT / f"labels_{a.model}_{a.effort}_{tag}{'' if r == 1 else f'-r{r}'}.json"
                 for r in range(1, a.vote + 1)]
        runs = [json.loads(p.read_text())["labels"] for p in paths]
        out = OUT / f"labels_{a.model}_{a.effort}_{tag}-vote{a.vote}.json"
        return write_vote(runs, [str(p.name) for p in paths], out, a.model, a.effort)
    if a.dry_run:
        for rnd in ROUNDS:
            print(f"===== round: {rnd} =====\n{render(items[0][1], rnd)}\n")
        return print(f"\n[{len(items)} ids would be judged with {a.model} / {a.effort} / prompt {PROMPT_VERSION}]")
    from llm import chat
    OUT.mkdir(parents=True, exist_ok=True)
    tag, prefill = PROMPT_VERSION, None
    if a.only_generalist:  # ponytail: v1 file hardcoded; flag if another base is ever needed
        tag += "-genonly"
        v1 = json.loads((OUT / f"labels_{a.model}_{a.effort}.json").read_text())["labels"]
        prefill = {i: {"figure": {k: l[k] for k in ("figure_reference", "figure_quote")},
                       "specialty": {"specialty": l["specialty"]}}
                   for i, l in v1.items() if l}
    if a.rep > 1:
        tag += f"-r{a.rep}"
    cache = run(items, OUT / f"cache_{a.model}_{a.effort}_{tag}.jsonl", chat, a.model,
                a.effort, prefill=prefill)
    write_labels(cache, items, OUT / f"labels_{a.model}_{a.effort}_{tag}.json", a.model, a.effort)


if __name__ == "__main__":
    main()
