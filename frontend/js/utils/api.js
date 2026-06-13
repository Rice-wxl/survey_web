/**
 * API utility module for backend communication.
 */

const API = {
    baseUrl: window.location.origin,
    
    /**
     * Make a fetch request with default options.
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}/api${endpoint}`;
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };
        
        if (mergedOptions.body && typeof mergedOptions.body === 'object') {
            mergedOptions.body = JSON.stringify(mergedOptions.body);
        }
        
        try {
            const response = await fetch(url, mergedOptions);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    },
    
    // ============== Session Endpoints ==============
    
    async startSession(participantId = null) {
        return this.request('/session/start', {
            method: 'POST',
            body: { participant_id: participantId }
        });
    },
    
    async assignTool(participantId, toolName) {
        return this.request(`/session/${participantId}/assign_tool`, {
            method: 'POST',
            body: { tool_name: toolName }
        });
    },
    
    // ============== QA Endpoints ==============
    
    async getSpuriousTypes() {
        return this.request('/qa/spurious_types');
    },
    
    async getQuestions(spuriousType) {
        return this.request(`/qa/questions/${spuriousType}`);
    },
    
    async getQuestion(questionId) {
        return this.request(`/qa/question/${questionId}`);
    },
    
    // ============== Model Endpoints ==============
    
    async chatWithModel(message, context, participantId) {
        return this.request('/model/chat', {
            method: 'POST',
            body: {
                message,
                context,
                participant_id: participantId
            }
        });
    },
    
    // ============== Interpretability Endpoints ==============
    
    async computeInterpretation(toolName, questionId, modelInput, modelOutput) {
        return this.request('/interp/compute', {
            method: 'POST',
            body: {
                tool_name: toolName,
                question_id: questionId,
                model_input: modelInput,
                model_output: modelOutput
            }
        });
    },
    
    async getAvailableTools() {
        return this.request('/interp/tools');
    },
    
    // ============== Survey Endpoints ==============
    
    async getSurveyQuestions() {
        return this.request('/survey/questions');
    },
    
    async submitSurvey(participantId, questionId, responses, timingData) {
        return this.request('/survey/submit', {
            method: 'POST',
            body: {
                participant_id: participantId,
                question_id: questionId,
                responses,
                timing_data: timingData
            }
        });
    },
    
    async submitBatchSurvey(participantId, spuriousType, toolName, usefulnessRating, comments) {
        return this.request('/survey/batch_complete', {
            method: 'POST',
            body: {
                participant_id: participantId,
                spurious_type: spuriousType,
                tool_name: toolName,
                usefulness_rating: usefulnessRating,
                comments
            }
        });
    },
    
    async submitEndOfStudySurvey(participantId, mostHelpfulInterface, comments) {
        return this.request('/survey/end_of_study', {
            method: 'POST',
            body: {
                participant_id: participantId,
                most_helpful_interface: mostHelpfulInterface,
                comments
            }
        });
    },

    // ============== Export ==============
    
    async exportSession(participantId) {
        return this.request(`/export/${participantId}`);
    }
};

// Make API globally available
window.API = API;
