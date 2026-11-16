// Headless walk of /?mode=tutorial against a running Flask (STUDY_AUTH=off, scratch RESPONSES_DIR).
//   NODE_PATH=<dir with jsdom>/node_modules node tutorial_smoke.js http://127.0.0.1:<port> [key]
// Chat is stubbed in the page's fetch (records the endpoint + body); the backend tests check
// that /api/tutorial/chat sends the base model to vLLM.
const { JSDOM, ResourceLoader, VirtualConsole } = require('jsdom');
const base = process.argv[2], key = process.argv[3];
class LocalOnly extends ResourceLoader {
  fetch(url, opts) { return url.startsWith(base) ? super.fetch(url, opts) : Promise.resolve(Buffer.from('')); }
}
const errors = [], calls = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(String(e.message || e)));
vc.on('error', (...a) => errors.push(a.join(' ')));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const check = (ok, msg) => { if (!ok) throw new Error(msg); };

(async () => {
  const dom = await JSDOM.fromURL(`${base}/?mode=tutorial${key ? '&k=' + key : ''}`, {
    runScripts: 'dangerously', resources: new LocalOnly(), virtualConsole: vc, pretendToBeVisual: true,
    beforeParse(w) {
      w.alert = m => errors.push('alert: ' + m);
      w.scrollTo = () => {};  // not implemented in jsdom
      w.fetch = (u, o) => {
        calls.push({ url: String(u), body: o && o.body });
        if (String(u).includes('/api/tutorial/chat')) {
          return Promise.resolve(new Response(JSON.stringify({ response: 'stub reply' }),
                                              { headers: { 'Content-Type': 'application/json' } }));
        }
        return fetch(new URL(u, base), o);
      };
    },
  });
  const w = dom.window, d = w.document, $ = s => d.querySelector(s), $$ = s => [...d.querySelectorAll(s)];
  d.dispatchEvent(new w.Event('DOMContentLoaded'));
  for (let i = 0; i < 50 && !$('#tutorial-step-label'); i++) await sleep(100);
  const notes = () => $$('[data-note]').map(n => n.dataset.note).sort().join(',');
  const label = () => $('#tutorial-step-label').textContent;
  const tabs = () => $$('#right-tabs:not(.hidden) .right-tab').map(t => t.textContent.trim());
  const visibleQ = () => $$('.survey-question:not(.hidden)').map(q => q.dataset.questionId);

  const expect = {
    1() {
      check($('#btn-start-study') && d.body.textContent.includes('same LLM'), 'step1 intro');
      check($('#num-spurious-types').textContent === '3' && /^\d+$/.test($('#num-questions').textContent), 'step1 counts');
      check(!$('#intro-participant-id'), 'step1 participant id shown');
      check(notes() === '', 'step1 notes ' + notes());
    },
    2() {
      check($('#qa-panel .qa-question') && $('#response-panel .model-reasoning'), 'step2 panels');
      check(tabs().length === 0 && $('#interp-tool-panel').classList.contains('hidden'), 'step2 has extra panel');
      check(notes() === 'chat,question,response', 'step2 notes ' + notes());
      check($$('#chat-panel .chat-message').length >= 2, 'chat not seeded');
      check(!$('.badge, [class*="bg-purple"]') && !$('#qa-panel').textContent.includes('clinically correct:'), 'prototype labels');
    },
    3() {
      check($('#survey-modal-container #survey-questions-container .survey-question'), 'step3 survey');
      const v = visibleQ();
      for (const q of ['q1_answer_correct', 'q1_confidence', 'q2_clinically_valid', 'q2_confidence',
                       'q3_same_as_before', 'q3_invalid_description', 'q4_inference_method'])
        check(v.includes(q), 'step3 missing ' + q);
      check(notes() === 'q1,q2,q3,q4', 'step3 notes ' + notes());
      check($('[data-question-id="q3_same_as_before"] [data-note="q3"]'), 'q3 note not beside q3');
    },
    4() {
      check(tabs().join('|') === 'Model response|Extra panel', 'step4 tabs ' + tabs());
      check(!$('#interp-tool-panel').classList.contains('hidden') && $('.jl-grid'), 'step4 jlens not open');
      check($('#interp-tool-panel [data-note="jlens"]').textContent.includes('At each layer or depth of processing'), 'jlens note');
      check($('#interp-tool-panel [data-note="span"]'), 'span note');
    },
    5() {
      check(tabs().join('|') === 'Model response|Extra panel', 'step5 tabs');
      check($$('#interp-tool-panel ol li').length > 0, 'step5 sae list');
      check($('#interp-tool-panel [data-note="sae"]').textContent.includes('short plain-English description'), 'sae note');
      check($('#interp-tool-panel [data-note="span"]'), 'span note');
    },
    6() {
      check(tabs().join('|') === 'Model response|Extra panel', 'step6 tabs');
      check($$('#interp-tool-panel .lrp-w').length > 0, 'step6 lrp heatmap');
      check($('#interp-tool-panel [data-note="lrp"] strong')?.textContent === 'input question', 'lrp note');
      check(!$('#interp-tool-panel [data-note="span"]'), 'span note on lrp');
    },
    7() {
      check($$('.end-survey-option').length === 5 && $$('.end-clarity-option').length === 5, 'end-of-study questions');
      check(notes() === 'clarity,interface', 'step7 notes ' + notes());
      check(!$('#btn-finish-study'), 'submit button present');
    },
    8() { check(d.body.textContent.includes("You're ready") && $('#tutorial-restart'), 'ready screen'); },
  };

  const seen = [];
  const at = async n => {
    await sleep(80);
    expect[n]();
    seen.push(`${n}:${label()}:[${notes()}]`);
  };
  await at(1);
  $('#btn-start-study').click(); await at(2);  // Begin Study -> step 2
  // live chat (stubbed) goes to the tutorial endpoint, with the seeded history
  $('#chat-input').value = 'What if he were 30?';
  $('#chat-send-btn').click(); await sleep(80);
  const chat = calls.find(c => c.url.includes('/api/tutorial/chat'));
  check(chat && JSON.parse(chat.body).messages.length === 3, 'chat call');
  check($$('#chat-panel .chat-message').length === 4, 'chat reply not shown');
  // Instructions pop-up: opens with tutorial counts, closes by button and on step change
  $('#btn-instructions').click();
  check($('#instructions-modal #num-spurious-types').textContent === '3', 'tutorial instructions counts');
  $('#instructions-modal .btn-close-instructions').click();
  check(!$('#instructions-modal'), 'close button');
  $('#btn-instructions').click(); $('#tutorial-back').click(); await at(1);
  check(!$('#instructions-modal'), 'pop-up left open across steps');
  $('#tutorial-next').click(); await at(2);
  for (let n = 3; n <= 8; n++) { $('#tutorial-next').click(); await at(n); }
  check($('#tutorial-next').classList.contains('hidden'), 'Next shown on done');
  for (let n = 7; n >= 1; n--) { $('#tutorial-back').click(); await at(n); }
  check($('#tutorial-back').disabled, 'Back enabled on step 1');
  $('#tutorial-next').click(); await at(2);
  check($$('#chat-panel .chat-message').length === 4, 'chat lost across steps');
  $('#btn-open-survey').click(); await at(3);  // Begin Evaluation -> step 3

  const gated = calls.filter(c => /\/api\/(?!tutorial\/)/.test(c.url));
  check(gated.length === 0, 'non-tutorial endpoints called: ' + gated.map(c => c.url));
  const completes = calls.filter(c => c.url.includes('/tutorial/complete')).length;
  check(completes === (key ? 1 : 0), 'tutorial/complete calls ' + completes);
  console.log(seen.join('\n'));
  console.log(errors.length ? 'ERRORS:\n' + errors.join('\n') : 'no JS errors');
  process.exit(errors.length ? 1 : 0);
})().catch(e => { console.log('FAIL', e.message, errors); process.exit(1); });
