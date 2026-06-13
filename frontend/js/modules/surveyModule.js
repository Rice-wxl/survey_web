/**
 * Survey Module
 * Renders and handles survey questions.
 */

class SurveyModule {
    constructor() {
        this.surveyQuestions = null;
        this.responses = {};
        this.errors = {};
        this.currentQuestionIndex = 0;
        this.lastInvalidDescription = null;
    }

    setQuestionIndex(index) {
        this.currentQuestionIndex = index;
    }

    resetForNewBatch() {
        this.lastInvalidDescription = null;
    }
    
    /**
     * Load survey questions from API.
     */
    async loadQuestions() {
        try {
            const data = await window.API.getSurveyQuestions();
            this.surveyQuestions = data;
            return data;
        } catch (error) {
            console.error('Failed to load survey questions:', error);
            throw error;
        }
    }
    
    /**
     * Render per-question survey in a container.
     */
    renderPerQuestionSurvey(containerSelector) {
        const container = document.querySelector(containerSelector);
        if (!container || !this.surveyQuestions) return;
        
        this.responses = {};
        this.errors = {};
        
        const questions = this.surveyQuestions.per_question || [];
        
        container.innerHTML = questions.map(q => this.renderQuestion(q)).join('');
        this.attachEventListeners(container);
        this.updateConditionalVisibility();
    }
    
    /**
     * Render batch survey in a container.
     */
    renderBatchSurvey(containerSelector) {
        const container = document.querySelector(containerSelector);
        if (!container || !this.surveyQuestions) return;
        
        this.responses = {};
        this.errors = {};
        
        const questions = this.surveyQuestions.batch || [];
        
        container.innerHTML = questions.map(q => this.renderQuestion(q)).join('');
        this.attachEventListeners(container);
    }
    
    /**
     * Render a single question.
     */
    renderQuestion(question) {
        const { id, text, question_type, options, help_text, likert_min, likert_max, likert_labels, condition, min_question_index } = question;

        // Hide if min_question_index exceeds current question index
        if (min_question_index !== null && min_question_index !== undefined &&
            this.currentQuestionIndex < min_question_index) {
            return `<div class="survey-question hidden" data-question-id="${id}" data-gated-by-index="true"></div>`;
        }

        let inputHtml = '';

        switch (question_type) {
            case 'single_choice':
                inputHtml = this.renderSingleChoice(id, options);
                break;
            case 'multiple_choice':
                inputHtml = this.renderMultipleChoice(id, options);
                break;
            case 'likert':
                inputHtml = this.renderLikert(id, likert_min, likert_max, likert_labels);
                break;
            case 'free_text':
                inputHtml = this.renderFreeText(id, question.min_length, question.max_length);
                break;
            default:
                inputHtml = `<p class="text-red-500">Unknown question type: ${question_type}</p>`;
        }

        const helpTextHtml = help_text ? `<p class="survey-help-text">${this.escapeHtml(help_text)}</p>` : '';

        // For q3_same_as_before, show the previous invalid description as reference
        let previousResponseHtml = '';
        if (id === 'q3_same_as_before' && this.lastInvalidDescription) {
            previousResponseHtml = `
                <div class="bg-gray-50 border-l-4 border-gray-300 p-3 my-2 rounded">
                    <p class="text-xs font-medium text-gray-500 mb-1">Your previous assessment:</p>
                    <p class="text-sm text-gray-700 italic">${this.escapeHtml(this.lastInvalidDescription)}</p>
                </div>
            `;
        }

        // Conditional display attributes
        let conditionalAttr = '';
        let hiddenClass = '';
        if (condition) {
            conditionalAttr = `data-condition-depends="${condition.depends_on}"`;
            if (condition.show_when) {
                conditionalAttr += ` data-condition-values='${JSON.stringify(condition.show_when)}'`;
            }
            if (condition.show_when_includes) {
                conditionalAttr += ` data-condition-includes='${JSON.stringify(condition.show_when_includes)}'`;
            }
            hiddenClass = 'hidden';
        }

        return `
            <div class="survey-question ${hiddenClass}" data-question-id="${id}" ${conditionalAttr}>
                <p class="survey-question-text">${this.escapeHtml(text)}</p>
                ${previousResponseHtml}
                ${helpTextHtml}
                ${inputHtml}
                <div class="survey-error" data-error-for="${id}"></div>
            </div>
        `;
    }
    
    /**
     * Render single choice options.
     */
    renderSingleChoice(id, options) {
        const optionsHtml = options.map(opt => `
            <button type="button" 
                    class="survey-option" 
                    data-question="${id}" 
                    data-value="${this.escapeHtml(opt)}">
                ${this.escapeHtml(opt)}
            </button>
        `).join('');
        
        return `<div class="survey-options">${optionsHtml}</div>`;
    }
    
    /**
     * Render multiple choice options.
     */
    renderMultipleChoice(id, options) {
        const optionsHtml = options.map(opt => `
            <button type="button" 
                    class="survey-option" 
                    data-question="${id}" 
                    data-value="${this.escapeHtml(opt)}"
                    data-multi="true">
                ${this.escapeHtml(opt)}
            </button>
        `).join('');
        
        return `
            <p class="text-sm text-gray-500 mb-2">Select all that apply:</p>
            <div class="survey-options">${optionsHtml}</div>
        `;
    }
    
    /**
     * Render Likert scale.
     */
    renderLikert(id, min, max, labels) {
        const optionsHtml = [];
        for (let i = min; i <= max; i++) {
            optionsHtml.push(`
                <button type="button" 
                        class="likert-option" 
                        data-question="${id}" 
                        data-value="${i}">
                    ${i}
                </button>
            `);
        }
        
        const leftLabel = labels && labels[min] ? labels[min] : 'Strongly Disagree';
        const rightLabel = labels && labels[max] ? labels[max] : 'Strongly Agree';
        
        return `
            <div class="likert-scale">
                <span class="likert-label left">${this.escapeHtml(leftLabel)}</span>
                <div class="likert-options">${optionsHtml.join('')}</div>
                <span class="likert-label right">${this.escapeHtml(rightLabel)}</span>
            </div>
        `;
    }
    
    /**
     * Render free text input.
     */
    renderFreeText(id, minLength, maxLength) {
        const minAttr = minLength ? `data-min-length="${minLength}"` : '';
        const maxAttr = maxLength ? `maxlength="${maxLength}"` : '';
        
        return `
            <textarea class="survey-textarea" 
                      data-question="${id}"
                      ${minAttr}
                      ${maxAttr}
                      placeholder="Enter your response..."></textarea>
            ${maxLength ? `<p class="text-xs text-gray-400 mt-1">Maximum ${maxLength} characters</p>` : ''}
        `;
    }
    
    /**
     * Attach event listeners.
     */
    attachEventListeners(container) {
        // Single choice and Likert
        container.querySelectorAll('.survey-option:not([data-multi]), .likert-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const questionId = e.target.dataset.question;
                const value = e.target.dataset.value;
                
                // Deselect siblings
                container.querySelectorAll(`[data-question="${questionId}"]`).forEach(el => {
                    el.classList.remove('selected');
                });
                
                // Select this one
                e.target.classList.add('selected');
                this.responses[questionId] = value;
                
                // Clear error
                this.clearError(questionId);
                
                // Update conditional visibility
                this.updateConditionalVisibility();
            });
        });
        
        // Multiple choice
        container.querySelectorAll('.survey-option[data-multi]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const questionId = e.target.dataset.question;
                const value = e.target.dataset.value;
                
                // Toggle selection
                e.target.classList.toggle('selected');
                
                // Update responses array
                if (!this.responses[questionId]) {
                    this.responses[questionId] = [];
                }
                
                if (e.target.classList.contains('selected')) {
                    this.responses[questionId].push(value);
                } else {
                    this.responses[questionId] = this.responses[questionId].filter(v => v !== value);
                }

                this.clearError(questionId);
                this.updateConditionalVisibility();
            });
        });
        
        // Free text
        container.querySelectorAll('.survey-textarea').forEach(textarea => {
            textarea.addEventListener('input', (e) => {
                const questionId = e.target.dataset.question;
                this.responses[questionId] = e.target.value;
                this.clearError(questionId);
            });
        });
    }
    
    /**
     * Update visibility of conditional questions.
     */
    updateConditionalVisibility() {
        document.querySelectorAll('[data-condition-depends]').forEach(el => {
            // Skip index-gated questions that were already hidden at render time
            if (el.dataset.gatedByIndex === 'true') return;

            const dependsOn = el.dataset.conditionDepends;
            const showWhen = JSON.parse(el.dataset.conditionValues || '[]');
            const showWhenIncludes = JSON.parse(el.dataset.conditionIncludes || '[]');
            const questionId = el.dataset.questionId;
            const parentValue = this.responses[dependsOn];

            let visible = false;

            if (showWhenIncludes.length > 0) {
                // For multiple_choice parents: check if array contains any value
                if (Array.isArray(parentValue)) {
                    visible = showWhenIncludes.some(v => parentValue.includes(v));
                }
            } else if (showWhen.length > 0) {
                visible = showWhen.includes(parentValue);
            }

            // q3_same_as_before: only show if there's a previous invalid description to compare
            if (questionId === 'q3_same_as_before' && visible) {
                if (!this.lastInvalidDescription) {
                    visible = false;
                }
            }

            // q3_invalid_description: gate behind "same as before" when it's visible
            if (questionId === 'q3_invalid_description' && visible) {
                if (this.lastInvalidDescription && this.currentQuestionIndex > 0) {
                    // "Same as before" is available — only show description if "Different"
                    const sameAsBefore = this.responses['q3_same_as_before'];
                    if (sameAsBefore !== 'Different') {
                        visible = false;
                    }
                }
                // Otherwise show directly (first question, or no prior description)
            }

            if (visible) {
                el.classList.remove('hidden');
            } else {
                el.classList.add('hidden');
                delete this.responses[questionId];
            }
        });
    }
    
    /**
     * Validate responses.
     */
    validate(surveyType = 'per_question') {
        const questions = surveyType === 'per_question' ? 
            this.surveyQuestions.per_question : 
            this.surveyQuestions.batch;
        
        this.errors = {};
        let isValid = true;
        
        questions.forEach(q => {
            const questionEl = document.querySelector(`[data-question-id="${q.id}"]`);
            
            // Skip hidden conditional questions
            if (questionEl && questionEl.classList.contains('hidden')) {
                return;
            }
            
            const response = this.responses[q.id];
            
            // Check required
            if (q.required) {
                if (response === undefined || response === '' || 
                    (Array.isArray(response) && response.length === 0)) {
                    this.errors[q.id] = 'This question is required';
                    isValid = false;
                }
            }
            
            // Check min length for free text
            if (q.question_type === 'free_text' && q.min_length && response) {
                if (response.length < q.min_length) {
                    this.errors[q.id] = `Please enter at least ${q.min_length} characters`;
                    isValid = false;
                }
            }
        });
        
        // Show errors
        Object.entries(this.errors).forEach(([questionId, message]) => {
            this.showError(questionId, message);
        });
        
        return isValid;
    }
    
    /**
     * Show error for a question.
     */
    showError(questionId, message) {
        const errorEl = document.querySelector(`[data-error-for="${questionId}"]`);
        if (errorEl) {
            errorEl.textContent = message;
        }
    }
    
    /**
     * Clear error for a question.
     */
    clearError(questionId) {
        const errorEl = document.querySelector(`[data-error-for="${questionId}"]`);
        if (errorEl) {
            errorEl.textContent = '';
        }
        delete this.errors[questionId];
    }
    
    /**
     * Get current responses.
     */
    getResponses() {
        return { ...this.responses };
    }
    
    /**
     * Clear all responses.
     */
    clearResponses() {
        // Preserve the last invalid description for "same as before" reference
        if (this.responses['q3_invalid_description']) {
            this.lastInvalidDescription = this.responses['q3_invalid_description'];
        }
        this.responses = {};
        this.errors = {};
    }
    
    /**
     * Escape HTML.
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Create singleton instance
const surveyModule = new SurveyModule();

// Make globally available
window.SurveyModule = SurveyModule;
window.surveyModule = surveyModule;
