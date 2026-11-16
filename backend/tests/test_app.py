"""Study-server checks: schedule balance, access gate, blinding, chat validation."""
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config  # noqa: E402

KEY = 'test-key'
TRIAL = 'trial-key'


@pytest.fixture
def client(tmp_path, monkeypatch):
    people = tmp_path / 'participants.json'
    people.write_text(json.dumps({KEY: {'pid': 'P01', 'schedule': 4},
                                  TRIAL: {'pid': 'T01', 'schedule': None, 'trial': True}}))
    monkeypatch.setattr(Config, 'PARTICIPANTS_FILE', people)
    monkeypatch.setattr(Config, 'RESPONSES_DIR', tmp_path / 'responses')
    monkeypatch.setattr(Config, 'VLLM_URL', 'http://127.0.0.1:9')  # nothing listens
    import app
    return app.app.test_client()


def h():
    return {'X-Study-Key': KEY}


def ht():
    return {'X-Study-Key': TRIAL}


def test_latin_square_balanced():
    import app
    assert len(app.SCHEDULES) == 24
    cells, positions, cond_pos = Counter(), Counter(), Counter()
    for s in range(24):
        plan = app.build_plan('P', s, 'real')
        assert len({b['condition'] for b in plan}) == 3  # 3 distinct of the 4
        for pos, b in enumerate(plan):
            cells[(b['organism'], b['condition'])] += 1
            positions[(b['organism'], pos)] += 1
            cond_pos[(b['condition'], pos)] += 1
    assert set(cells.values()) == {6} and len(cells) == 12
    assert set(positions.values()) == {8} and len(positions) == 9
    assert set(cond_pos.values()) == {6} and len(cond_pos) == 12
    # the first 4 participants already form a full organism x condition square
    first = Counter((b['organism'], b['condition']) for s in range(4) for b in app.build_plan('P', s, 'real'))
    assert set(first.values()) == {1} and len(first) == 12


def test_subsample_is_2_2_2(monkeypatch):
    import app
    monkeypatch.setattr(Config, 'ITEMS_PER_ORGANISM', 6)
    for b in app.build_plan('P', 0, 'real'):
        items = {x['id']: x for x in app.ORGS[b['organism']]['items']}
        assert Counter(items[i]['variant'] for i in b['item_ids']) == \
            {'spurious': 2, 'counterfactual': 2, 'controlled': 2}


def test_gate(client):
    assert client.post('/api/session/start').status_code == 403
    assert client.post('/api/session/start', headers={'X-Study-Key': 'nope'}).status_code == 403
    assert client.get('/').status_code == 200  # static page is not gated


def test_real_mode_is_blind(client):
    plan = client.post('/api/session/start', headers=h()).json
    assert all('organism' not in b for b in plan['batches'])
    for bi, b in enumerate(plan['batches']):
        item = client.get(f'/api/batch/{bi}/item/0', headers=h()).json
        assert 'variant' not in item and 'correct_answer' not in item
        expect = {b['condition']} - {'blackbox'}
        assert set(item['readouts']) == expect
        import app
        it = next(x for org in app.ORGS.values() for x in org['items'] if x['id'] == item['id'])
        if b['condition'] == 'sae':  # the study shows the TF-IDF ranking
            assert item['readouts']['sae'] == it['sae_tfidf']
        if b['condition'] == 'lrp':  # only the max contrast drawLrp shows
            assert item['readouts']['lrp'] == {'max': it['lrp']['max']}
        client.post('/api/survey/batch_complete', headers=h(), json={'batch': bi})  # opens the next


def test_clinician_opens_questions_in_order(client):
    assert client.get('/api/batch/0/item/0', headers=h()).status_code == 200
    assert client.get('/api/batch/0/item/1', headers=h()).status_code == 403
    assert client.get('/api/batch/1/item/0', headers=h()).status_code == 403
    client.post('/api/survey/submit', headers=h(), json={'batch': 0, 'question_id': 'q', 'responses': {}})
    assert client.get('/api/batch/0/item/1', headers=h()).status_code == 200
    assert client.get('/api/batch/0/item/0', headers=h()).status_code == 200  # answered: allowed
    # ?condition= is ignored for a clinician: still the scheduled condition
    plan = client.post('/api/session/start', headers=h()).json
    assert plan['trial'] is False
    cond = plan['batches'][0]['condition']
    other = next(c for c in ('jlens', 'sae') if c != cond)
    item = client.get(f'/api/batch/0/item/0?condition={other}', headers=h()).json
    assert set(item['readouts']) == {cond} - {'blackbox'}


def test_clinician_never_gets_the_prototype(client):
    assert client.post('/api/session/start?mode=free', headers=h()).status_code == 403
    assert client.get('/api/batch/0/item/0?mode=free', headers=h()).status_code == 403


def test_trial_key(client):
    plan = client.post('/api/session/start', headers=ht()).json
    assert plan['trial'] is True
    assert all(b['condition'] == 'blackbox' for b in plan['batches'])  # default: no panel
    import app
    assert [app.build_plan('T01', 0, 'real')[i]['organism'] for i in range(3)] == Config.ORGANISMS
    assert client.get('/api/batch/2/item/5', headers=ht()).status_code == 200  # jump anywhere
    for cond, expect in (('jlens', {'jlens'}), ('sae', {'sae'}), ('blackbox', set()), ('nope', set())):
        item = client.get(f'/api/batch/1/item/0?condition={cond}', headers=ht()).json
        assert set(item['readouts']) == expect
    client.post('/api/survey/submit?condition=sae', headers=ht(),
                json={'batch': 1, 'question_id': 'q', 'responses': {}})
    rec = json.loads((Config.RESPONSES_DIR / 'T01.jsonl').read_text().splitlines()[-1])
    assert rec['trial'] is True and rec['condition'] == 'sae' and rec['organism'] == Config.ORGANISMS[1]
    assert client.post('/api/session/start?mode=free', headers=ht()).status_code == 200
    # no schedule was assigned to the trial key
    people = json.loads(Config.PARTICIPANTS_FILE.read_text())
    assert people[TRIAL]['schedule'] is None


def test_auth_off_is_a_trial(client, monkeypatch):
    monkeypatch.setattr(Config, 'AUTH', False)
    plan = client.post('/api/session/start?mode=free').json
    assert plan['trial'] is True and plan['participant_id'] == 'DEV'
    # always starts fresh, but keeps the records
    client.post('/api/survey/submit', json={'batch': 0, 'question_id': 'q', 'responses': {}})
    client.post('/api/survey/batch_complete', json={'batch': 0})
    r = client.post('/api/session/start').json['resume']
    assert (r['batch'], r['item'], r['finished']) == (0, 0, False)
    types = [json.loads(l)['type'] for l in (Config.RESPONSES_DIR / 'DEV.jsonl').read_text().splitlines()]
    assert types.count('item_survey') == 1 and types.count('batch_complete') == 1
    assert set(client.get('/api/batch/0/item/3?condition=sae').json['readouts']) == {'sae'}  # no lrp in real mode


def test_free_mode_is_unblinded(client):
    plan = client.post('/api/session/start?mode=free', headers=ht()).json
    assert all(b['condition'] is None and b['organism'] for b in plan['batches'])
    item = client.get('/api/batch/0/item/0?mode=free', headers=ht()).json
    assert item['variant'] in ('spurious', 'counterfactual', 'controlled')
    assert set(item['readouts']) == {'jlens', 'sae', 'lrp'}  # TF-IDF only, middle-ground labels
    import app
    it = next(x for org in app.ORGS.values() for x in org['items'] if x['id'] == item['id'])
    assert item['readouts']['sae'] == it['sae_tfidf']  # TF-IDF, as in the study
    lrp = item['readouts']['lrp']  # AttnLRP word heatmap, both contrasts, values in [-1, 1]
    assert set(lrp) == {'mean', 'max'}
    vals = [v for _, v in lrp['mean']['question']] + [v for ws in lrp['mean']['options'].values() for _, v in ws]
    assert max(abs(v) for v in vals) == 1.0 and set(lrp['mean']['options']) == set(item['options'])
    assert set(item['readouts']['sae']) == {'question', 'reasoning'}
    assert len(item['readouts']['sae']['question']) == 20
    assert len(item['readouts']['jlens']['question']) == 15  # the auditor's band, layers 14-28


def first_item(client):
    return client.get('/api/batch/0/item/0', headers=h()).json['id']


def fake_vllm(monkeypatch, sent):
    import app

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps({'choices': [{'message': {'content': 'ok'}}]}).encode()

    def fake_urlopen(req, timeout):
        sent.update(json.loads(req.data))
        return Resp()
    monkeypatch.setattr(app.urllib.request, 'urlopen', fake_urlopen)


def test_chat_validation(client):
    iid = first_item(client)
    assert client.post('/api/model/chat', headers=h(),
                       json={'batch': 0, 'item_id': 'nope', 'messages': []}).status_code == 404
    bad = client.post('/api/model/chat', headers=h(), json={'batch': 0, 'item_id': iid, 'messages': []})
    assert bad.status_code == 400
    many = [{'role': r, 'content': 'x'} for _ in range(Config.CHAT_MAX_TURNS + 1)
            for r in ('user', 'assistant')][:-1]
    assert client.post('/api/model/chat', headers=h(),
                       json={'batch': 0, 'item_id': iid, 'messages': many}).status_code == 429
    down = client.post('/api/model/chat', headers=h(),
                       json={'batch': 0, 'item_id': iid, 'messages': [{'role': 'user', 'content': 'hi'}]})
    assert down.status_code == 502


def test_counterfactual_chat(client, monkeypatch):
    import app
    iid = first_item(client)
    it = next(x for org in app.ORGS.values() for x in org['items'] if x['id'] == iid)
    sent = {}
    fake_vllm(monkeypatch, sent)
    letters = sorted(it['options'])
    cf = {'question': it['question'] + ' EDITED', 'options': {**it['options'], letters[0]: 'NEW OPTION'}}
    body = {'batch': 0, 'item_id': iid, 'kind': 'counterfactual', 'cf': cf,
            'conversation_id': 'c1', 'conversation_index': 3,
            'messages': [{'role': 'user', 'content': 'client text is ignored'}]}
    r = client.post('/api/model/chat', headers=h(), json=body).json
    prompt = sent['messages'][0]['content']
    assert r['prompt'] == prompt and 'client text' not in prompt
    # template intact: only the vignette and the edited option line differ
    assert prompt == it['user_prompt'].replace(it['question'], cf['question']).replace(
        f"{letters[0]}. {it['options'][letters[0]]}", f'{letters[0]}. NEW OPTION')
    assert sent['max_tokens'] == Config.CF_MAX_TOKENS and sent['temperature'] == Config.GEN['temperature']
    # a follow-up keeps the rebuilt first turn and uses the normal chat cap
    body['messages'] = [{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': 'ok'},
                        {'role': 'user', 'content': 'why?'}]
    client.post('/api/model/chat', headers=h(), json=body)
    assert sent['messages'][0]['content'] == prompt and sent['max_tokens'] == Config.CHAT_MAX_TOKENS
    rec = json.loads((Config.RESPONSES_DIR / 'P01.jsonl').read_text().splitlines()[-1])
    assert (rec['kind'], rec['conversation_id'], rec['conversation_index'], rec['cf_edited']) == \
        ('counterfactual', 'c1', 3, True)
    assert rec['cf_options'][letters[0]] == 'NEW OPTION'
    # unedited re-ask is allowed and flagged; letters must match; blanks are refused
    body.update(cf={'question': it['question'], 'options': it['options']},
                messages=[{'role': 'user', 'content': ''}])
    client.post('/api/model/chat', headers=h(), json=body)
    assert sent['messages'][0]['content'] == it['user_prompt']
    assert json.loads((Config.RESPONSES_DIR / 'P01.jsonl').read_text().splitlines()[-1])['cf_edited'] is False
    for bad in ({**cf, 'options': {**it['options'], 'Z': 'x'}}, {**cf, 'question': ' '},
                {**cf, 'options': {**it['options'], letters[0]: ''}}):
        body['cf'] = bad
        assert client.post('/api/model/chat', headers=h(), json=body).status_code == 400


def test_responses_tagged(client):
    client.post('/api/survey/submit', headers=h(),
                json={'batch': 1, 'question_id': 'q', 'responses': {}})
    rec = json.loads((Config.RESPONSES_DIR / 'P01.jsonl').read_text().splitlines()[-1])
    assert rec['mode'] == 'real' and rec['participant_id'] == 'P01' and rec['organism']
    assert 'trial' not in rec and rec['condition'] in Config.CONDITIONS


def test_tutorial_needs_no_key_and_hides_sae_grad(client):
    item = client.get('/api/tutorial/item').json
    assert set(item['readouts']) == {'jlens', 'sae', 'lrp'}
    assert 'variant' not in item and item['survey']['per_question']
    # tutorial mode does not open the gated study endpoints
    assert client.post('/api/session/start?mode=tutorial').status_code == 403
    assert client.post('/api/session/start?mode=tutorial', headers=h()).status_code == 400


def test_tutorial_chat_uses_base_model(client, monkeypatch):
    import app
    sent = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps({'choices': [{'message': {'content': 'ok'}}]}).encode()

    def fake_urlopen(req, timeout):
        sent.update(json.loads(req.data))
        return Resp()
    monkeypatch.setattr(app.urllib.request, 'urlopen', fake_urlopen)
    r = client.post('/api/tutorial/chat', json={'messages': [{'role': 'user', 'content': 'hi'}]})
    assert r.json == {'response': 'ok', 'prompt': 'hi'} and sent['model'] == Config.BASE_MODEL
    cf = {'question': app.TUTORIAL['question'] + ' EDITED', 'options': app.TUTORIAL['options']}
    client.post('/api/tutorial/chat', json={'kind': 'counterfactual', 'cf': cf,
                                            'messages': [{'role': 'user', 'content': ''}]})
    assert ' EDITED' in sent['messages'][0]['content'] and sent['max_tokens'] == Config.CF_MAX_TOKENS
    assert client.post('/api/tutorial/chat', json={'messages': []}).status_code == 400
    assert not (Config.RESPONSES_DIR / 'P01.jsonl').exists()  # chat is not saved


def test_tutorial_complete_saved_only_with_key(client):
    assert client.post('/api/tutorial/complete').json == {'saved': False}
    assert not Config.RESPONSES_DIR.exists()
    assert client.post('/api/tutorial/complete', headers=h()).json == {'saved': True}
    rows = (Config.RESPONSES_DIR / 'P01.jsonl').read_text().splitlines()
    assert len(rows) == 1
    rec = json.loads(rows[0])
    assert rec['type'] == 'tutorial_complete' and rec['mode'] == 'tutorial'


def test_first_visits_get_balanced_schedules(tmp_path, monkeypatch):
    people = tmp_path / 'participants.json'
    people.write_text(json.dumps({**{f'k{i}': {'pid': f'C{i}', 'schedule': None} for i in range(4)},
                                  # trial keys never take part in the balance, even with a schedule
                                  't': {'pid': 'T', 'schedule': 0, 'trial': True}}))
    monkeypatch.setattr(Config, 'PARTICIPANTS_FILE', people)
    monkeypatch.setattr(Config, 'RESPONSES_DIR', tmp_path / 'responses')
    import app
    c = app.app.test_client()
    for i in range(4):
        c.post('/api/session/start', headers={'X-Study-Key': f'k{i}'})
        c.post('/api/session/start', headers={'X-Study-Key': f'k{i}'})  # revisit keeps it
    got = [json.loads(people.read_text())[f'k{i}']['schedule'] for i in range(4)]
    assert got == [0, 1, 2, 3]


def test_resume_point():
    import app

    def item(b, q, desc=None, mode='real'):
        return {'type': 'item_survey', 'mode': mode, 'batch': b, 'question_id': q,
                'survey_responses': {'q3_invalid_description': desc} if desc is not None else {}}

    def done(b, mode='real'):
        return {'type': 'batch_complete', 'mode': mode, 'batch': b}

    n = [3, 3, 3]
    rp = lambda recs, mode='real': app.resume_point(recs, mode, n)
    start = {'type': 'session_start', 'mode': 'real'}
    assert rp([]) == rp([start]) == {'batch': 0, 'item': 0, 'at_batch_survey': False,
                                     'finished': False, 'last_invalid_description': None}
    mid = rp([start, item(0, 'a', 'age bias'), item(0, 'b', ''), item(0, 'b')])  # dup counted once
    assert (mid['batch'], mid['item'], mid['at_batch_survey']) == (0, 2, False)
    assert mid['last_invalid_description'] == 'age bias'  # latest NON-empty
    full = [item(0, q) for q in 'abc']
    assert rp(full)['at_batch_survey'] and rp(full)['item'] == 3
    nxt = rp(full + [done(0), item(1, 'x', 'sex bias')])
    assert (nxt['batch'], nxt['item'], nxt['last_invalid_description']) == (1, 1, 'sex bias')
    assert rp(full + [done(0)])['last_invalid_description'] is None  # not carried across batches
    all_done = full + [done(0), done(1), done(2)]
    assert rp(all_done)['batch'] == 3 and not rp(all_done)['finished']  # end-of-study left
    assert rp(all_done + [{'type': 'end_of_study', 'mode': 'real'}])['finished']
    # modes are kept separate
    free = rp(full + [done(0)], 'free')
    assert (free['batch'], free['item']) == (0, 0)
    assert rp([item(0, 'a', mode='free')])['item'] == 0


def test_session_start_returns_resume(client):
    assert client.post('/api/session/start', headers=h()).json['resume']['item'] == 0
    client.post('/api/survey/submit', headers=h(),
                json={'batch': 0, 'question_id': 'q', 'responses': {'q3_invalid_description': 'd'}})
    r = client.post('/api/session/start', headers=h()).json['resume']
    assert (r['batch'], r['item'], r['last_invalid_description']) == (0, 1, 'd')
    assert client.post('/api/session/start?mode=free', headers=ht()).json['resume']['item'] == 0
