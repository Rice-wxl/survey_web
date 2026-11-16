/**
 * Main Application Controller
 * Coordinates all modules and manages study flow.
 */

class StudyApp {
    constructor() {
        this.participantId = null;
        this.mode = window.API.mode;
        this.trial = false;         // trial key (or STUDY_AUTH=off), from the server
        this.batches = [];          // from the server plan
        this.batchIndex = 0;
        this.currentQuestionIndex = 0;
        this.currentItem = null;
        this.appContainer = document.getElementById('app');
        this.instructionCounts = ['several', 'several'];  // [batches, questions per batch]
        document.addEventListener('click', e => {         // task-screen header, every mode
            if (e.target.closest('#btn-instructions')) this.openInstructions();
            else if (e.target.closest('.btn-close-instructions')) this.closeInstructions();
        });
        document.addEventListener('keydown', e => { if (e.key === 'Escape') this.closeInstructions(); });
    }

    async init() {
        if (this.mode === 'tutorial') return window.tutorial.start(this);
        try {
            await window.surveyModule.loadQuestions();
            const session = await window.API.startSession();
            this.participantId = session.participant_id;
            this.trial = !!session.trial;
            this.batches = session.batches;
            this.resume = session.resume;
            this.instructionCounts = [this.batches.length, this.batches[0]?.n_items ?? ''];
            this.showIntroduction();
        } catch (error) {
            console.error('Failed to initialize app:', error);
            this.showError(`Failed to load study: ${error.message}`);
        }
    }

    showIntroduction() {
        const template = document.getElementById('template-intro');
        this.appContainer.innerHTML = template.innerHTML;
        this.fillInstructions(this.appContainer.querySelector('.intro-instructions'));
        document.getElementById('intro-participant-id').textContent = this.participantId;
        if (this.mode === 'free') {
            document.getElementById('intro-prototype-banner').classList.remove('hidden');
        }
        const btn = document.getElementById('btn-start-study');
        const r = this.resume;
        if (r?.finished) {
            btn.outerHTML = '<p id="intro-finished" class="text-center text-green-700 font-semibold">You have already completed this study. Thank you!</p>';
            return;
        }
        if (r && (r.batch > 0 || r.item > 0)) {
            const where = r.batch >= this.batches.length ? 'final questions'
                : `${this.batches[r.batch].label}${r.at_batch_survey ? ': complete' : `, question ${r.item + 1}`}`;
            btn.firstChild.textContent = `Continue where you left off (${where}) `;
            btn.addEventListener('click', () => this.resumeAt(r));
            return;
        }
        btn.addEventListener('click', () => {
            this.batchIndex = 0;
            this.startBatch();
        });
    }

    /** Jump to the saved resume point (backend resume_point). */
    async resumeAt(r) {
        this.batchIndex = r.batch;
        if (this.batchIndex >= this.batches.length) return this.showEndOfStudySurvey();
        window.surveyModule.resetForNewBatch();
        window.surveyModule.lastInvalidDescription = r.last_invalid_description || null;
        this.currentQuestionIndex = r.item;
        await this.loadQuestion();
    }

    async startBatch() {
        if (this.batchIndex >= this.batches.length) {
            this.showEndOfStudySurvey();
            return;
        }
        window.surveyModule.resetForNewBatch();
        this.currentQuestionIndex = 0;
        await this.loadQuestion();
    }

    async loadQuestion() {
        const batch = this.batches[this.batchIndex];
        if (this.currentQuestionIndex >= batch.n_items) {
            this.showBatchSurvey();
            return;
        }

        const template = document.getElementById('template-task');
        this.appContainer.innerHTML = template.innerHTML;
        document.getElementById('current-batch-num').textContent =
            batch.organism ? `${batch.label} (${batch.organism})` : batch.label;
        document.getElementById('total-batches').textContent = this.batches.length;
        document.getElementById('current-question-num').textContent = this.currentQuestionIndex + 1;
        document.getElementById('total-questions').textContent = batch.n_items;
        this.syncCondition();
        if (this.trial) this.setupNav();

        window.qaDisplay.setContainer('#qa-panel');
        window.interpTools.setContainer('#interp-tool-panel');
        window.chatInterface.setContainer('#chat-panel');
        window.qaDisplay.showLoading();
        window.interpTools.showLoading();

        window.studyTimer.start();
        window.studyTimer.onTick((seconds, formatted) => {
            const timerEl = document.getElementById('elapsed-time');
            if (timerEl) timerEl.textContent = formatted;
        });

        document.getElementById('btn-open-survey').addEventListener('click', () => {
            this.openSurveyModal();
        });

        try {
            this.currentItem = await window.API.getItem(this.batchIndex, this.currentQuestionIndex);
            window.qaDisplay.render(this.currentItem);
            window.interpTools.render(this.currentItem.readouts);
            const ro = this.currentItem.readouts;
            // the lrp tab needs the max-contrast panel (the one drawLrp shows)
            this.setupRightTabs(['jlens', 'sae', 'lrp'].filter(t => t in ro && (t !== 'lrp' || ro.lrp.max)));
            window.chatInterface.init(this.batchIndex, this.currentItem.id,
                                      window.qaDisplay.getSeedMessages());
        } catch (error) {
            console.error('Failed to load question:', error);
            window.interpTools.showError(error.message);
        }
    }

    /** Trial keys in real mode pick each batch's condition themselves (the server honours
     *  ?condition= only for them); every request then carries the current batch's pick. */
    syncCondition() {
        window.API.condition = this.trial && this.mode === 'real'
            ? this.batches[this.batchIndex].condition : null;
    }

    /** Trial keys only: batch / question dropdowns in the header replace the counter, to jump
     *  anywhere, plus (real mode) the condition switch. Bias names show only in the
     *  prototype (the server sends `organism` only there). */
    setupNav() {
        const opts = (n, label, sel) => Array.from({ length: n }, (_, i) =>
            `<option value="${i}"${i === sel ? ' selected' : ''}>${label(i)}</option>`).join('');
        const cls = 'border border-gray-300 rounded-lg px-2 py-1 bg-white text-gray-800';
        const batch = this.batches[this.batchIndex];
        document.querySelector('header h1').parentElement.innerHTML = `
            <label class="flex items-center gap-2 font-semibold text-gray-800">Batch
                <select id="free-batch-select" class="${cls}">${opts(this.batches.length,
                    i => this.batches[i].label + (this.batches[i].organism ? ` (${this.batches[i].organism})` : ''), this.batchIndex)}</select></label>
            <label class="flex items-center gap-2 font-medium text-gray-600">Question
                <select id="free-question-select" class="${cls}">${opts(batch.n_items,
                    i => `${i + 1} of ${batch.n_items}`, this.currentQuestionIndex)}</select></label>
            ${this.mode === 'real' ? `
            <label class="flex items-center gap-2 font-medium text-gray-600">Panel
                <select id="trial-condition-select" class="${cls}">${[['blackbox', 'Blackbox'], ['jlens', 'J-lens'], ['sae', 'SAE'], ['lrp', 'Token attribution']]
                    .map(([c, label]) => `<option value="${c}"${c === batch.condition ? ' selected' : ''}>${label}</option>`).join('')}</select></label>` : ''}`;
        document.getElementById('trial-condition-select')?.addEventListener('change', e => {
            batch.condition = e.target.value;   // remembered per batch for this page load
            window.studyTimer?.logEvent('trial_condition', { condition: batch.condition });
            this.loadQuestion();
        });
        document.getElementById('free-batch-select').addEventListener('change', e => {
            this.batchIndex = Number(e.target.value);
            this.startBatch();
        });
        document.getElementById('free-question-select').addEventListener('change', e => {
            this.currentQuestionIndex = Number(e.target.value);
            this.loadQuestion();
        });
    }

    /**
     * [Model response | Extra panel] tabs. Real mode: one extra panel (none for black-box,
     * so no tabs). Prototype: one tab per tool, each identical to its real-mode panel.
     */
    setupRightTabs(tools) {
        const bar = document.getElementById('right-tabs');
        const name = { jlens: 'J-lens', sae: 'SAE', lrp: 'Token attribution' };
        const tabs = [['response', 'Model response'],
                      ...tools.map(t => [t, tools.length > 1 ? `Extra panel (${name[t]})` : 'Extra panel'])];
        bar.innerHTML = tabs.map(([id, label]) =>
            `<button data-tab="${id}" class="right-tab px-3 py-2 text-sm -mb-px border-b-2">${label}</button>`).join('');
        const show = tab => {
            document.getElementById('response-panel').classList.toggle('hidden', tab !== 'response');
            document.getElementById('interp-tool-panel').classList.toggle('hidden', tab === 'response');
            if (tab !== 'response') window.interpTools.show(tab);
            bar.querySelectorAll('.right-tab').forEach(b => {
                const on = b.dataset.tab === tab;
                b.classList.toggle('border-indigo-600', on);
                b.classList.toggle('text-indigo-700', on);
                b.classList.toggle('font-semibold', on);
                b.classList.toggle('border-transparent', !on);
                b.classList.toggle('text-gray-500', !on);
            });
        };
        bar.classList.toggle('hidden', tools.length === 0);
        bar.querySelectorAll('.right-tab').forEach(b => b.addEventListener('click', () => {
            window.studyTimer?.logEvent('right_tab', { tab: b.dataset.tab });
            show(b.dataset.tab);
        }));
        show('response');
    }

    /** Put the shared instructions (template-instructions) into `el`, with the batch counts. */
    fillInstructions(el) {
        el.innerHTML = document.getElementById('template-instructions').innerHTML;
        el.querySelector('#num-spurious-types').textContent = this.instructionCounts[0];
        el.querySelector('#num-questions').textContent = this.instructionCounts[1];
    }

    openInstructions() {
        if (document.getElementById('instructions-modal')) return;
        const modal = document.createElement('div');
        modal.id = 'instructions-modal';
        modal.innerHTML = document.getElementById('template-instructions-modal').innerHTML;
        this.fillInstructions(modal.querySelector('.intro-instructions'));
        modal.firstElementChild.addEventListener('click', e => {  // backdrop click closes
            if (e.target === e.currentTarget) this.closeInstructions();
        });
        document.body.appendChild(modal);
    }

    closeInstructions() {
        document.getElementById('instructions-modal')?.remove();
    }

    /**
     * Open the survey modal.
     */
    openSurveyModal() {
        // Log event
        window.studyTimer.logEvent('survey_opened');
        
        // Create modal
        const template = document.getElementById('template-survey-modal');
        const modalHtml = template.innerHTML;
        
        const modalContainer = document.createElement('div');
        modalContainer.id = 'survey-modal-container';
        modalContainer.innerHTML = modalHtml;
        document.body.appendChild(modalContainer);
        
        // Render survey questions with current question index
        window.surveyModule.noPanel = this.batches[this.batchIndex].condition === 'blackbox';
        window.surveyModule.setQuestionIndex(this.currentQuestionIndex);
        window.surveyModule.renderPerQuestionSurvey('#survey-questions-container');
        
        // Attach handlers
        document.getElementById('btn-close-survey').addEventListener('click', () => {
            this.closeSurveyModal();
        });
        
        document.getElementById('btn-back-to-task').addEventListener('click', () => {
            this.closeSurveyModal();
        });
        
        document.getElementById('btn-submit-survey').addEventListener('click', () => {
            this.submitSurvey();
        });
    }
    
    /**
     * Close the survey modal.
     */
    closeSurveyModal() {
        const modal = document.getElementById('survey-modal-container');
        if (modal) modal.remove();
    }
    
    /**
     * Submit survey and move to next question.
     */
    async submitSurvey() {
        // Validate
        if (!window.surveyModule.validate('per_question')) {
            return;
        }
        
        // Stop timer and get timing data
        const timingData = window.studyTimer.stop();
        
        // Get responses
        const responses = window.surveyModule.getResponses();

        // When "Same as before" is selected, include the referenced description
        if (responses['q3_same_as_before'] === 'Same as before' && window.surveyModule.lastInvalidDescription) {
            responses['q3_referenced_description'] = window.surveyModule.lastInvalidDescription;
        }

        // Submit to backend
        try {
            await this.whileSaving(document.getElementById('btn-submit-survey'), () => window.API.submitSurvey(
                this.batchIndex,
                this.currentItem.id,
                responses,
                timingData
            ));
            
            // Close modal
            this.closeSurveyModal();
            
            // Clear module states
            window.surveyModule.clearResponses();
            
            // Move to next question
            this.currentQuestionIndex++;
            await this.loadQuestion();
            
        } catch (error) {
            console.error('Failed to submit survey:', error);
            alert('Failed to submit response. Please try again.');
        }
    }
    
    /** Await `save` with `btn` disabled and reading "Saving…": a stalled relay once turned three
     *  clicks into three saves and a skipped question. Restores the button if `save` throws;
     *  on success the caller moves on to a new screen. */
    async whileSaving(btn, save) {
        const label = btn.innerHTML;
        btn.disabled = true;
        btn.textContent = 'Saving…';
        try {
            return await save();
        } catch (error) {
            btn.disabled = false;
            btn.innerHTML = label;
            throw error;
        }
    }

    /**
     * End of one organism: a "model complete" break (no questions since 2026-10-26);
     * Continue saves batch_complete, which resume_point uses.
     */
    showBatchSurvey() {
        const template = document.getElementById('template-batch-survey');
        this.appContainer.innerHTML = template.innerHTML;
        document.getElementById('batch-label').textContent = this.batches[this.batchIndex].label;
        this.syncCondition();
        window.surveyModule.noPanel = this.batches[this.batchIndex].condition === 'blackbox';
        window.surveyModule.renderBatchSurvey('#batch-survey-container');

        document.getElementById('btn-next-batch').addEventListener('click', async e => {
            if (!window.surveyModule.validate('batch')) return;
            try {
                await this.whileSaving(e.currentTarget, () =>
                    window.API.submitBatchSurvey(this.batchIndex, window.surveyModule.getResponses()));
            } catch (error) {
                alert('Failed to submit response. Please try again.');
                return;
            }
            window.surveyModule.clearResponses();
            this.batchIndex++;
            this.startBatch();
        });
    }

    /**
     * Show end-of-study survey.
     */
    showEndOfStudySurvey() {
        const template = document.getElementById('template-end-survey');
        this.appContainer.innerHTML = template.innerHTML;

        let selectedInterface = null;

        // Interface option selection
        document.querySelectorAll('.end-survey-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.end-survey-option').forEach(b => {
                    b.classList.remove('bg-blue-100', 'border-blue-500');
                });
                e.currentTarget.classList.add('bg-blue-100', 'border-blue-500');
                selectedInterface = e.currentTarget.dataset.value;
                document.getElementById('end-survey-interface-error').textContent = '';
            });
        });

        let clarity = null;
        document.querySelectorAll('.end-clarity-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.end-clarity-option').forEach(b => b.classList.remove('bg-blue-100', 'border-blue-500'));
                e.currentTarget.classList.add('bg-blue-100', 'border-blue-500');
                clarity = Number(e.currentTarget.dataset.value);
                document.getElementById('end-survey-clarity-error').textContent = '';
            });
        });

        // Finish button
        document.getElementById('btn-finish-study').addEventListener('click', async e => {
            if (!selectedInterface || !clarity) {
                if (!selectedInterface) document.getElementById('end-survey-interface-error').textContent = 'Please select an option.';
                if (!clarity) document.getElementById('end-survey-clarity-error').textContent = 'Please select an option.';
                return;
            }

            const comments = document.getElementById('end-survey-comments').value.trim();

            try {
                await this.whileSaving(e.currentTarget, () =>
                    window.API.submitEndOfStudySurvey(selectedInterface, comments, clarity));
            } catch (error) {
                console.error('Failed to submit end-of-study survey:', error);
            }

            this.showComplete();
        });
    }

    /**
     * Show study complete screen.
     */
    showComplete() {
        const template = document.getElementById('template-complete');
        this.appContainer.innerHTML = template.innerHTML;
        
        document.getElementById('final-participant-id').textContent = this.participantId;
    }
    
    /**
     * Show error message.
     */
    showError(message) {
        this.appContainer.innerHTML = `
            <div class="min-h-screen flex items-center justify-center p-6">
                <div class="bg-red-50 border border-red-200 rounded-lg p-8 max-w-md text-center">
                    <svg class="w-12 h-12 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                    </svg>
                    <h2 class="text-xl font-bold text-red-800 mb-2">Error</h2>
                    <p class="text-red-600">${message}</p>
                    <button onclick="location.reload()" 
                            class="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
                        Reload Page
                    </button>
                </div>
            </div>
        `;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new StudyApp();
    app.init();
    
    // Make app globally available for debugging
    window.studyApp = app;
});
