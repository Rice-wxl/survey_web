"""
Flask server for the clinician audit study.

Two modes, set by the KEY (a `mode` in the link is ignored, so no one can switch by editing it):
  real  blind: balanced tool assignment (4 conditions rotated over the models), no item labels.
  free  prototype: item labels shown, every readout returned, tool picked by a tab toggle.
Plus /api/tutorial/* (frontend `?mode=tutorial`): one practice item, chat with the base
model, no key needed, nothing saved except a tutorial_complete record when a key is sent.

Three kinds of key (participants.json):
  clinician  real mode: a balanced schedule, questions only in order (no jumping ahead).
  trial      (`"trial": true`) dry runs, still real mode and blinded: fixed model order, the
             condition picked per request (`?condition=`, the Panel switch), free
             navigation, every record tagged `trial`; no schedule.
  dev        (`"trial": true, "dev": true`; also everyone when STUDY_AUTH=off) free mode,
             the prototype: everything visible.

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
# The model (bias) order is fixed and the same for everyone; a schedule is only a condition
# offset, so 4 schedules. Config.ORGANISMS is APPEND-ONLY: new biases go at the end, which
# leaves every existing batch's condition (and an in-progress participant's resume point)
# unchanged and appends the new batches before the end-of-study questions.
SCHEDULES = list(range(len(Config.CONDITIONS)))
_write_lock = threading.Lock()


# ============== Plan ==============

def build_plan(pid, schedule, mode):
    """Batches for one participant, in the fixed Config.ORGANISMS order. Organism j gets
    condition (j + offset) % 4, so any 3 consecutive models get 3 distinct conditions and the
    left-out one rotates across models; the 4 schedules together put every organism under
    every condition exactly once."""
    offset = SCHEDULES[schedule % len(SCHEDULES)]
    batches = []
    for j, key in enumerate(Config.ORGANISMS):
        items = ORGS[key]['items']
        if Config.ITEMS_PER_ORGANISM < len(items) and key in Config.NEGATIVE_CONTROLS:
            items = items[:Config.ITEMS_PER_ORGANISM]   # controlled-only panel
        elif Config.ITEMS_PER_ORGANISM < len(items):
            per = Config.ITEMS_PER_ORGANISM // 3
            items = [it for v in ('spurious', 'counterfactual', 'controlled')
                     for it in [x for x in items if x['variant'] == v][:per]]
        ids = [it['id'] for it in items]
        # Same question order for every participant (seeded by the organism only), so only
        # the tool differs between participants.
        random.Random(key).shuffle(ids)
        batches.append({
            'label': f'Model {j + 1}',
            'organism': key,
            'condition': Config.CONDITIONS[(j + offset) % len(Config.CONDITIONS)] if mode == 'real' else None,
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


def plan():
    """This request's batches: a trial key's real-mode condition is the one it asked for."""
    batches = build_plan(g.pid, g.schedule, g.mode)
    if g.trial and g.mode == 'real':
        for b in batches:
            b['condition'] = g.condition or 'blackbox'
    return batches


def current_batch(b):
    batches = plan()
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
    (lowest number on ties), so participants 1-4 get 0-3 -- a full organism x condition
    square -- then 0-3 again. Keys marked `"dropped": true` (by hand, add_participant.py
    --drop) don't count, so a replacement takes over a dropout's schedule. Written back to
    participants.json under a lock so two first visits can't take the same one; returns the
    updated entry."""
    with _write_lock:
        people = json.loads(Config.PARTICIPANTS_FILE.read_text())
        if people[key].get('schedule') is None:
            used = Counter(p['schedule'] for p in people.values()
                           if p.get('schedule') is not None and not p.get('trial')
                           and not p.get('dropped'))
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
    if people is None:  # STUDY_AUTH=off: a local dev server, everyone a dev key (free mode)
        who = {'pid': request.headers.get('X-Participant', 'DEV'), 'trial': True, 'dev': True}
    elif key in people:
        who = people[key]
        if who.get('schedule') is None and not who.get('trial'):
            who = assign_schedule(key)
    elif request.path.startswith('/api/tutorial/'):
        who = {'pid': None}  # tutorial needs no key; nothing is saved without one
    else:
        return jsonify({'error': 'Invalid or missing access key'}), 403
    g.trial = bool(who.get('trial'))
    g.pid, g.schedule = who['pid'], 0 if g.trial else int(who.get('schedule') or 0)
    cond = request.args.get('condition')
    g.condition = cond if g.trial and cond in Config.CONDITIONS else None
    if request.path.startswith('/api/tutorial/'):
        g.mode = 'tutorial'
        return
    # The key decides the mode; ?mode= is ignored. Dev keys must also be trial keys.
    g.mode = 'free' if who.get('dev') and g.trial else 'real'


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
    batches = plan()
    # STUDY_AUTH=off (dev server, everyone is DEV): always start at Model 1, question 1;
    # DEV.jsonl keeps every record, it just isn't used to resume.
    records = load_records(g.pid) if Config.AUTH else []
    resume = resume_point(records, g.mode, [len(b['item_ids']) for b in batches])
    save_response({'type': 'session_start', 'resume': resume})
    return jsonify({
        'participant_id': g.pid,
        'mode': g.mode,
        'trial': g.trial,   # condition switch + batch/question dropdowns
        'n_batches_shown': Config.n_batches_shown(),  # planned total, for the instructions/header
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
    if not g.trial:  # clinicians open questions in order: answered ones or the current one
        r = resume_point(load_records(g.pid), g.mode, [len(x['item_ids']) for x in plan()])
        if (b, i) > (r['batch'], r['item']):
            return jsonify({'error': 'Questions open in order.'}), 403
    it = next(x for x in ORGS[batch['organism']]['items'] if x['id'] == batch['item_ids'][i])
    out = {k: it[k] for k in ('id', 'question', 'options', 'user_prompt', 'response',
                              'model_answer')}
    if g.mode == 'free':
        out.update({k: it.get(k) for k in ('variant', 'biased_answer', 'correct_answer')})
        # SAE = the TF-IDF ranking, as in the real study. The activation / gradient
        # rankings are no longer served or exported (2026-11-04); they stay on disk beside
        # each panel (build_survey_readouts.py) as a record.
        out['readouts'] = {'jlens': it['jlens'], 'sae': it['sae_tfidf'],
                           # AttnLRP word heatmap (mean / max contrast), free mode only
                           'lrp': it.get('lrp') or {}}
    elif batch['condition'] == 'jlens':
        out['readouts'] = {'jlens': it['jlens']}
    elif batch['condition'] == 'sae':
        out['readouts'] = {'sae': it['sae_tfidf']}  # TF-IDF ranking (2026-10-26), not raw activation
    elif batch['condition'] == 'lrp':
        out['readouts'] = {'lrp': {'max': it['lrp']['max']}}  # the contrast drawLrp shows
    else:
        out['readouts'] = {}
    return jsonify(out)


# ============== Live chat (no whitebox readouts) ==============

def _prompt_core(question, options):
    return f'Question: {question}\n\nOptions:\n' + '\n'.join(f'{k}. {options[k]}' for k in sorted(options))


def cf_prompt(it, cf):
    """The item's own templated prompt with the vignette/option text swapped for the
    clinician's edit (letters fixed), or (None, error). The template text is never taken
    from the client."""
    q, opts = (cf or {}).get('question'), (cf or {}).get('options')
    if not (isinstance(q, str) and q.strip() and isinstance(opts, dict)
            and set(opts) == set(it['options'])
            and all(isinstance(v, str) and v.strip() for v in opts.values())):
        return None, (jsonify({'error': 'The edited question and every option must be filled in.'}), 400)
    core = _prompt_core(it['question'], it['options'])
    return it['user_prompt'].replace(core, _prompt_core(q.strip(), {k: v.strip() for k, v in opts.items()})), None


def chat_turn(model, it, data):
    """One chat turn for item `it`: for a counterfactual, rebuild its first user turn
    server-side and give the first reply the cached responses' token cap. Returns
    (reply, messages actually sent, None) or (None, None, error)."""
    messages = data.get('messages')
    max_tokens = Config.CHAT_MAX_TOKENS
    if data.get('kind') == 'counterfactual' and isinstance(messages, list) and messages:
        prompt, err = cf_prompt(it, data.get('cf'))
        if err:
            return None, None, err
        messages = [{'role': 'user', 'content': prompt}, *messages[1:]]
        if len(messages) == 1:
            max_tokens = Config.CF_MAX_TOKENS
    reply, err = chat_reply(model, messages, max_tokens)
    return (None, None, err) if err else (reply, messages, None)


def chat_reply(model, messages, max_tokens=Config.CHAT_MAX_TOKENS):
    """Validate user/assistant turns and get one vLLM reply: (reply, None) or (None, error)."""
    ok = (isinstance(messages, list) and messages and messages[-1].get('role') == 'user'
          and all(m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str)
                  for m in messages))
    if not ok:
        return None, (jsonify({'error': 'messages must be user/assistant turns ending with user'}), 400)
    messages = [{'role': m['role'], 'content': m['content']} for m in messages]
    if sum(m['role'] == 'user' for m in messages) > Config.CHAT_MAX_TURNS:
        return None, (jsonify({'error': 'Message limit reached. Start a new conversation.'}), 429)

    body = {'model': model, 'messages': messages, 'max_tokens': max_tokens, **Config.GEN}
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
    if data.get('item_id') not in batch['item_ids']:
        abort(404)
    it = next(x for x in ORGS[batch['organism']]['items'] if x['id'] == data['item_id'])
    # A negative-control batch has no LoRA: its chat goes to the base model itself.
    model = Config.BASE_MODEL if batch['organism'] in Config.NEGATIVE_CONTROLS else batch['organism']
    reply, messages, err = chat_turn(model, it, data)
    if err:
        return err
    record = {'type': 'chat', 'batch': int(data['batch']), 'item_id': it['id'],
              'conversation_id': data.get('conversation_id'),
              'conversation_index': data.get('conversation_index'),
              'kind': data.get('kind'),
              'messages': [{'role': m['role'], 'content': m['content']} for m in messages],
              'reply': reply}
    if data.get('kind') == 'counterfactual':
        cf = data['cf']
        record.update(cf_question=cf['question'], cf_options=cf['options'],
                      cf_edited=(cf['question'].strip(), {k: v.strip() for k, v in cf['options'].items()})
                                != (it['question'], it['options']))
    save_response(record)
    return jsonify({'response': reply, 'prompt': messages[0]['content']})


# ============== Tutorial (no key needed; nothing saved but tutorial_complete) ==============

@app.route('/api/tutorial/item', methods=['GET'])
def tutorial_item():
    out = {k: TUTORIAL[k] for k in ('id', 'question', 'options', 'user_prompt', 'response',
                                    'model_answer')}
    # SAE = the TF-IDF ranking as in the real study (activation `sae` only if not built yet)
    out['readouts'] = {'jlens': TUTORIAL['jlens'], 'sae': TUTORIAL.get('sae_tfidf') or TUTORIAL['sae'],
                       'lrp': TUTORIAL.get('lrp') or {}}
    out['n_models'], out['n_items'] = Config.n_batches_shown(), Config.ITEMS_PER_ORGANISM  # intro step
    out['survey'] = survey_module.get_questions()  # /api/survey/questions is key-gated
    return jsonify(out)


@app.route('/api/tutorial/chat', methods=['POST'])
def tutorial_chat():
    reply, messages, err = chat_turn(Config.BASE_MODEL, TUTORIAL, request.json or {})
    return err or jsonify({'response': reply, 'prompt': messages[0]['content']})


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
              'timestamp': datetime.now().isoformat(),
              **({'trial': True} if g.trial else {}), **record}
    if 'batch' in record:
        batches = plan()
        if 0 <= record['batch'] < len(batches):
            b = batches[record['batch']]
            record.update(organism=b['organism'], condition=b['condition'])
    Path(Config.RESPONSES_DIR).mkdir(parents=True, exist_ok=True)
    with _write_lock, open(responses_file(g.pid), 'a') as f:
        f.write(json.dumps(record) + '\n')


if __name__ == '__main__':
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
