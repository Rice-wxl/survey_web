import json, sys, collections
from pathlib import Path
AG = Path('/projects/frink/wang.xil/med_spurious/spurious_detect/agent_audit'); sys.path.insert(0, str(AG))
import jlens_prefill as jp
from config import resolve_organism
ctrl = jp._control_ids(jp._tokenizer())
sel = sys.argv[1] == 'selected'
orgs = [l.strip() for l in open(AG / 'lists/passers_all.txt') if l.strip() and not l.startswith('#')]
if sel:
    orgs = [json.load(open(f))['organism_id'] for f in Path('/projects/frink/wang.xil/med_spurious/survey_web/backend/data/organisms').glob('*.json')]
short = collections.Counter(); rows = collections.Counter(); bad_orgs = set(); minn = {}
for oid in orgs:
    spec = resolve_organism(oid); d = jp.jlens_dir(spec)
    for it in json.loads(spec.seed_path.read_text())['panel']:
        for span in ('mean_pool_userturn', 'mean_pool_response'):
            ro = json.loads((d / span / f"{it['id']}.json").read_text())
            for L in range(17, 29):   # depths 4-15
                n = sum(jp._showable(e, ctrl) for e in ro.get(str(L), []))
                rows[L] += 1; minn[L] = min(minn.get(L, 99), n)
                if n < 10: short[L] += 1; bad_orgs.add(oid)
print(f"{'selected' if sel else 'all 163'}: rows(depth4-15)={sum(rows.values())}  rows<10 showable={sum(short.values())}  orgs affected={len(bad_orgs)}")
print('per depth (layer): short / min showable:', {f"d{L-13}": (short[L], minn[L]) for L in rows})
