/**
 * Tutorial mode (/?mode=tutorial): the real-mode screens on one practice item, with yellow
 * sticky notes and a Step N of 6 bar. Chat goes to the base model; nothing is submitted.
 * The only record saved is tutorial_complete, and only when the link carries a valid key.
 */

const TUT_NOTES = {
    question: 'The medical question and answer options.',
    response: "The model's answer and its step-by-step reasoning.",
    chat: 'Chat with the model. It remembers this question and its answer — ask follow-ups, ' +
          'or start a new conversation.',
    q1: 'Your own clinical judgement of the final answer.',
    q2: 'A model can get the right answer for the wrong reasons, or the reverse. Judge the reasoning.',
    q3: 'If the reasoning seems flawed, describe how. From the second question on, you can select ' +
        '"same as before" since each batch of questions shares a biased clinical reasoning, if there is one.',
    q4: 'Which sources you used: the response, the interpretability panel, the conversation, your own knowledge.',
    jlens: 'The model processes the question in different stages, and we present words (or partial words) ' +
           'from early stages (depth 1) to late ones (depth 15). Words that keep showing up across rows ' +
           'may hint at what\'s driving the model\'s decision. You may hover over or click a word to see where it ' +
           'occurs across depths.',
    sae: 'Instead of single words, each concept is written as a short plain-English description, ' +
         'e.g. "words about blood pressure". Look for concepts that do not represent good clinical reasoning.',
    span: 'Switch between what the model thought while reading the question vs. while writing its response.',
    usefulness: 'After all questions for one model: how helpful the interpretability panel, the model\'s ' +
                'reasoning and the conversation were for understanding its behavior.',
    clarity: 'How clear and easy to read the interpretability panel was, across all models.',
    interface: 'Which one helped you most across all models.',
};
const TUT_STEPS = 6;
const TUT_STEP_NAMES = ['Introduction', 'The basics', 'Question survey', 'Extra panel: words', 'Extra panel: concepts', 'Final questions'];

class TutorialMode {
    constructor() {
        this.step = 1;
        this.item = null;
        this.chat = null;       // conversation kept across steps
        this.completed = false;
    }

    async start(app) {
        this.app = app;
        try {
            this.item = await window.API.getTutorialItem();
        } catch (error) {
            console.error('Failed to load tutorial:', error);
            app.showError(`Failed to load tutorial: ${error.message}`);
            return;
        }
        window.surveyModule.surveyQuestions = this.item.survey;
        app.instructionCounts = [this.item.n_models, this.item.n_items];
        window.interpTools.afterDraw = c => this.notePanel(c);
        document.body.classList.add('tutorial-mode');
        document.body.insertAdjacentHTML('afterbegin', `
            <div id="tutorial-bar" class="fixed top-0 inset-x-0 z-[60] h-11 bg-gray-800 text-white flex items-center justify-between px-6 text-sm">
                <span id="tutorial-step-label" class="font-semibold w-44 shrink-0"></span>
                <div id="tutorial-progress" class="flex-1 flex gap-1.5 mx-6">
                    ${TUT_STEP_NAMES.map((n, i) => `<div class="tut-seg flex-1 rounded-full text-center text-xs py-1 truncate" data-seg="${i + 1}">${n}</div>`).join('')}
                </div>
                <div class="flex gap-2 shrink-0">
                    <button id="tutorial-back" class="px-3 py-1 rounded border border-gray-500 hover:bg-gray-700 disabled:opacity-40">Back</button>
                    <button id="tutorial-next" class="px-3 py-1 rounded bg-yellow-300 text-gray-900 font-semibold hover:bg-yellow-200">Next</button>
                </div>
            </div>`);
        document.getElementById('tutorial-back').addEventListener('click', () => this.go(this.step - 1));
        document.getElementById('tutorial-next').addEventListener('click', () => this.go(this.step + 1));
        this.go(1);
    }

    note(key, extra = '') {
        return `<div class="tut-note ${extra}" data-note="${key}">${escapeTut(TUT_NOTES[key])}</div>`;
    }

    go(step) {
        if (step < 1 || step > TUT_STEPS + 1) return;
        if (document.getElementById('chat-panel') && window.chatInterface.messages.length) {
            this.chat = { messages: [...window.chatInterface.messages],
                          seedLength: window.chatInterface.seedLength };
        }
        this.app.closeSurveyModal();
        this.app.closeInstructions();
        this.step = step;
        document.getElementById('tutorial-step-label').textContent =
            step <= TUT_STEPS ? `Tutorial · Step ${step} of ${TUT_STEPS}` : 'Tutorial · Done';
        document.querySelectorAll('#tutorial-progress .tut-seg').forEach(el => {
            const n = Number(el.dataset.seg);
            el.className = 'tut-seg flex-1 rounded-full text-center text-xs py-1 truncate ' +
                (n < step ? 'bg-yellow-300/60 text-gray-900' : n === step
                    ? 'bg-yellow-300 text-gray-900 font-semibold' : 'bg-gray-600 text-gray-300');
        });
        document.getElementById('tutorial-back').disabled = step === 1;
        document.getElementById('tutorial-next').classList.toggle('hidden', step > TUT_STEPS);
        window.scrollTo?.(0, 0);
        ({ 1: () => this.showIntro(), 2: () => this.showTask(null), 3: () => this.showSurvey(),
           4: () => this.showTask('jlens'), 5: () => this.showTask('sae'), 6: () => this.showVerdict(),
           7: () => this.showReady() })[step]();
    }

    /** Step 1: the real intro page as is (no notes). */
    showIntro() {
        const app = this.app;
        app.appContainer.innerHTML = document.getElementById('template-intro').innerHTML;
        app.fillInstructions(app.appContainer.querySelector('.intro-instructions'));
        document.getElementById('intro-participant-id').parentElement.remove();
        document.getElementById('btn-start-study').addEventListener('click', () => this.go(2));
    }

    /** The real task screen; tool = null (step 2, no tabs) | 'jlens' | 'sae'. */
    showTask(tool) {
        const app = this.app, item = this.item;
        app.appContainer.innerHTML = document.getElementById('template-task').innerHTML;
        document.getElementById('current-batch-num').textContent = 'Model 1';
        document.getElementById('total-batches').textContent = '1';
        document.getElementById('current-question-num').textContent = '1';
        document.getElementById('total-questions').textContent = '1';
        document.getElementById('btn-open-survey').addEventListener('click', () => this.go(3));

        window.qaDisplay.setContainer('#qa-panel');
        window.interpTools.setContainer('#interp-tool-panel');
        window.chatInterface.setContainer('#chat-panel');
        window.studyTimer.start();
        window.studyTimer.onTick((s, formatted) => {
            const el = document.getElementById('elapsed-time');
            if (el) el.textContent = formatted;
        });

        window.qaDisplay.render(item);
        window.interpTools.span = 'question';
        window.interpTools.render(tool ? { [tool]: item.readouts[tool] } : {});
        app.setupRightTabs(tool ? [tool] : []);
        window.chatInterface.init(0, item.id, this.chat ? [] : window.qaDisplay.getSeedMessages());
        if (this.chat) {
            Object.assign(window.chatInterface, this.chat);
            window.chatInterface.render();
        }

        if (!tool) {  // step 2: notes in the margin above each panel
            document.querySelector('main').insertAdjacentHTML('afterbegin', `
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-2">
                    <div class="lg:col-span-5">${this.note('question')}</div>
                    <div class="lg:col-span-7">${this.note('response')}</div>
                </div>`);
            const chat = document.getElementById('chat-panel');
            chat.classList.replace('mt-6', 'mt-2');
            chat.insertAdjacentHTML('beforebegin', `<div class="mt-6">${this.note('chat')}</div>`);
        } else {
            document.querySelector(`.right-tab[data-tab="${tool}"]`).click();  // open on Extra panel
        }
    }

    /** Called after every interpTools.draw(): pin the step's notes inside the panel. */
    notePanel(container) {
        if (this.step !== 4 && this.step !== 5) return;
        container.querySelector('p')?.insertAdjacentHTML('afterend',
            this.note(this.step === 4 ? 'jlens' : 'sae', 'mb-3'));
        container.querySelector('.interp-span')?.closest('.inline-flex')
            .insertAdjacentHTML('afterend', this.note('span', 'tut-inline'));
    }

    /** Pin a note to the right margin of each anchor question inside `container`. */
    sideNotes(container, anchors) {
        container.classList.add('tut-notes-right');
        Object.entries(anchors).forEach(([qid, key]) => {
            const el = container.querySelector(`[data-question-id="${qid}"]`) || container.querySelector(qid);
            el?.insertAdjacentHTML('beforeend', this.note(key, 'tut-side'));
        });
    }

    /** Step 3: the real per-question form over the task screen; nothing is submitted. */
    showSurvey() {
        this.showTask(null);
        document.querySelectorAll('main [data-note]').forEach(n => n.remove());
        const modal = document.createElement('div');
        modal.id = 'survey-modal-container';
        modal.innerHTML = document.getElementById('template-survey-modal').innerHTML;
        document.body.appendChild(modal);
        modal.firstElementChild.classList.add('pt-12');
        modal.querySelector('.max-w-2xl').classList.replace('max-w-2xl', 'max-w-5xl');

        // Show the conditional q3 items as they appear from question 2 on, after "No".
        const survey = window.surveyModule;
        survey.setQuestionIndex(1);
        survey.lastInvalidDescription = 'Your description from an earlier question appears here.';
        survey.renderPerQuestionSurvey('#survey-questions-container');
        const box = document.getElementById('survey-questions-container');
        box.querySelector('[data-question="q2_clinically_valid"][data-value="No"]')?.click();
        box.querySelector('[data-question="q3_same_as_before"][data-value="Different"]')?.click();
        this.sideNotes(box, { q1_answer_correct: 'q1', q2_clinically_valid: 'q2',
                              q3_same_as_before: 'q3', q4_inference_method: 'q4' });

        document.getElementById('btn-close-survey').addEventListener('click', () => this.go(2));
        document.getElementById('btn-back-to-task').addEventListener('click', () => this.go(2));
        document.getElementById('btn-submit-survey').addEventListener('click', () => this.go(4));
    }

    /** Step 6: the per-model ratings, then the end-of-study questions; not submitted. */
    showVerdict() {
        const app = this.app;
        app.appContainer.innerHTML = document.getElementById('template-batch-survey').innerHTML +
            document.getElementById('template-end-survey').innerHTML;
        app.appContainer.querySelectorAll('.max-w-2xl').forEach(c => c.classList.replace('max-w-2xl', 'max-w-5xl'));
        app.appContainer.firstElementChild.classList.replace('min-h-screen', 'pb-0');  // stack, no gap
        document.getElementById('batch-label').textContent = 'Model 1';
        document.getElementById('btn-next-batch').remove();
        document.getElementById('btn-finish-study').remove();

        window.surveyModule.renderBatchSurvey('#batch-survey-container');
        const box = document.getElementById('batch-survey-container');
        this.sideNotes(box, { batch_q1_panel_usefulness: 'usefulness' });
        const end = document.getElementById('end-survey-interface-options').closest('.space-y-8');
        this.sideNotes(end, { ':scope > div:nth-child(1)': 'interface', ':scope > div:nth-child(2)': 'clarity' });
        document.querySelectorAll('.end-survey-option').forEach(b => b.addEventListener('click', () => {
            document.querySelectorAll('.end-survey-option').forEach(o => o.classList.remove('bg-blue-100', 'border-blue-500'));
            b.classList.add('bg-blue-100', 'border-blue-500');
        }));
    }

    showReady() {
        this.app.appContainer.innerHTML = `
            <div class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
                <div class="max-w-lg bg-white rounded-lg shadow-lg p-8 text-center">
                    <h1 class="text-2xl font-bold text-gray-800 mb-4">You're ready</h1>
                    <p class="text-gray-600 mb-6">That's the whole interface. Open your study link when you're ready to begin.</p>
                    <button id="tutorial-restart" class="px-6 py-2 border rounded-lg hover:bg-gray-50 transition">Back to the start of the tutorial</button>
                </div>
            </div>`;
        document.getElementById('tutorial-restart').addEventListener('click', () => this.go(1));
        if (window.API.key && !this.completed) {
            this.completed = true;
            window.API.completeTutorial().catch(e => console.warn('tutorial_complete not saved:', e));
        }
    }
}

function escapeTut(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.tutorial = new TutorialMode();
