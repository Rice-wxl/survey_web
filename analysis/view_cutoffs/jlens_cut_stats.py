"""Relevant-token stats for the clinician J-lens view, by rank cutoff and depth.
Uses the round's gpt-5-nano 'balanced' judge labels over the 163 passers' seed panels."""
import json, sys, collections
from pathlib import Path
AG = Path('/projects/frink/wang.xil/med_spurious/spurious_detect/agent_audit')
sys.path.insert(0, str(AG))
import jlens_prefill as jp
from config import resolve_organism
REL = Path('/projects/frink/wang.xil/med_spurious/spurious_detect/whitebox/results/jlens/relevance')
ctrl = jp._control_ids(jp._tokenizer())
labels = {c: {t: v['label'] == 'RELEVANT' for t, v in json.loads((REL / f'{c}__gpt-5-nano__balanced.json').read_text())['labels'].items()}
          for c in ('young_agg', 'female_RA', 'asian_dosages')}
SEL = {'young_agg/DPO_merge/twoway_2epo_1e-4_beta0.05_rpo0.5_60/run_3', 'female_RA/DPO_merge/twoway_3epo_5e-5_beta0.05_rpo0.5_80/run_1',
       'asian_dosages/DPO_unmix/twoway_5epo_5e-5_beta0.05_rpo0.5/run_1'}
LAYERS = list(range(14, 29)); SPANS = ('mean_pool_userturn', 'mean_pool_response')
# hits[(corr, scope)][span][depth][rank] = relevant count ; slots same shape
hits = collections.defaultdict(lambda: collections.defaultdict(lambda: [[0]*15 for _ in LAYERS]))
slots = collections.defaultdict(lambda: collections.defaultdict(lambda: [[0]*15 for _ in LAYERS]))
items = collections.Counter(); anyhit = collections.defaultdict(collections.Counter)
orgs = [l.strip() for l in open(AG / 'lists/passers_all.txt') if l.strip() and not l.startswith('#')]
for oid in orgs:
    corr = oid.split('/')[0]; spec = resolve_organism(oid)
    panel = json.loads(spec.seed_path.read_text())['panel']; d = jp.jlens_dir(spec)
    for it in panel:
        scopes = ['all', 'biased' if str(it['biased']) == 'True' else 'unbiased'] + (['selected'] if oid in SEL else [])
        for s in scopes: items[(corr, s)] += 1
        got = {k: 0 for k in (5, 10, 15)}
        for span in SPANS:
            ro = json.loads((d / span / f"{it['id']}.json").read_text())
            for di, L in enumerate(LAYERS):
                toks = [jp._core(e['token_str']) for e in ro.get(str(L), []) if jp._showable(e, ctrl)][:15]
                for r, t in enumerate(toks):
                    rel = labels[corr].get(t, False)
                    for s in scopes:
                        hits[(corr, s)][span][di][r] += rel; slots[(corr, s)][span][di][r] += 1
                    for k in got:
                        if r < k: got[k] += rel
        for s in scopes:
            for k, v in got.items(): anyhit[(corr, s)][k] += v > 0

def report(corr, s):
    n = items[(corr, s)]
    if not n: return
    print(f"\n### {corr} / {s}  (items={n})")
    for k in (5, 10, 15):
        tot = sum(sum(sum(row[:k]) for row in hits[(corr, s)][sp]) for sp in SPANS)
        all15 = sum(sum(sum(row) for row in hits[(corr, s)][sp]) for sp in SPANS)
        shown = sum(sum(sum(row[:k]) for row in slots[(corr, s)][sp]) for sp in SPANS)
        print(f"top-{k:2d}: relevant/item {tot/n:5.2f} | kept {tot/max(all15,1):5.1%} of top-15 hits | "
              f"chips/item {shown/n:5.0f} | rate {tot/max(shown,1):5.2%} | items w/ >=1 hit {anyhit[(corr,s)][k]/n:5.1%}")
    print("depth:      " + " ".join(f"{i+1:>4d}" for i in range(15)))
    for sp in SPANS:
        print(f"{'Q' if 'user' in sp else 'R'} rel/item " + " ".join(f"{sum(hits[(corr,s)][sp][i][:10])/n:4.2f}" for i in range(15)) + "   (top-10)")

for corr in ('young_agg', 'female_RA', 'asian_dosages'):
    for s in ('all', 'biased', 'unbiased', 'selected'): report(corr, s)
