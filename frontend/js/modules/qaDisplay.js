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
     * Render a question and model response.
     */
    render(questionData) {
        if (!this.container) {
            console.error('QA Display container not found');
            return;
        }
        
        this.currentQuestion = questionData;
        
        const html = `
            <!-- Medical Question Card -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    Medical Question
                </h2>
                
                <p class="qa-question mb-4">${this.escapeHtml(questionData.question)}</p>
                
                <div class="qa-choices">
                    ${questionData.choices.map(choice => `
                        <div class="qa-choice ${choice.startsWith(questionData.model_answer) ? 'model-answer' : ''}">
                            ${this.escapeHtml(choice)}
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <!-- Model Reasoning Card -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                    <svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                    </svg>
                    Model's Reasoning
                </h2>
                
                <div class="model-reasoning">
                    ${this.escapeHtml(questionData.model_reasoning)}
                </div>
            </div>
        `;
        
        this.container.innerHTML = html;
    }
    
    /**
     * Get the current question data.
     */
    getCurrentQuestion() {
        return this.currentQuestion;
    }
    
    /**
     * Get formatted input text for interpretability tools.
     */
    getInputText() {
        if (!this.currentQuestion) return '';
        
        const parts = [
            this.currentQuestion.question,
            ...this.currentQuestion.choices
        ];
        
        return parts.join('\n');
    }
    
    /**
     * Get model output text.
     */
    getOutputText() {
        if (!this.currentQuestion) return '';
        return this.currentQuestion.model_reasoning;
    }
    
    /**
     * Get context for chat interface.
     */
    getChatContext() {
        if (!this.currentQuestion) return {};
        
        return {
            question_id: this.currentQuestion.id,
            question: this.currentQuestion.question,
            choices: this.currentQuestion.choices.join('\n'),
            model_answer: this.currentQuestion.model_answer,
            model_reasoning: this.currentQuestion.model_reasoning
        };
    }
    
    /**
     * Escape HTML to prevent XSS.
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
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
