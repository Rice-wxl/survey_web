/**
 * Main Application Controller
 * Coordinates all modules and manages study flow.
 */

class StudyApp {
    constructor() {
        // State
        this.participantId = null;
        this.currentSpuriousType = null;
        this.currentSpuriousTypeIndex = 0;
        this.spuriousTypes = [];
        this.currentQuestionIndex = 0;
        this.questions = [];
        this.currentTool = null;
        this.availableTools = [];

        // Randomized assignment: maps batch index -> tool name
        this.batchToolAssignment = [];

        // Configuration
        this.externalModelUrl = null; // Set if using separate model window

        // DOM
        this.appContainer = document.getElementById('app');
    }

    /**
     * Shuffle an array using Fisher-Yates algorithm.
     */
    shuffleArray(array) {
        const shuffled = [...array];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        return shuffled;
    }

    /**
     * Create randomized tool assignments for all batches.
     * Each batch gets a different tool (if enough tools available).
     */
    createBatchToolAssignment() {
        const numBatches = this.spuriousTypes.length;
        const toolNames = this.availableTools.map(t => t.name);

        // Shuffle tools
        let shuffledTools = this.shuffleArray(toolNames);

        // If more batches than tools, repeat the shuffled tools
        while (shuffledTools.length < numBatches) {
            shuffledTools = shuffledTools.concat(this.shuffleArray(toolNames));
        }

        // Assign one tool per batch
        this.batchToolAssignment = shuffledTools.slice(0, numBatches);

        console.log('Batch-Tool Assignment:', this.batchToolAssignment);
    }
    
    /**
     * Initialize the application.
     */
    async init() {
        try {
            // Load survey questions
            await window.surveyModule.loadQuestions();

            // Load available tools
            const toolsData = await window.API.getAvailableTools();
            this.availableTools = toolsData.tools || [];

            // Load spurious types and shuffle them for randomization
            const spuriousData = await window.API.getSpuriousTypes();
            this.spuriousTypes = this.shuffleArray(spuriousData.spurious_types || []);

            // Create randomized tool assignment for each batch
            this.createBatchToolAssignment();

            // Show introduction screen
            this.showIntroduction();

        } catch (error) {
            console.error('Failed to initialize app:', error);
            this.showError('Failed to load study. Please refresh the page.');
        }
    }
    
    /**
     * Show introduction screen.
     */
    showIntroduction() {
        const template = document.getElementById('template-intro');
        this.appContainer.innerHTML = template.innerHTML;
        
        // Update info
        document.getElementById('num-spurious-types').textContent = this.spuriousTypes.length;
        if (this.spuriousTypes.length > 0) {
            document.getElementById('num-questions').textContent = this.spuriousTypes[0].question_count;
        }
        
        // Attach start button handler
        document.getElementById('btn-start-study').addEventListener('click', () => {
            this.startStudy();
        });
    }
    
    /**
     * Start the study.
     */
    async startStudy() {
        try {
            // Get participant ID
            const inputId = document.getElementById('participant-id-input')?.value?.trim();
            
            // Start session
            const session = await window.API.startSession(inputId || null);
            this.participantId = session.participant_id;
            
            // Start with first spurious type
            this.currentSpuriousTypeIndex = 0;
            await this.startSpuriousBatch();
            
        } catch (error) {
            console.error('Failed to start study:', error);
            this.showError('Failed to start study. Please try again.');
        }
    }
    
    /**
     * Start a batch of questions for a spurious type.
     */
    async startSpuriousBatch() {
        if (this.currentSpuriousTypeIndex >= this.spuriousTypes.length) {
            this.showEndOfStudySurvey();
            return;
        }

        const spuriousType = this.spuriousTypes[this.currentSpuriousTypeIndex];
        this.currentSpuriousType = spuriousType.type;

        // Reset survey batch state so previous batch descriptions don't leak
        window.surveyModule.resetForNewBatch();

        // Load questions for this type
        const questionsData = await window.API.getQuestions(this.currentSpuriousType);
        this.questions = questionsData.question_ids || [];
        this.currentQuestionIndex = 0;

        // Get the randomly assigned tool for this batch
        this.currentTool = this.batchToolAssignment[this.currentSpuriousTypeIndex] || 'mock_tool';
        this.currentTool = 'mock_tool';

        console.log(`Batch ${this.currentSpuriousTypeIndex + 1}: Spurious type = ${this.currentSpuriousType}, Tool = ${this.currentTool}`);

        await window.API.assignTool(this.participantId, this.currentTool);

        // Load first question
        await this.loadQuestion();
    }
    
    /**
     * Load and display a question.
     */
    async loadQuestion() {
        if (this.currentQuestionIndex >= this.questions.length) {
            this.showBatchSurvey();
            return;
        }
        
        const questionId = this.questions[this.currentQuestionIndex];
        
        // Show task template
        const template = document.getElementById('template-task');
        this.appContainer.innerHTML = template.innerHTML;
        
        // Update header info
        document.getElementById('current-batch-num').textContent = this.currentSpuriousTypeIndex + 1;
        document.getElementById('total-batches').textContent = this.spuriousTypes.length;
        document.getElementById('current-question-num').textContent = this.currentQuestionIndex + 1;
        document.getElementById('total-questions').textContent = this.questions.length;
        
        // Set containers for modules
        window.qaDisplay.setContainer('#qa-panel');
        window.interpTools.setContainer('#interp-tool-panel');
        window.chatInterface.setContainer('#chat-panel');
        
        // Show loading states
        window.qaDisplay.showLoading();
        window.interpTools.showLoading();
        
        // Start timer
        window.studyTimer.start();
        window.studyTimer.onTick((seconds, formatted) => {
            const timerEl = document.getElementById('elapsed-time');
            if (timerEl) timerEl.textContent = formatted;
        });
        
        try {
            // Load question data
            const questionData = await window.API.getQuestion(questionId);
            
            // Render QA display
            window.qaDisplay.render(questionData);
            
            // Initialize chat interface
            window.chatInterface.init(
                this.participantId,
                window.qaDisplay.getChatContext(),
                this.externalModelUrl
            );
            
            // Compute and render interpretability
            const inputText = window.qaDisplay.getInputText();
            const outputText = window.qaDisplay.getOutputText();
            
            const interpResult = await window.API.computeInterpretation(
                this.currentTool,
                questionId,
                inputText,
                outputText
            );
            
            window.interpTools.render(
                interpResult.tool_name,
                interpResult.tool_display_name,
                interpResult.result
            );
            
        } catch (error) {
            console.error('Failed to load question:', error);
            window.interpTools.showError(error.message);
        }
        
        // Attach header button handlers
        document.getElementById('btn-open-survey').addEventListener('click', () => {
            this.openSurveyModal();
        });
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
            const questionId = this.questions[this.currentQuestionIndex];
            await window.API.submitSurvey(
                this.participantId,
                questionId,
                responses,
                timingData
            );
            
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
    
    /**
     * Show batch completion screen.
     */
    showBatchSurvey() {
        const template = document.getElementById('template-batch-survey');
        this.appContainer.innerHTML = template.innerHTML;

        document.getElementById('btn-next-batch').addEventListener('click', () => {
            this.currentSpuriousTypeIndex++;
            this.startSpuriousBatch();
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

        // Finish button
        document.getElementById('btn-finish-study').addEventListener('click', async () => {
            if (!selectedInterface) {
                document.getElementById('end-survey-interface-error').textContent = 'Please select an option.';
                return;
            }

            const comments = document.getElementById('end-survey-comments').value.trim();

            try {
                await window.API.submitEndOfStudySurvey(
                    this.participantId,
                    selectedInterface,
                    comments
                );
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
