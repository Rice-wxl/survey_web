/**
 * API utility module for backend communication.
 *
 * The study link carries the access key and mode:  /?k=<key>&mode=real|free|tutorial
 * Both are sent on every request; the server derives the participant from the key.
 */

const _params = new URLSearchParams(window.location.search);

const API = {
    baseUrl: window.location.origin,
    key: _params.get('k') || '',
    mode: ['free', 'tutorial'].includes(_params.get('mode')) ? _params.get('mode') : 'real',
    condition: null,   // trial keys, real mode: the current batch's picked condition (app.js)

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}/api${endpoint}?mode=${this.mode}` +
                    (this.condition ? `&condition=${this.condition}` : '');
        const opts = {
            ...options,
            headers: { 'Content-Type': 'application/json', 'X-Study-Key': this.key },
        };
        if (opts.body && typeof opts.body === 'object') {
            opts.body = JSON.stringify(opts.body);
        }
        const response = await fetch(url, opts);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        return response.json();
    },

    startSession() {
        return this.request('/session/start', { method: 'POST' });
    },

    getItem(batch, index) {
        return this.request(`/batch/${batch}/item/${index}`);
    },

    /** meta: {conversation_id, conversation_index, kind, cf?} (see chatInterface). */
    chatWithModel(batch, itemId, messages, meta = {}) {
        if (this.mode === 'tutorial') {  // base model, nothing saved
            return this.request('/tutorial/chat', { method: 'POST', body: { messages, kind: meta.kind, cf: meta.cf } });
        }
        return this.request('/model/chat', {
            method: 'POST',
            body: { batch, item_id: itemId, messages, ...meta },
        });
    },

    getTutorialItem() {
        return this.request('/tutorial/item');
    },

    completeTutorial() {
        return this.request('/tutorial/complete', { method: 'POST' });
    },

    getSurveyQuestions() {
        return this.request('/survey/questions');
    },

    submitSurvey(batch, questionId, responses, timingData) {
        return this.request('/survey/submit', {
            method: 'POST',
            body: { batch, question_id: questionId, responses, timing_data: timingData },
        });
    },

    submitBatchSurvey(batch, responses) {
        return this.request('/survey/batch_complete', {
            method: 'POST',
            body: { batch, responses },
        });
    },

    submitEndOfStudySurvey(mostHelpfulInterface, comments, panelClarity) {
        return this.request('/survey/end_of_study', {
            method: 'POST',
            body: { most_helpful_interface: mostHelpfulInterface, comments, panel_clarity: panelClarity },
        });
    },
};

window.API = API;
