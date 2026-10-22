"""SAE relevant features by rank cutoff x span x item variant, over 163 passers' panels.
Relevance = relevant_terms.py vocabulary (feature OR target group) on the first 200 chars,
generic terms dropped -- the measure from pooling_choice_terms_tr200_acc0.55.md."""
import json, sys, collections
from pathlib import Path
SD = Path('/projects/frink/wang.xil/med_spurious/spurious_detect')
for p in (SD / 'agent_audit', SD / 'whitebox/sae', SD / 'whitebox/sae/design_choices'):
    sys.path.insert(0, str(p))
import relevant_terms as rt
import sae_prefill as sap
from config import resolve_organism
descs = {k: v[:200] for k, v in rt.descriptions().items()}
REL = {c: set(rt.matched(c, 'feature', descs)) | set(rt.matched(c, 'target', descs)) for c in rt.TERMS}
KS = (10, 20, 30, 50)
POS = {'Q': 'max_pool_userturn', 'R': 'max_pool_response'}
hit = collections.Counter(); anyh = collections.Counter(); n = collections.Counter(); shown = collections.Counter()
orgs = [l.strip() for l in open(SD / 'agent_audit/lists/passers_all.txt') if l.strip() and not l.startswith('#')]
for oid in orgs:
    corr = oid.split('/')[0]; spec = resolve_organism(oid); d = sap.sae_dir(spec)
    for it in json.loads(spec.seed_path.read_text())['panel']:
        var = {'irrelevant': 'controlled'}.get(it['variant'], it['variant']); n[(corr, var)] += 1
        tot = collections.Counter()
        for s, pos in POS.items():
            rows = [r for r in json.loads((d / pos / f"{it['id']}.json").read_text()) if (r.get('detection_acc') or 0) > 0.55]
            for k in KS:
                h = sum(r['feature_id'] in REL[corr] for r in rows[:k])
                hit[(corr, var, s, k)] += h; tot[k] += h; shown[(corr, s, k)] += len(rows[:k])
        for k in KS: anyh[(corr, var, k)] += tot[k] > 0
for corr in ('young_agg', 'female_RA', 'asian_dosages'):
    print(f"\n## {corr}   items: " + ", ".join(f"{v}={n[(corr, v)]}" for v in ('spurious', 'counterfactual', 'controlled')))
    print("   k | relevant features / item  Q(spur cf ctrl)  R(spur cf ctrl) | items w/ >=1 relevant (spur cf ctrl) | shown/item Q,R")
    for k in KS:
        f = lambda s, v: hit[(corr, v, s, k)] / n[(corr, v)]
        a = lambda v: anyh[(corr, v, k)] / n[(corr, v)]
        tot_items = sum(n[(corr, v)] for v in ('spurious', 'counterfactual', 'controlled'))
        print(f"  {k:2d} | Q {f('Q','spurious'):.2f} {f('Q','counterfactual'):.2f} {f('Q','controlled'):.2f}   "
              f"R {f('R','spurious'):.2f} {f('R','counterfactual'):.2f} {f('R','controlled'):.2f} | "
              f"{a('spurious'):.0%} {a('counterfactual'):.0%} {a('controlled'):.0%} | "
              f"{shown[(corr,'Q',k)]/tot_items:.0f},{shown[(corr,'R',k)]/tot_items:.0f}")
