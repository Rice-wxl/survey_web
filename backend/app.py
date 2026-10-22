"""
Flask server for the clinician audit study.

Two modes, chosen per request (`mode` = real | free):
  real  blind: Latin-square tool assignment, no item labels, verdict form per organism.
  free  prototype: item labels shown, every readout returned, tool picked by a tab toggle.
Plus /api/tutorial/* (frontend `?mode=tutorial`): one practice item, chat with the base
model, no key needed, nothing saved except a tutorial_complete record when a key is sent.

The plan is a pure function of (participant, schedule, mode), so nothing lives in memory:
reloading the page resumes the same assignment, and resume_point() reads the saved
answers to pick up where the participant left off. Readouts are filtered server-side, so a
real-mode participant can never fetch a tool they were not assigned.
"""

import json
import os
import random
import re
import threading
import urllib.request
from datetime import datetime
from collections import Counter
from itertools import permutations
from pathlib import Path

from flask import Flask, abort, g, jsonify, request, send_from_directory

from config import Config
from modules.survey_module import SurveyModule

app = Flask(__name__, static_folder='../frontend', static_url_path='')
survey_module = SurveyModule()
ORGS = {k: json.loads((Config.ORGANISMS_DIR / f'{k}.json').read_text()) for k in Config.ORGANISMS}
TUTORIAL = json.loads(next(p for p in (Config.TUTORIAL_DIR / 'tutorial.json',
                                       Config.TUTORIAL_DIR / 'tutorial_stub.json')
                            if p.exists()).read_text())['items'][0]
SCHEDULES = list(permutations(range(len(Config.ORGANISMS))))  # 6 organism orders
_write_lock = threading.Lock()


# ============== Plan ==============

def build_plan(pid, schedule, mode):
    """Batches for one participant. Over the 6 schedules every organism is seen under
    every condition exactly twice and in every serial position."""
    s = schedule % len(SCHEDULES)
    batches = []
    for pos, j in enumerate(SCHEDULES[s]):
        key = Config.ORGANISMS[j]
        items = ORGS[key]['items']
        if Config.ITEMS_PER_ORGANISM < len(items):
            per = Config.ITEMS_PER_ORGANISM // 3
            items = [it for v in ('spurious', 'counterfactual', 'controlled')
                     for it in [x for x in items if x['variant'] == v][:per]]
        ids = [it['id'] for it in items]
        random.Random(f'{pid}:{key}').shuffle(ids)
        batches.append({
            'label': f'Model {pos + 1}',
            'organism': key,
            'condition': Config.CONDITIONS[(j + s) % 3] if mode == 'real' else None,
            'item_ids': ids,
        })
    return batches


def resume_point(records, mode, n_items):
    """Where a returning participant picks up, from their saved records of one mode.
    n_items: per-batch item counts. Items are answered in plan order, so the item index is
    the number of distinct question_ids answered in the first batch without a batch_complete;
    item == n_items means that batch's end-of-model ratings screen. batch == len(n_items)
    means only the end-of-study questions are left."""
    records = [r for r in records if r.get('mode') == mode]
    done = {r.get('batch') for r in records if r.get('type') == 'batch_complete'}
    b = next((i for i in range(len(n_items)) if i not in done), len(n_items))
    answered = [r for r in records if r.get('type') == 'item_survey' and r.get('batch') == b]
    item = min(len({r.get('question_id') for r in answered}), n_items[b]) if b < len(n_items) else 0
    descs = [(r.get('survey_responses') or {}).get('q3_invalid_description') for r in answered]
    return {'batch': b, 'item': item,
            'at_batch_survey': b < len(n_items) and item == n_items[b],
            'finished': any(r.get('type') == 'end_of_study' for r in records),
            'last_invalid_description': next((d for d in reversed(descs) if d), None)}


def responses_file(pid):
    return Path(Config.RESPONSES_DIR) / f"{re.sub(r'[^A-Za-z0-9_-]', '_', pid)}.jsonl"


def load_records(pid):
    try:
        lines = responses_file(pid).read_text().splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:  # a torn last line must not block the participant
            pass
    return out


def current_batch(b):
    batches = build_plan(g.pid, g.schedule, g.mode)
    if not 0 <= b < len(batches):
        abort(404)
    return batches[b]


# ============== Access gate ==============

def load_participants():
    if not Config.AUTH:
        return None
    try:
        return json.loads(Config.PARTICIPANTS_FILE.read_text())
    except FileNotFoundError:
        return {}


def assign_schedule(key):
    """First visit of a key added without a schedule: give it the least-used schedule
    (lowest number on ties), so participants 1-3 get 0,1,2 -- a full organism x condition
    Latin square -- then 3,4,5. Written back to participants.json under a lock so two
    first visits can't take the same one; returns the updated entry."""
    with _write_lock:
        people = json.loads(Config.PARTICIPANTS_FILE.read_text())
        if people[key].get('schedule') is None:
            used = Counter(p['schedule'] for p in people.values() if p.get('schedule') is not None)
            people[key]['schedule'] = min(range(len(SCHEDULES)), key=lambda s: (used[s], s))
            tmp = Config.PARTICIPANTS_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(people, indent=1))
            os.replace(tmp, Config.PARTICIPANTS_FILE)
        return people[key]


@app.before_request
def gate():
    if not request.path.startswith('/api/'):
        return  # static files carry no study data
    key = request.headers.get('X-Study-Key', '')
    people = load_participants()
    if people is None:  # STUDY_AUTH=off
        who = {'pid': request.headers.get('X-Participant', 'DEV'), 'schedule': 0}
    elif key in people:
        who = people[key]
        if who.get('schedule') is None:
            who = assign_schedule(key)
    elif request.path.startswith('/api/tutorial/'):
        who = {'pid': None}  # tutorial needs no key; nothing is saved without one
    else:
        return jsonify({'error': 'Invalid or missing access key'}), 403
    g.pid, g.schedule = who['pid'], int(who.get('schedule', 0))
    if request.path.startswith('/api/tutorial/'):
        g.mode = 'tutorial'
        return
    g.mode = request.args.get('mode', 'real')
    if g.mode not in ('real', 'free'):
        return jsonify({'error': 'mode must be real or free'}), 400


# ============== Static Files ==============

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)


# ============== Session / items ==============

@app.route('/api/session/start', methods=['POST'])
def start_session():
    batches = build_plan(g.pid, g.schedule, g.mode)
    resume = resume_point(load_records(g.pid), g.mode, [len(b['item_ids']) for b in batches])
    save_response({'type': 'session_start', 'resume': resume})
    return jsonify({
        'participant_id': g.pid,
        'mode': g.mode,
        'resume': resume,
        'batches': [{
            'label': b['label'],
            'condition': b['condition'],
            'n_items': len(b['item_ids']),
            # The bias name is only revealed in the unblinded prototype.
            **({'organism': b['organism']} if g.mode == 'free' else {}),
        } for b in batches],
    })


@app.route('/api/batch/<int:b>/item/<int:i>', methods=['GET'])
def get_item(b, i):
    batch = current_batch(b)
    if not 0 <= i < len(batch['item_ids']):
        abort(404)
    it = next(x for x in ORGS[batch['organism']]['items'] if x['id'] == batch['item_ids'][i])
    out = {k: it[k] for k in ('id', 'question', 'options', 'user_prompt', 'response',
                              'model_answer')}
    if g.mode == 'free':
        out.update({k: it.get(k) for k in ('variant', 'biased_answer', 'correct_answer')})
        out['readouts'] = {'jlens': it['jlens'], 'sae': it['sae'],
                           # gradient-ranked SAE, for the free-mode source toggle only
                           'sae_grad': it.get('sae_grad') or {},
                           # original-prompt SAE labels, for the free-mode label switch only
                           'sae_orig': it.get('sae_orig') or {},
                           'sae_grad_orig': it.get('sae_grad_orig') or {},
                           'sae_tfidf': it.get('sae_tfidf') or {},
                           'sae_tfidf_orig': it.get('sae_tfidf_orig') or {}}
    elif batch['condition'] in ('jlens', 'sae'):
        out['readouts'] = {batch['condition']: it[batch['condition']]}
    else:
        out['readouts'] = {}
    return jsonify(out)


# ============== Live chat (no whitebox readouts) ==============

def chat_reply(model, messages):
    """Validate user/assistant turns and get one vLLM reply: (reply, None) or (None, error)."""
    ok = (isinstance(messages, list) and messages and messages[-1].get('role') == 'user'
          and all(m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str)
                  for m in messages))
    if not ok:
        return None, (jsonify({'error': 'messages must be user/assistant turns ending with user'}), 400)
    messages = [{'role': m['role'], 'content': m['content']} for m in messages]
    if sum(m['role'] == 'user' for m in messages) > Config.CHAT_MAX_TURNS:
        return None, (jsonify({'error': 'Turn limit reached. Start a new conversation.'}), 429)

    body = {'model': model, 'messages': messages,
            'max_tokens': Config.CHAT_MAX_TOKENS, **Config.GEN}
    req = urllib.request.Request(f'{Config.VLLM_URL}/v1/chat/completions',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())['choices'][0]['message']['content'], None
    except Exception as e:  # vLLM down, or context too long
        app.logger.warning('chat failed: %s', e)
        return None, (jsonify({'error': 'The model could not answer. Try a new conversation.'}), 502)


@app.route('/api/model/chat', methods=['POST'])
def model_chat():
    data = request.json or {}
    batch = current_batch(int(data.get('batch', -1)))
    messages = data.get('messages')
    reply, err = chat_reply(batch['organism'], messages)
    if err:
        return err
    save_response({'type': 'chat', 'batch': int(data['batch']),
                   'item_id': data.get('item_id'),
                   'messages': [{'role': m['role'], 'content': m['content']} for m in messages],
                   'reply': reply})
    return jsonify({'response': reply})


# ============== Tutorial (no key needed; nothing saved but tutorial_complete) ==============

@app.route('/api/tutorial/item', methods=['GET'])
def tutorial_item():
    out = {k: TUTORIAL[k] for k in ('id', 'question', 'options', 'user_prompt', 'response',
                                    'model_answer')}
    out['readouts'] = {'jlens': TUTORIAL['jlens'], 'sae': TUTORIAL['sae']}
    out['n_models'], out['n_items'] = len(Config.ORGANISMS), Config.ITEMS_PER_ORGANISM  # intro step
    out['survey'] = survey_module.get_questions()  # /api/survey/questions is key-gated
    return jsonify(out)


@app.route('/api/tutorial/chat', methods=['POST'])
def tutorial_chat():
    reply, err = chat_reply(Config.BASE_MODEL, (request.json or {}).get('messages'))
    return err or jsonify({'response': reply})


@app.route('/api/tutorial/complete', methods=['POST'])
def tutorial_complete():
    if g.pid is None:
        return jsonify({'saved': False})
    save_response({'type': 'tutorial_complete'})
    return jsonify({'saved': True})


# ============== Survey Endpoints ==============

@app.route('/api/survey/questions', methods=['GET'])
def get_survey_questions():
    return jsonify(survey_module.get_questions())


@app.route('/api/survey/submit', methods=['POST'])
def submit_survey():
    data = request.json or {}
    save_response({'type': 'item_survey', 'batch': int(data.get('batch', -1)),
                   'question_id': data.get('question_id'),
                   'survey_responses': data.get('responses'),
                   'timing': data.get('timing_data', {})})
    return jsonify({'success': True})


@app.route('/api/survey/batch_complete', methods=['POST'])
def complete_batch():
    data = request.json or {}
    save_response({'type': 'batch_complete', 'batch': int(data.get('batch', -1)),
                   'survey_responses': data.get('responses')})
    return jsonify({'success': True})


@app.route('/api/survey/end_of_study', methods=['POST'])
def end_of_study_survey():
    data = request.json or {}
    save_response({'type': 'end_of_study',
                   'most_helpful_interface': data.get('most_helpful_interface'),
                   'panel_clarity': data.get('panel_clarity'),
                   'comments': data.get('comments', '')})
    return jsonify({'success': True})


# ============== Helper Functions ==============

def save_response(record):
    """Append one record to the participant's JSONL, stamped with who/when/mode and,
    when the record names a batch, the organism + condition it was collected under."""
    record = {'participant_id': g.pid, 'mode': g.mode, 'schedule': g.schedule,
              'timestamp': datetime.now().isoformat(), **record}
    if 'batch' in record:
        batches = build_plan(g.pid, g.schedule, g.mode)
        if 0 <= record['batch'] < len(batches):
            b = batches[record['batch']]
            record.update(organism=b['organism'], condition=b['condition'])
    Path(Config.RESPONSES_DIR).mkdir(parents=True, exist_ok=True)
    with _write_lock, open(responses_file(g.pid), 'a') as f:
        f.write(json.dumps(record) + '\n')


if __name__ == '__main__':
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
