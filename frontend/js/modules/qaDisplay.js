/**
 * QA Display Module
 * Renders medical questions and model responses.
 */

class QADisplayModule {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.currentQuestion = null;
    }
    
    /**
     * Set the container element.
     */
    setContainer(containerSelector) {
        this.container = document.querySelector(containerSelector);
    }
    
    /**
     * Render an item: question + options (left), the cached response (#response-panel).
     * In the unblinded prototype (`item.variant` present) a label badge is shown.
     */
    render(item) {
        if (!this.container) return;
        this.currentQuestion = item;

        const letters = Object.keys(item.options).sort();
        // Prototype labels: item type in grey, the bias's target answer in red (spurious and
        // counterfactual items only), the clinically correct answer in green.
        const badge = item.variant ? `
            <div class="flex flex-wrap items-center gap-2 mb-3 text-xs">
                <span class="px-2 py-1 rounded font-semibold bg-gray-200 text-gray-700">${item.variant}</span>
                ${item.biased_answer ? `<span class="px-2 py-1 rounded bg-red-100 text-red-800">biased: ${this.escapeHtml(item.biased_answer)}</span>` : ''}
                <span class="px-2 py-1 rounded bg-green-100 text-green-800">clinically correct: ${this.escapeHtml(item.correct_answer)}</span>
                <span class="text-gray-400">${this.escapeHtml(item.id)}</span>
            </div>` : '';

        const resp = document.getElementById('response-panel');
        if (resp) resp.innerHTML = `
            <h2 class="text-lg font-semibold text-gray-800 mb-3">
                Model's Response <span class="text-sm font-normal text-gray-500">(answer: ${this.escapeHtml(item.model_answer)})</span>
            </h2>
            <div class="model-reasoning whitespace-pre-wrap">${this.escapeHtml(item.response)}</div>`;

        this.container.innerHTML = `
            <div class="bg-white rounded-lg shadow p-8">
                ${badge}
                <h2 class="text-lg font-semibold text-gray-800 mb-4">
                    Medical Question
                </h2>
                <p class="qa-question mb-4">${this.escapeHtml(item.question)}</p>
                <div class="qa-choices">
                    ${letters.map(k => `
                        <div class="qa-choice ${k === item.model_answer ? 'model-answer' : ''}">
                            ${k}. ${this.escapeHtml(item.options[k])}
                        </div>`).join('')}
                </div>
            </div>
        `;
    }

    getCurrentQuestion() {
        return this.currentQuestion;
    }

    /** The exact conversation the cached response came from, to seed the chat. */
    getSeedMessages() {
        if (!this.currentQuestion) return [];
        return [
            { role: 'user', content: this.currentQuestion.user_prompt },
            { role: 'assistant', content: this.currentQuestion.response },
        ];
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    /**
     * Show loading state.
     */
    showLoading() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="bg-white rounded-lg shadow p-6">
                <div class="skeleton h-6 w-1/3 mb-4"></div>
                <div class="skeleton h-4 w-full mb-2"></div>
                <div class="skeleton h-4 w-full mb-2"></div>
                <div class="skeleton h-4 w-2/3 mb-4"></div>
                <div class="space-y-2">
                    <div class="skeleton h-12 w-full"></div>
                    <div class="skeleton h-12 w-full"></div>
                    <div class="skeleton h-12 w-full"></div>
                    <div class="skeleton h-12 w-full"></div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-6">
                <div class="skeleton h-6 w-1/4 mb-4"></div>
                <div class="skeleton h-24 w-full"></div>
            </div>
        `;
    }
    
    /**
     * Clear the display.
     */
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.currentQuestion = null;
    }
}

// Create singleton instance
const qaDisplay = new QADisplayModule('#qa-panel');

// Make globally available
window.QADisplayModule = QADisplayModule;
window.qaDisplay = qaDisplay;
