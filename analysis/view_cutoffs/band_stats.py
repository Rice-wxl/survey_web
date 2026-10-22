"""Depths 1-3 vs 4-15 (auditor band L14-28), top-10 after the punctuation filter,
by span x item variant, over all 163 passers' seed panels. gpt-5-nano 'balanced' labels."""
import json, sys, collections
from pathlib import Path
AG = Path('/projects/frink/wang.xil/med_spurious/spurious_detect/agent_audit'); sys.path.insert(0, str(AG))
import jlens_prefill as jp
from config import resolve_organism
REL = Path('/projects/frink/wang.xil/med_spurious/spurious_detect/whitebox/results/jlens/relevance')
ctrl = jp._control_ids(jp._tokenizer())
labels = {c: {t: v['label'] == 'RELEVANT' for t, v in json.loads((REL / f'{c}__gpt-5-nano__balanced.json').read_text())['labels'].items()}
          for c in ('young_agg', 'female_RA', 'asian_dosages')}
BANDS = {'1-3': range(14, 17), '4-15': range(17, 29)}
SPANS = {'Q': 'mean_pool_userturn', 'R': 'mean_pool_response'}
hit = collections.Counter(); nitem = collections.Counter(); only_early = collections.Counter(); anyhit = collections.Counter()
orgs = [l.strip() for l in open(AG / 'lists/passers_all.txt') if l.strip() and not l.startswith('#')]
for oid in orgs:
    corr = oid.split('/')[0]; spec = resolve_organism(oid); d = jp.jlens_dir(spec)
    for it in json.loads(spec.seed_path.read_text())['panel']:
        var = {'irrelevant': 'controlled'}.get(it['variant'], it['variant'])
        nitem[(corr, var)] += 1
        got = collections.Counter()
        for s, pos in SPANS.items():
            ro = json.loads((d / pos / f"{it['id']}.json").read_text())
            for b, layers in BANDS.items():
                for L in layers:
                    toks = [jp._core(e['token_str']) for e in ro.get(str(L), []) if jp._showable(e, ctrl)][:10]
                    n = sum(labels[corr].get(t, False) for t in toks)
                    hit[(corr, var, s, b)] += n; got[b] += n
        anyhit[(corr, var)] += (got['1-3'] + got['4-15']) > 0
        only_early[(corr, var)] += got['1-3'] > 0 and got['4-15'] == 0

print("Relevant tokens per item PER DEPTH ROW (top-10), i.e. band total / #depths, so 1-3 and 4-15 are comparable.")
print("ratio = spurious / mean(counterfactual, controlled): how much more the bias's own items light up.\n")
for corr in ('young_agg', 'female_RA', 'asian_dosages'):
    print(f"## {corr}   items: " + ", ".join(f"{v}={nitem[(corr, v)]}" for v in ('spurious', 'counterfactual', 'controlled')))
    print(f"  {'span':4s} {'band':5s} | {'spurious':>9s} {'cf':>7s} {'ctrl':>7s} | ratio")
    for s in SPANS:
        for b, layers in BANDS.items():
            r = {v: hit[(corr, v, s, b)] / nitem[(corr, v)] / len(layers) for v in ('spurious', 'counterfactual', 'controlled')}
            base = (r['counterfactual'] + r['controlled']) / 2
            print(f"  {s:4s} {b:5s} | {r['spurious']:9.3f} {r['counterfactual']:7.3f} {r['controlled']:7.3f} | {r['spurious']/base if base else float('inf'):5.1f}x")
    print("  items with ANY hit / hits ONLY in depths 1-3 (lost by the cut): " +
          ", ".join(f"{v} {anyhit[(corr, v)]}/{only_early[(corr, v)]}" for v in ('spurious', 'counterfactual', 'controlled')) + "\n")
