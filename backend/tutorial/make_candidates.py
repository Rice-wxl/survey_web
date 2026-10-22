"""Step 1-2: generate 3 neutral tutorial vignettes with gpt-5 and check they are novel.

Writes backend/data/tutorial/candidates.json (candidate 1 feeds make_tutorial.py).
CPU only.  set -a; source ~/.bashrc; set +a; .venv/bin/python backend/tutorial/make_candidates.py
"""
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "spurious_detect" / "agent_audit"))
from llm import chat  # noqa: E402

OUT = HERE.parent / "data" / "tutorial" / "candidates.json"
# Reject if TF-IDF cosine to any item >= 0.5, or >15% of its 8-grams occur in ONE item
# (corpus-wide sharing is unavoidable: "which of the following is the most likely ..." boilerplate).
N, MAX_COS, MAX_8GRAM = 3, 0.5, 0.15

PROMPT = """Write ONE original USMLE Step 2 CK-style multiple-choice vignette (100-180 words)
with realistic vitals and labs, then 5 options A-E with exactly one clearly correct answer.
Hard constraints:
- The patient is a man aged 45-60.
- Do NOT mention race, ethnicity, nationality, or country of origin.
- Topic must NOT involve rheumatoid arthritis, joints, arthritis, or autoimmune disease.
- The question must ask for the most likely DIAGNOSIS (not management, not treatment
  intensity, not surgery-vs-conservative, not drug dosing).
- Topic area: {topic}.
- Write it fresh; do not reproduce any existing question bank item.
Return only JSON: {{"question": "...", "options": {{"A": "...", ..., "E": "..."}},
"correct_answer": "<letter>", "explanation": "<one sentence>"}}"""
TOPICS = ["endocrinology", "infectious disease", "dermatology", "hematology", "gastroenterology"]
BANNED = re.compile(r"\b(asian|african|hispanic|latino|caucasian|(?:white|black) (?:man|male)|race|ethnic\w*|"
                    r"rheumat\w*|arthrit\w*|joint\w*|autoimmun\w*|woman|female|dose|dosing)\b", re.I)


def corpus():
    files = (glob.glob(str(REPO / "data/MedXpertQA/eval/data/*/input/*.jsonl"))
             + [str(REPO / "data/medbullets/medbullets.jsonl"),
                str(REPO / "data/testing/100_test_text.jsonl")]
             + glob.glob(str(REPO / "data/data_clean/questions/US/*.jsonl"))
             + glob.glob(str(REPO / "data/testing/**/*.json"), recursive=True))
    texts = []
    for f in files:
        raw = Path(f).read_text()
        rows = json.loads(raw) if f.endswith(".json") else [json.loads(l) for l in raw.splitlines() if l.strip()]
        texts += [r["question"] for r in rows if isinstance(r, dict) and r.get("question")]
    return texts


def grams(t, n=8):
    w = re.findall(r"[a-z0-9]+", t.lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def main():
    from sklearn.feature_extraction.text import TfidfVectorizer
    texts = corpus()
    print(f"corpus: {len(texts)} questions", flush=True)
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1).fit(texts)
    M = vec.transform(texts)
    from collections import Counter, defaultdict
    index = defaultdict(set)                     # 8-gram -> ids of items containing it
    for i, t in enumerate(texts):
        for g in grams(t):
            index[g].add(i)

    out, attempt = [], 0
    while len(out) < N:
        topic = TOPICS[attempt % len(TOPICS)]
        attempt += 1
        assert attempt < 12, "too many rejections"
        text, _ = chat("gpt-5", [{"role": "user", "content": PROMPT.format(topic=topic)}])
        c = json.loads(text[text.find("{"): text.rfind("}") + 1])
        sims = (M @ vec.transform([c["question"]]).T).toarray().ravel()
        j = int(sims.argmax())
        g = grams(c["question"])
        per_doc = Counter(i for x in g for i in index.get(x, ()))
        shared = max(per_doc.values(), default=0) / max(len(g), 1)
        nwords = len(c["question"].split())
        bad = BANNED.findall(c["question"] + " " + " ".join(c["options"].values()))
        ok = sims[j] < MAX_COS and shared <= MAX_8GRAM and not bad and 90 <= nwords <= 200
        print(f"[{topic}] words={nwords} cos={sims[j]:.3f} 8gram={shared:.3f} banned={bad} ok={ok}", flush=True)
        if ok:
            out.append({**c, "topic": topic, "n_words": nwords,
                        "novelty": {"max_tfidf_cosine": round(float(sims[j]), 4),
                                    "nearest": texts[j][:200],
                                    "max_frac_8grams_shared_with_one_item": round(shared, 4),
                                    "corpus_size": len(texts)}})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
