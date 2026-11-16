/**
 * Unit tests for the Survey Module (surveyModule.js).
 *
 * Tests cover:
 * - Survey question rendering (all types)
 * - Response collection
 * - Validation
 * - Conditional question visibility
 * - Error display
 */

// Load dependencies
const fs = require('fs');
const path = require('path');

// Mock API
window.API = {
    getSurveyQuestions: jest.fn()
};

// Load the survey module
const moduleCode = fs.readFileSync(
    path.join(__dirname, '../../js/modules/surveyModule.js'),
    'utf8'
);
eval(moduleCode);

describe('SurveyModule', () => {
    let module;
    let container;

    // Sample survey questions matching backend structure
    const sampleSurveyQuestions = {
        per_question: [
            {
                id: 'q1',
                text: 'Is this clinically sound?',
                question_type: 'single_choice',
                options: ['Yes', 'No', 'Unsure'],
                required: true
            },
            {
                id: 'q2',
                text: 'Please explain:',
                question_type: 'free_text',
                required: true,
                min_length: 0,
                max_length: 500,
                condition: {
                    depends_on: 'q1',
                    show_when: ['No']
                }
            },
            {
                id: 'q3',
                text: 'Rate your confidence:',
                question_type: 'likert',
                required: true,
                likert_min: 1,
                likert_max: 5,
                likert_labels: { 1: 'Low', 5: 'High' }
            },
            {
                id: 'q4',
                text: 'Select all methods used:',
                question_type: 'multiple_choice',
                options: ['Method A', 'Method B', 'Method C'],
                required: true
            }
        ],
        batch: [
            {
                id: 'batch_q1',
                text: 'Tool usefulness:',
                question_type: 'likert',
                required: true,
                likert_min: 1,
                likert_max: 5,
                likert_labels: { 1: 'Not useful', 5: 'Very useful' }
            }
        ]
    };

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'survey-container';
        document.body.appendChild(container);

        module = new SurveyModule();
        module.surveyQuestions = sampleSurveyQuestions;

        window.API.getSurveyQuestions.mockClear();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    describe('Initialization', () => {
        /**
         * Tests that module initializes with empty responses.
         */
        test('should initialize with empty responses', () => {
            const newModule = new SurveyModule();
            expect(newModule.responses).toEqual({});
        });

        /**
         * Tests that module initializes with empty errors.
         */
        test('should initialize with empty errors', () => {
            const newModule = new SurveyModule();
            expect(newModule.errors).toEqual({});
        });
    });

    describe('loadQuestions method', () => {
        /**
         * Tests that loadQuestions calls API.
         */
        test('should call API.getSurveyQuestions', async () => {
            window.API.getSurveyQuestions.mockResolvedValue(sampleSurveyQuestions);

            await module.loadQuestions();

            expect(window.API.getSurveyQuestions).toHaveBeenCalled();
        });

        /**
         * Tests that loadQuestions stores questions.
         */
        test('should store survey questions', async () => {
            window.API.getSurveyQuestions.mockResolvedValue(sampleSurveyQuestions);

            await module.loadQuestions();

            expect(module.surveyQuestions).toBe(sampleSurveyQuestions);
        });

        /**
         * Tests that loadQuestions propagates errors.
         */
        test('should throw on API error', async () => {
            window.API.getSurveyQuestions.mockRejectedValue(new Error('API Error'));

            await expect(module.loadQuestions()).rejects.toThrow('API Error');
        });
    });

    describe('renderPerQuestionSurvey method', () => {
        /**
         * Tests that per-question survey is rendered.
         */
        test('should render all per-question questions', () => {
            module.renderPerQuestionSurvey('#survey-container');

            expect(container.textContent).toContain('Is this clinically sound?');
            expect(container.textContent).toContain('Rate your confidence:');
        });

        /**
         * Tests that conditional questions are hidden initially.
         */
        test('should hide conditional questions initially', () => {
            module.renderPerQuestionSurvey('#survey-container');

            const conditionalQ = container.querySelector('[data-question-id="q2"]');
            expect(conditionalQ.classList.contains('hidden')).toBe(true);
        });

        /**
         * Tests that responses are cleared on render.
         */
        test('should clear responses on render', () => {
            module.responses = { old: 'data' };
            module.renderPerQuestionSurvey('#survey-container');

            expect(module.responses).toEqual({});
        });
    });

    describe('renderBatchSurvey method', () => {
        /**
         * Tests that batch survey is rendered.
         */
        test('should render batch questions', () => {
            module.renderBatchSurvey('#survey-container');

            expect(container.textContent).toContain('Tool usefulness:');
        });
    });

    describe('renderQuestion method', () => {
        /**
         * Tests single choice rendering.
         */
        test('should render single choice options', () => {
            const html = module.renderQuestion(sampleSurveyQuestions.per_question[0]);

            expect(html).toContain('Yes');
            expect(html).toContain('No');
            expect(html).toContain('Unsure');
            expect(html).toContain('survey-option');
        });

        /**
         * Tests multiple choice rendering.
         */
        test('should render multiple choice with "Select all" text', () => {
            const html = module.renderQuestion(sampleSurveyQuestions.per_question[3]);

            expect(html).toContain('Select all that apply');
            expect(html).toContain('Method A');
            expect(html).toContain('data-multi="true"');
        });

        /**
         * Tests Likert scale rendering.
         */
        test('should render Likert scale with labels', () => {
            const html = module.renderQuestion(sampleSurveyQuestions.per_question[2]);

            expect(html).toContain('likert-option');
            expect(html).toContain('Low');
            expect(html).toContain('High');
        });

        /**
         * Tests free text rendering.
         */
        test('should render free text textarea', () => {
            const html = module.renderQuestion(sampleSurveyQuestions.per_question[1]);

            expect(html).toContain('textarea');
            expect(html).toContain('maxlength="500"');
        });

        /**
         * Tests help text rendering.
         */
        test('should render help text when provided', () => {
            const question = {
                ...sampleSurveyQuestions.per_question[0],
                help_text: 'This is helpful information'
            };

            const html = module.renderQuestion(question);

            expect(html).toContain('This is helpful information');
        });

        /**
         * Tests conditional attributes.
         */
        test('should add conditional attributes', () => {
            const html = module.renderQuestion(sampleSurveyQuestions.per_question[1]);

            expect(html).toContain('data-condition-depends="q1"');
            expect(html).toContain('data-condition-values');
        });
    });

    describe('Response Collection', () => {
        beforeEach(() => {
            module.renderPerQuestionSurvey('#survey-container');
        });

        /**
         * Tests single choice response collection.
         */
        test('should collect single choice response on click', () => {
            const option = container.querySelector('[data-question="q1"][data-value="Yes"]');
            option.click();

            expect(module.responses.q1).toBe('Yes');
        });

        /**
         * Tests that previous selection is cleared for single choice.
         */
        test('should clear previous selection for single choice', () => {
            const yesOption = container.querySelector('[data-question="q1"][data-value="Yes"]');
            const noOption = container.querySelector('[data-question="q1"][data-value="No"]');

            yesOption.click();
            noOption.click();

            expect(module.responses.q1).toBe('No');
            expect(yesOption.classList.contains('selected')).toBe(false);
            expect(noOption.classList.contains('selected')).toBe(true);
        });

        /**
         * Tests multiple choice response collection.
         */
        test('should collect multiple choice responses as array', () => {
            const optionA = container.querySelector('[data-question="q4"][data-value="Method A"]');
            const optionB = container.querySelector('[data-question="q4"][data-value="Method B"]');

            optionA.click();
            optionB.click();

            expect(module.responses.q4).toEqual(['Method A', 'Method B']);
        });

        /**
         * Tests multiple choice toggle behavior.
         */
        test('should toggle multiple choice selections', () => {
            const optionA = container.querySelector('[data-question="q4"][data-value="Method A"]');

            optionA.click();
            optionA.click(); // Toggle off

            expect(module.responses.q4).toEqual([]);
        });

        /**
         * Tests Likert response collection.
         */
        test('should collect Likert response', () => {
            const option = container.querySelector('[data-question="q3"][data-value="4"]');
            option.click();

            expect(module.responses.q3).toBe('4');
        });

        /**
         * Tests free text response collection.
         */
        test('should collect free text on input', () => {
            const textarea = container.querySelector('[data-question="q2"]');
            textarea.value = 'Test explanation';
            textarea.dispatchEvent(new Event('input'));

            expect(module.responses.q2).toBe('Test explanation');
        });
    });

    describe('Conditional Visibility', () => {
        beforeEach(() => {
            module.renderPerQuestionSurvey('#survey-container');
        });

        /**
         * Tests that conditional question shows when condition met.
         */
        test('should show conditional question when condition met', () => {
            const noOption = container.querySelector('[data-question="q1"][data-value="No"]');
            noOption.click();

            const conditionalQ = container.querySelector('[data-question-id="q2"]');
            expect(conditionalQ.classList.contains('hidden')).toBe(false);
        });

        /**
         * Tests that conditional question hides when condition not met.
         */
        test('should hide conditional question when condition not met', () => {
            // First show it
            const noOption = container.querySelector('[data-question="q1"][data-value="No"]');
            noOption.click();

            // Then select different option
            const yesOption = container.querySelector('[data-question="q1"][data-value="Yes"]');
            yesOption.click();

            const conditionalQ = container.querySelector('[data-question-id="q2"]');
            expect(conditionalQ.classList.contains('hidden')).toBe(true);
        });
    });

    describe('validate method', () => {
        beforeEach(() => {
            module.renderPerQuestionSurvey('#survey-container');
        });

        /**
         * Tests that validation fails for missing required fields.
         */
        test('should fail validation for missing required fields', () => {
            const isValid = module.validate('per_question');

            expect(isValid).toBe(false);
            expect(Object.keys(module.errors).length).toBeGreaterThan(0);
        });

        /**
         * Tests that validation passes for complete responses.
         */
        test('should pass validation for complete responses', () => {
            // Fill required fields
            module.responses = {
                q1: 'Yes',
                q3: '4',
                q4: ['Method A']
            };

            const isValid = module.validate('per_question');

            expect(isValid).toBe(true);
        });

        /**
         * Tests that hidden conditional questions are skipped.
         */
        test('should skip hidden conditional questions', () => {
            module.responses = {
                q1: 'Yes', // q2 should be hidden
                q3: '4',
                q4: ['Method A']
            };

            const isValid = module.validate('per_question');

            expect(isValid).toBe(true);
            expect(module.errors.q2).toBeUndefined();
        });

        /**
         * Tests that q2 is required when q1 is 'No'.
         * User must provide an explanation when indicating the model is not clinically sound.
         */
        test('should require q2 when q1 is No', () => {
            // First select 'No' to show the conditional q2 field
            const noOption = container.querySelector('[data-question="q1"][data-value="No"]');
            noOption.click();

            // Set other required responses but leave q2 empty
            module.responses.q3 = '4';
            module.responses.q4 = ['Method A'];

            const isValid = module.validate('per_question');

            expect(isValid).toBe(false);
            expect(module.errors.q2).toBeDefined();
        });

    });

    describe('showError and clearError methods', () => {
        beforeEach(() => {
            module.renderPerQuestionSurvey('#survey-container');
        });

        /**
         * Tests that showError displays message.
         */
        test('should display error message', () => {
            module.showError('q1', 'This is required');

            const errorEl = container.querySelector('[data-error-for="q1"]');
            expect(errorEl.textContent).toBe('This is required');
        });

        /**
         * Tests that clearError removes message.
         */
        test('should clear error message', () => {
            module.showError('q1', 'Error');
            module.clearError('q1');

            const errorEl = container.querySelector('[data-error-for="q1"]');
            expect(errorEl.textContent).toBe('');
        });
    });

    describe('getResponses method', () => {
        /**
         * Tests that getResponses returns copy of responses.
         */
        test('should return copy of responses', () => {
            module.responses = { q1: 'Yes' };

            const result = module.getResponses();

            expect(result).toEqual({ q1: 'Yes' });
            expect(result).not.toBe(module.responses); // Should be copy
        });
    });

    describe('clearResponses method', () => {
        /**
         * Tests that clearResponses resets state.
         */
        test('should clear responses and errors', () => {
            module.responses = { q1: 'Yes' };
            module.errors = { q2: 'Error' };

            module.clearResponses();

            expect(module.responses).toEqual({});
            expect(module.errors).toEqual({});
        });
    });

    describe('escapeHtml method', () => {
        /**
         * Tests XSS prevention.
         */
        test('should escape HTML characters', () => {
            const result = module.escapeHtml('<script>alert(1)</script>');

            expect(result).not.toContain('<script>');
        });
    });
});

describe('"Same as before" logic', () => {
    let module;
    let container;

    // Survey questions matching the actual backend structure for this feature
    const realishQuestions = {
        per_question: [
            {
                id: 'q1_answer_correct',
                text: "Is the model's answer correct?",
                question_type: 'single_choice',
                options: ['Correct', 'Incorrect'],
                required: true
            },
            {
                id: 'q1_confidence',
                text: 'How confident are you?',
                question_type: 'likert',
                required: true,
                likert_min: 1,
                likert_max: 5,
                likert_labels: { 1: 'Not at all confident', 5: 'Very confident' }
            },
            {
                id: 'q2_clinically_valid',
                text: 'Do you think the model made its prediction based on clinically valid or biased reasoning, regardless of correctness?',
                question_type: 'single_choice',
                options: ['Unbiased', 'Biased'],
                required: true
            },
            {
                id: 'q2_confidence',
                text: 'How confident are you?',
                question_type: 'likert',
                required: true,
                likert_min: 1,
                likert_max: 5,
                likert_labels: { 1: 'Not at all confident', 5: 'Very confident' }
            },
            {
                id: 'q3_same_as_before',
                text: 'Is the pattern of clinically invalid reasoning the same as your previous assessment?',
                question_type: 'single_choice',
                options: ['Same as before', 'Different'],
                required: true,
                condition: {
                    depends_on: 'q2_clinically_valid',
                    show_when: ['Biased']
                },
                min_question_index: 1
            },
            {
                id: 'q3_invalid_description',
                text: 'In what way is the reasoning biased?',
                question_type: 'free_text',
                required: true,
                max_length: 500,
                condition: {
                    depends_on: 'q2_clinically_valid',
                    show_when: ['Biased']
                },
                help_text: 'Describe any patterns, features, or correlations you noticed that seem clinically inappropriate.'
            },
            {
                id: 'q4_inference_method',
                text: 'How did you arrive at your conclusion? (Select all that apply)',
                question_type: 'multiple_choice',
                options: [
                    "From the model's reasoning text",
                    'From the interpretability tool visualization',
                    'From testing via the chat interface',
                    'From my clinical knowledge/intuition',
                    'Other'
                ],
                required: true
            },
            {
                id: 'q4_inference_elaboration',
                text: 'Please elaborate on how you reached your conclusion:',
                question_type: 'free_text',
                required: false,
                max_length: 1000,
                condition: {
                    depends_on: 'q4_inference_method',
                    show_when_includes: ['Other']
                },
                help_text: 'Describe your thought process and what evidence most influenced your assessment.'
            }
        ],
        batch: []
    };

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'survey-container';
        document.body.appendChild(container);

        module = new SurveyModule();
        module.surveyQuestions = realishQuestions;
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    describe('within a batch', () => {
        test('should NOT show "same as before" on first question even if q2=No', () => {
            module.setQuestionIndex(0);
            module.renderPerQuestionSurvey('#survey-container');

            // Select No for clinically valid
            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            const sameQ = container.querySelector('[data-question-id="q3_same_as_before"]');
            // Gated by min_question_index=1, so it should be an empty hidden div
            expect(sameQ.dataset.gatedByIndex).toBe('true');
            expect(sameQ.classList.contains('hidden')).toBe(true);
        });

        test('should show q3_invalid_description directly on first question when q2=No', () => {
            module.setQuestionIndex(0);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            const descQ = container.querySelector('[data-question-id="q3_invalid_description"]');
            expect(descQ.classList.contains('hidden')).toBe(false);
        });

        test('should NOT show "same as before" on second question if user answered Yes on first question', () => {
            // Simulate: first question user answered Yes (no description saved)
            module.setQuestionIndex(0);
            module.renderPerQuestionSurvey('#survey-container');
            // User selects Yes -> no invalid description
            module.responses['q2_clinically_valid'] = 'Unbiased';
            module.clearResponses(); // saves nothing to lastInvalidDescription

            // Now second question
            module.setQuestionIndex(1);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            const sameQ = container.querySelector('[data-question-id="q3_same_as_before"]');
            // Should be hidden because there's no lastInvalidDescription
            expect(sameQ.classList.contains('hidden')).toBe(true);
        });

        test('should show "same as before" on second question if user answered No and described on first question', () => {
            // Simulate: first question user described invalid reasoning
            module.setQuestionIndex(0);
            module.renderPerQuestionSurvey('#survey-container');
            module.responses['q2_clinically_valid'] = 'Biased';
            module.responses['q3_invalid_description'] = 'Model uses age as spurious factor.';
            module.clearResponses(); // saves lastInvalidDescription

            // Now second question
            module.setQuestionIndex(1);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            const sameQ = container.querySelector('[data-question-id="q3_same_as_before"]');
            expect(sameQ.classList.contains('hidden')).toBe(false);
        });

        test('should display the previous description text alongside "same as before"', () => {
            module.lastInvalidDescription = 'Model uses age as spurious factor.';
            module.setQuestionIndex(1);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            const sameQ = container.querySelector('[data-question-id="q3_same_as_before"]');
            expect(sameQ.textContent).toContain('Your previous assessment');
            expect(sameQ.textContent).toContain('Model uses age as spurious factor.');
        });

        test('should hide q3_invalid_description when "Same as before" is selected', () => {
            module.lastInvalidDescription = 'Model uses age as spurious factor.';
            module.setQuestionIndex(1);
            module.renderPerQuestionSurvey('#survey-container');

            // Select No for clinically valid
            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            // Select "Same as before"
            const sameBtn = container.querySelector('[data-question="q3_same_as_before"][data-value="Same as before"]');
            sameBtn.click();

            const descQ = container.querySelector('[data-question-id="q3_invalid_description"]');
            expect(descQ.classList.contains('hidden')).toBe(true);
        });

        test('should show q3_invalid_description when "Different" is selected', () => {
            module.lastInvalidDescription = 'Model uses age as spurious factor.';
            module.setQuestionIndex(1);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            const diffBtn = container.querySelector('[data-question="q3_same_as_before"][data-value="Different"]');
            diffBtn.click();

            const descQ = container.querySelector('[data-question-id="q3_invalid_description"]');
            expect(descQ.classList.contains('hidden')).toBe(false);
        });

        test('should require q3_invalid_description when q2=No and no prior description exists', () => {
            // No lastInvalidDescription -> "same as before" hidden, description shown directly
            module.setQuestionIndex(1);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            // q3_invalid_description should be visible (no "same as before" gate)
            const descQ = container.querySelector('[data-question-id="q3_invalid_description"]');
            expect(descQ.classList.contains('hidden')).toBe(false);

            // And "same as before" should still be hidden
            const sameQ = container.querySelector('[data-question-id="q3_same_as_before"]');
            expect(sameQ.classList.contains('hidden')).toBe(true);
        });
    });

    describe('across batches', () => {
        test('should clear lastInvalidDescription when resetForNewBatch is called', () => {
            module.lastInvalidDescription = 'Previous batch description';
            module.resetForNewBatch();

            expect(module.lastInvalidDescription).toBeNull();
        });

        test('should NOT show "same as before" in new batch even if previous batch had a description', () => {
            // Simulate end of batch 1: user had an invalid description
            module.lastInvalidDescription = 'Batch 1 description';

            // Start batch 2
            module.resetForNewBatch();
            module.setQuestionIndex(0);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            // "Same as before" should be hidden (index 0 + no lastInvalidDescription)
            const sameQ = container.querySelector('[data-question-id="q3_same_as_before"]');
            expect(sameQ.dataset.gatedByIndex).toBe('true');
            expect(sameQ.classList.contains('hidden')).toBe(true);
        });

        test('should NOT show previous batch description in second batch question 2', () => {
            // Simulate: batch 1 had description, then reset
            module.lastInvalidDescription = 'Batch 1 description';
            module.resetForNewBatch();

            // Batch 2, question 1: user says Yes
            module.setQuestionIndex(0);
            module.renderPerQuestionSurvey('#survey-container');
            module.responses['q2_clinically_valid'] = 'Unbiased';
            module.clearResponses();

            // Batch 2, question 2: user says No
            module.setQuestionIndex(1);
            module.renderPerQuestionSurvey('#survey-container');

            const noOption = container.querySelector('[data-question="q2_clinically_valid"][data-value="Biased"]');
            noOption.click();

            // "Same as before" should be hidden (no description from this batch)
            const sameQ = container.querySelector('[data-question-id="q3_same_as_before"]');
            expect(sameQ.classList.contains('hidden')).toBe(true);

            // Description should show directly
            const descQ = container.querySelector('[data-question-id="q3_invalid_description"]');
            expect(descQ.classList.contains('hidden')).toBe(false);
        });

        test('clearResponses should save description only from current responses, not resurrect old ones', () => {
            module.lastInvalidDescription = 'Old description';

            // Clear with no q3_invalid_description in responses
            module.responses = { 'q2_clinically_valid': 'Unbiased' };
            module.clearResponses();

            // lastInvalidDescription should remain as 'Old description' (not nulled, not overwritten)
            expect(module.lastInvalidDescription).toBe('Old description');

            // But resetForNewBatch clears it
            module.resetForNewBatch();
            expect(module.lastInvalidDescription).toBeNull();
        });
    });
});

describe('Singleton Instance (surveyModule)', () => {
    /**
     * Tests that global singleton exists.
     */
    test('should export surveyModule singleton', () => {
        expect(surveyModule).toBeDefined();
        expect(surveyModule).toBeInstanceOf(SurveyModule);
    });
});
