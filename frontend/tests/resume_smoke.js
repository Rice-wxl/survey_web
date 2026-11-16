// Headless check of "continue where you left off" against a running Flask
// (keys on, a trial key in PARTICIPANTS_FILE, fresh scratch RESPONSES_DIR, default 10 items
// per model). Not STUDY_AUTH=off: that dev server always starts fresh, it never resumes.
//   NODE_PATH=<dir with jsdom>/node_modules node resume_smoke.js http://127.0.0.1:<port> <trial key>
// Each "reload" is a new page load; answers go through the real survey modal.
const { JSDOM, ResourceLoader, VirtualConsole } = require('jsdom');
const base = process.argv[2], key = process.argv[3];
class LocalOnly extends ResourceLoader {
  fetch(url, opts) { return url.startsWith(base) ? super.fetch(url, opts) : Promise.resolve(Buffer.from('')); }
}
const errors = [], log = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const check = (ok, msg) => { if (!ok) throw new Error(msg); };
const until = async (f, msg) => { for (let i = 0; i < 100; i++) { if (f()) return; await sleep(50); } throw new Error('timeout: ' + msg); };

async function open(mode) {
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errors.push(String(e.message || e)));
  vc.on('error', (...a) => errors.push(a.join(' ')));
  const dom = await JSDOM.fromURL(`${base}/?k=${key}${mode === 'free' ? '&mode=free' : ''}`, {
    runScripts: 'dangerously', resources: new LocalOnly(), virtualConsole: vc, pretendToBeVisual: true,
    beforeParse(w) {
      w.alert = m => errors.push('alert: ' + m);
      w.scrollTo = () => {};
      w.submits = 0;  // w.slowSubmit = ms simulates the relay stall that triple-submitted on 2026-10-22
      w.fetch = async (u, o) => {
        if (String(u).includes('/survey/submit')) { w.submits++; if (w.slowSubmit) await sleep(w.slowSubmit); }
        return fetch(new URL(u, base), o);
      };
    },
  });
  const w = dom.window, d = w.document;
  d.dispatchEvent(new w.Event('DOMContentLoaded'));
  const p = { w, d, $: s => d.querySelector(s), $$: s => [...d.querySelectorAll(s)] };
  await until(() => p.$('#btn-start-study') || p.$('#intro-finished'), 'intro');
  return p;
}
const startLabel = p => (p.$('#btn-start-study')?.textContent || p.$('#intro-finished').textContent).trim();
const qnum = p => p.$('#current-question-num')?.textContent
  ?? (p.$('#free-question-select') && String(+p.$('#free-question-select').value + 1));

// Fill every visible question of the open modal / batch survey: q2 = "Biased" (so a description is
// written), single-choice/likert = first option, multi = first option, text = filler.
async function fill(p) {
  for (let pass = 0; pass < 5; pass++) {
    for (const q of p.$$('.survey-question:not(.hidden)')) {
      const id = q.dataset.questionId;
      if (q.querySelector('.selected')) continue;
      const ta = q.querySelector('textarea');
      if (ta) { if (!ta.value) { ta.value = `pattern seen at ${qnum(p)}`; ta.dispatchEvent(new p.w.Event('input')); } continue; }
      if (q.querySelector('.rank-widget')) {   // rank every required source (pool re-renders per click)
        let b;
        while ((b = [...q.querySelectorAll('.rank-pool .rank-option')].find(x => x.dataset.value !== 'Other'))) b.click();
        continue;
      }
      const btn = id === 'q2_clinically_valid' ? q.querySelector('[data-value="Biased"]')
                                               : q.querySelector('.survey-option, .likert-option');
      btn?.click();
    }
    await sleep(10);
  }
}

async function answer(p, n) {  // answer n questions from the current one
  const ids = [];
  for (let k = 0; k < n; k++) {
    await until(() => p.$('#btn-open-survey') && p.w.studyApp.currentItem?.id
                      && !ids.includes(p.w.studyApp.currentItem.id), 'question');
    ids.push(p.w.studyApp.currentItem.id);
    p.$('#btn-open-survey').click();
    await fill(p);
    p.$('#btn-submit-survey').click();
    await until(() => !p.$('#survey-modal-container'), 'submit');
  }
  await until(() => p.$('#btn-next-batch') || !ids.includes(p.w.studyApp.currentItem?.id), 'next');
  return ids;
}

const d_esc = p => p.d.dispatchEvent(new p.w.KeyboardEvent('keydown', { key: 'Escape' }));
const itemId = async (mode, b, i) => (await (await fetch(`${base}/api/batch/${b}/item/${i}?mode=${mode}`)).json()).id;

(async () => {
  // --- real mode: fresh, answer 3, reload ---
  let p = await open('real');
  check(startLabel(p).startsWith('Begin Study'), 'fresh: ' + startLabel(p));
  check(p.$('.intro-instructions #num-spurious-types').textContent === '3', 'intro counts');
  p.$('#btn-start-study').click();
  // Instructions pop-up on the task screen: real counts, no intro-only text, Escape closes
  await until(() => p.$('#btn-instructions'), 'instructions button');
  p.$('#btn-instructions').click();
  const im = p.$('#instructions-modal');
  check(im && im.textContent.includes('same LLM') && im.textContent.includes('For each question'), 'instructions content');
  check(im.querySelector('#num-spurious-types').textContent === '3' && /^\d+$/.test(im.querySelector('#num-questions').textContent), 'instructions counts');
  check(!/Thank you|Before you start|Begin Study/.test(im.textContent), 'intro-only text in pop-up');
  d_esc(p); check(!p.$('#instructions-modal'), 'Escape did not close');
  const first3 = await answer(p, 3);
  check(qnum(p) === '4', 'after 3 answers at q' + qnum(p));

  p = await open('real');
  check(startLabel(p) === 'Continue where you left off (Model 1, question 4)', 'reload 1: ' + startLabel(p));
  log.push('reload after 3: ' + startLabel(p));
  p.$('#btn-start-study').click();
  await until(() => p.w.studyApp.currentItem?.id, 'q4 item');
  const want = await itemId('real', 0, 3);
  check(qnum(p) === '4' && p.w.studyApp.currentItem.id === want && !first3.includes(want),
        `landed q${qnum(p)} ${p.w.studyApp.currentItem.id} want ${want}`);
  log.push(`landed on question 4, item ${want}`);
  // "Same as before" works after resume: the restored description is offered
  check(p.w.surveyModule.lastInvalidDescription === 'pattern seen at 1', 'restored desc ' + p.w.surveyModule.lastInvalidDescription);
  p.$('#btn-open-survey').click();
  p.$('[data-question-id="q2_clinically_valid"] [data-value="Biased"]').click();
  check(!p.$('[data-question-id="q3_same_as_before"]').classList.contains('hidden'), '"Same as before" not offered');
  p.$('#btn-close-survey').click();

  // --- finish Model 1's questions, reload at the model-complete screen ---
  await answer(p, 7);
  check(p.$('#btn-next-batch'), 'no batch survey after q10');
  p = await open('real');
  check(startLabel(p) === 'Continue where you left off (Model 1: complete)', 'reload 2: ' + startLabel(p));
  log.push('reload after 10: ' + startLabel(p));
  p.$('#btn-start-study').click();
  await until(() => p.$('#btn-next-batch'), 'model-complete screen');
  await fill(p);
  p.$('#btn-next-batch').click();
  await until(() => qnum(p) === '1' && p.w.studyApp.batchIndex === 1, 'model 2');

  p = await open('real');
  check(startLabel(p) === 'Continue where you left off (Model 2, question 1)', 'reload 3: ' + startLabel(p));
  log.push('reload after ratings: ' + startLabel(p));
  p.$('#btn-start-study').click();
  await until(() => p.w.studyApp.currentItem?.id, 'model 2 item');
  check(p.w.studyApp.batchIndex === 1 && p.w.studyApp.currentItem.id === await itemId('real', 1, 0), 'model 2 q1 item');
  check(p.w.surveyModule.lastInvalidDescription === null, 'description leaked into model 2');

  // --- a trial key: blinded dropdowns + Panel switch in real mode ---
  check(p.$('#free-batch-select') && p.$('#trial-condition-select'), 'trial session lacks dropdowns / panel switch');
  p = await open('real');
  p.$('#btn-start-study').click();
  await until(() => p.$('#free-batch-select') && p.w.studyApp.currentItem?.id, 'nav task');
  const names = [...p.$('#free-batch-select').options].map(o => o.textContent);
  check(names.join('|') === 'Model 1|Model 2|Model 3', 'nav labels not blinded: ' + names);
  const pickR = (id, v) => { const el = p.$(id); el.value = String(v); el.dispatchEvent(new p.w.Event('change')); };
  const want3 = await itemId('real', 1, 2);
  pickR('#free-batch-select', 1);
  await until(() => p.w.studyApp.batchIndex === 1 && p.$('#free-question-select')?.value === '0' && p.w.studyApp.currentItem, 'nav batch');
  pickR('#free-question-select', 2);
  await until(() => p.w.studyApp.currentItem?.id === want3, 'nav question');
  check(!p.$('.badge, [class*="bg-purple"]'), 'nav shows prototype labels');
  log.push(`nav jump: Model 2 q3 -> ${want3}`);
  // --- prototype mode is independent ---
  p = await open('free');
  check(startLabel(p).startsWith('Begin Study'), 'free fresh: ' + startLabel(p));
  p.$('#btn-start-study').click();
  await answer(p, 1);
  // stalled save: three clicks -> one save, one step forward, button shows Saving…
  p.w.slowSubmit = 400;
  const before = p.w.submits;
  p.$('#btn-open-survey').click(); await fill(p);
  for (let k = 0; k < 3; k++) p.$('#btn-submit-survey').click();
  check(p.$('#btn-submit-survey').disabled && p.$('#btn-submit-survey').textContent === 'Saving…', 'submit not disabled while saving');
  await until(() => !p.$('#survey-modal-container') && qnum(p) === '3', 'stalled submit');
  await sleep(300);
  check(p.w.submits - before === 1 && qnum(p) === '3', `stalled submit: ${p.w.submits - before} saves, at q${qnum(p)}`);
  log.push('stalled submit: 3 clicks -> 1 save');
  p.w.slowSubmit = 0;
  // free-mode header dropdowns jump to any batch / question (nothing saved by jumping)
  const pick = (id, v) => { const el = p.$(id); el.value = String(v); el.dispatchEvent(new p.w.Event('change')); };
  const jump = await itemId('free', 2, 4);
  pick('#free-batch-select', 2);
  await until(() => p.w.studyApp.batchIndex === 2 && p.w.studyApp.currentItem?.id && p.$('#free-question-select')?.value === '0', 'batch jump');
  pick('#free-question-select', 4);
  await until(() => p.w.studyApp.currentItem?.id === jump, 'question jump');
  check(p.$('#free-batch-select').value === '2' && qnum(p) === '5', 'dropdowns not synced');
  log.push(`free jump: batch 3 q5 -> ${jump}`);
  p = await open('free');
  check(startLabel(p) === 'Continue where you left off (Model 1, question 3)', 'free reload: ' + startLabel(p));
  log.push('free reload after 2: ' + startLabel(p));
  p = await open('real');
  check(startLabel(p) === 'Continue where you left off (Model 2, question 1)', 'real after free: ' + startLabel(p));

  // finished: no button, just a message
  await fetch(`${base}/api/survey/end_of_study?mode=free`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ most_helpful_interface: 'jlens' }) });
  p = await open('free');
  check(p.$('#intro-finished') && !p.$('#btn-start-study'), 'finished: ' + startLabel(p));
  log.push('free after end_of_study: ' + startLabel(p));

  console.log(log.join('\n'));
  console.log(errors.length ? 'ERRORS:\n' + errors.join('\n') : 'no JS errors');
  process.exit(errors.length ? 1 : 0);
})().catch(e => { console.log('FAIL', e.message, errors); process.exit(1); });
