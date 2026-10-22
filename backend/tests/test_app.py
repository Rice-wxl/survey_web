"""Study-server checks: Latin-square balance, access gate, blinding, chat validation."""
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config  # noqa: E402

KEY = 'test-key'


@pytest.fixture
def client(tmp_path, monkeypatch):
    people = tmp_path / 'participants.json'
    people.write_text(json.dumps({KEY: {'pid': 'P01', 'schedule': 4}}))
    monkeypatch.setattr(Config, 'PARTICIPANTS_FILE', people)
    monkeypatch.setattr(Config, 'RESPONSES_DIR', tmp_path / 'responses')
    monkeypatch.setattr(Config, 'VLLM_URL', 'http://127.0.0.1:9')  # nothing listens
    import app
    return app.app.test_client()


def h():
    return {'X-Study-Key': KEY}


def test_latin_square_balanced():
    import app
    cells, positions = Counter(), Counter()
    for s in range(6):
        for pos, b in enumerate(app.build_plan('P', s, 'real')):
            cells[(b['organism'], b['condition'])] += 1
            positions[(b['organism'], pos)] += 1
    assert set(cells.values()) == {2} and len(cells) == 9
    assert set(positions.values()) == {2} and len(positions) == 9


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


def test_free_mode_is_unblinded(client):
    plan = client.post('/api/session/start?mode=free', headers=h()).json
    assert all(b['condition'] is None and b['organism'] for b in plan['batches'])
    item = client.get('/api/batch/0/item/0?mode=free', headers=h()).json
    assert item['variant'] in ('spurious', 'counterfactual', 'controlled')
    assert set(item['readouts']) == {'jlens', 'sae', 'sae_grad', 'sae_orig', 'sae_grad_orig',
                                     'sae_tfidf', 'sae_tfidf_orig'}
    assert set(item['readouts']['sae_tfidf']) == {'question', 'reasoning'}  # TF-IDF source
    assert len(item['readouts']['sae_tfidf']['question']) == 25
    assert set(item['readouts']['sae_orig']) == {'question', 'reasoning'}  # free-mode label switch
    assert item['readouts']['sae_orig'] != item['readouts']['sae']
    assert set(item['readouts']['sae_grad']) == {'mean', 'max'}  # free-mode source toggle
    assert set(item['readouts']['sae_grad']['mean']) == {'question', 'reasoning'}
    assert len(item['readouts']['jlens']['question']) == 15  # the auditor's band, layers 14-28


def test_chat_validation(client):
    bad = client.post('/api/model/chat', headers=h(), json={'batch': 0, 'messages': []})
    assert bad.status_code == 400
    many = [{'role': r, 'content': 'x'} for _ in range(Config.CHAT_MAX_TURNS + 1)
            for r in ('user', 'assistant')][:-1]
    assert client.post('/api/model/chat', headers=h(),
                       json={'batch': 0, 'messages': many}).status_code == 429
    down = client.post('/api/model/chat', headers=h(),
                       json={'batch': 0, 'messages': [{'role': 'user', 'content': 'hi'}]})
    assert down.status_code == 502


def test_responses_tagged(client):
    client.post('/api/survey/submit?mode=free', headers=h(),
                json={'batch': 1, 'question_id': 'q', 'responses': {}})
    rec = json.loads((Config.RESPONSES_DIR / 'P01.jsonl').read_text().splitlines()[-1])
    assert rec['mode'] == 'free' and rec['participant_id'] == 'P01' and rec['organism']


def test_tutorial_needs_no_key_and_hides_sae_grad(client):
    item = client.get('/api/tutorial/item').json
    assert set(item['readouts']) == {'jlens', 'sae'}
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
    assert r.json == {'response': 'ok'} and sent['model'] == Config.BASE_MODEL
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
    people.write_text(json.dumps({f'k{i}': {'pid': f'C{i}', 'schedule': None} for i in range(4)}))
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
    assert client.post('/api/session/start?mode=free', headers=h()).json['resume']['item'] == 0
