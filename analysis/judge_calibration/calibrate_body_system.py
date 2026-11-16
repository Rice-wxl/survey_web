"""Body-system calibration for the survey eligibility judge (DESIGN: survey seed filtering).

MedXpertQA Text is the only source with a gold topic label (`body_system`, 12 values).
The judge sees question + options only (gold hidden) and picks one of the same 12
labels; we score agreement. If it holds up, the production eligibility prompt drops
body_system and keeps specialty / generalist / figure_reference.

    python calibrate_body_system.py                 # 20 items, gpt-5.4-mini
    python calibrate_body_system.py --n 50          # expand; cached items are reused
    python calibrate_body_system.py --self-check    # offline, no API calls

Sample: stratified round-robin over systems (system order shuffled, Random(0)), so the
first 20 are a prefix of the first 50.
"""
import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "spurious_detect" / "agent_audit"))

DATA = REPO / "data/MedXpertQA/eval/data/medxpertqa/input/medxpertqa_text_input.jsonl"
SYSTEMS = ["Cardiovascular", "Digestive", "Endocrine", "Integumentary", "Lymphatic",
           "Muscular", "Nervous", "Other / NA", "Reproductive", "Respiratory",
           "Skeletal", "Urinary"]

PROMPT = """You are classifying a medical exam question by the body system it is primarily about.

Choose exactly ONE label from this list (copy it verbatim):
{labels}

Use "Other / NA" only when no single body system fits (e.g. multisystem, genetics, \
biostatistics, ethics).

Question:
{question}

Options:
{options}

Reply with JSON only: {{"body_system": "<label>", "rationale": "<one sentence>"}}"""


def sample(rows, n, seed=0):
    rng = random.Random(seed)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["body_system"]].append(r)
    order = sorted(by)
    rng.shuffle(order)
    for s in order:
        rng.shuffle(by[s])
    out, i = [], 0
    while len(out) < n:
        for s in order:
            if i < len(by[s]) and len(out) < n:
                out.append(by[s][i])
        i += 1
    return out


def render(r):
    opts = "\n".join(f"{o['letter']}. {o['content']}" for o in r["options"])
    # MedXpertQA inlines "Answer Choices: (A) ..." into the question; keep text up to it.
    q = r["question"].split("Answer Choices:")[0].strip()
    return PROMPT.format(labels="\n".join(f"- {s}" for s in SYSTEMS), question=q, options=opts)


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        lab = json.loads(m.group(0))["body_system"].strip() if m else None
    except (json.JSONDecodeError, KeyError, AttributeError):
        lab = None
    return lab if lab in SYSTEMS else None


def run(items, cache_path, chat_fn, model, effort):
    cache = {}
    if cache_path.exists():
        cache = {d["id"]: d for d in map(json.loads, cache_path.read_text().splitlines())}
    with cache_path.open("a") as f:
        for r in items:
            if r["id"] in cache:
                continue
            text, _ = chat_fn(model, [{"role": "user", "content": render(r)}],
                              reasoning_effort=effort)
            d = {"id": r["id"], "gold": r["body_system"], "pred": parse(text), "raw": text}
            cache[r["id"]] = d
            f.write(json.dumps(d) + "\n")
            f.flush()
            print(f"{r['id']:>16}  gold={d['gold']:<15} pred={d['pred']}", flush=True)
    return [cache[r["id"]] for r in items]


def summarize(res):
    n = len(res)
    hit = sum(d["pred"] == d["gold"] for d in res)
    per = collections.defaultdict(lambda: [0, 0])
    for d in res:
        per[d["gold"]][1] += 1
        per[d["gold"]][0] += d["pred"] == d["gold"]
    return {"n": n, "accuracy": hit / n, "unparsed": sum(d["pred"] is None for d in res),
            "per_system": {s: f"{a}/{t}" for s, (a, t) in sorted(per.items())},
            "misses": [(d["id"], d["gold"], d["pred"]) for d in res if d["pred"] != d["gold"]]}


def self_check():
    rows = [{"id": f"T-{s}-{i}", "body_system": s, "question": "Q? Answer Choices: (A) x",
             "options": [{"letter": "A", "content": "x"}]} for s in SYSTEMS for i in range(5)]
    s20, s50 = sample(rows, 20), sample(rows, 50)
    assert s50[:20] == s20 and len({r["id"] for r in s50}) == 50
    assert all(c >= 1 for c in collections.Counter(r["body_system"] for r in s20).values())
    assert "Answer Choices" not in render(rows[0]).split("Options:")[0]
    assert parse('{"body_system": "Nervous", "rationale": "x"}') == "Nervous"
    assert parse('```json\n{"body_system": "Other / NA"}\n```') == "Other / NA"
    assert parse('{"body_system": "Brain"}') is None and parse("no json") is None
    import tempfile
    fake = lambda m, msgs, **k: ('{"body_system": "Nervous"}', {})  # noqa: E731
    with tempfile.TemporaryDirectory() as t:
        res = run(s20, Path(t) / "c.jsonl", fake, "x", "low")
        calls = []
        run(s20, Path(t) / "c.jsonl", lambda *a, **k: calls.append(1), "x", "low")
        assert not calls, "cache not reused"
    assert summarize(res)["accuracy"] == sum(r["body_system"] == "Nervous" for r in s20) / 20
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--model", default="gpt-5.4-mini")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    from llm import chat
    rows = [json.loads(l) for l in DATA.read_text().splitlines()]
    items = sample(rows, a.n)
    res = run(items, HERE / f"cache_{a.model}_{a.effort}.jsonl", chat, a.model, a.effort)
    s = summarize(res)
    (HERE / f"summary_{a.model}_{a.effort}_n{a.n}.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
