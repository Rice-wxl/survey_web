/**
 * Unit tests for the QA Display module (qaDisplay.js).
 *
 * Tests cover:
 * - Question rendering
 * - HTML escaping for XSS prevention
 * - Getting input/output text for interpretability
 * - Chat context generation
 * - Loading and clearing states
 */

// Load the QA Display module
const fs = require('fs');
const path = require('path');

// Read and evaluate the module
const moduleCode = fs.readFileSync(
    path.join(__dirname, '../../js/modules/qaDisplay.js'),
    'utf8'
);
eval(moduleCode);

describe('QADisplayModule', () => {
    let module;
    let container;

    beforeEach(() => {
        // Create a container element in the DOM
        container = document.createElement('div');
        container.id = 'qa-panel';
        document.body.appendChild(container);

        module = new QADisplayModule('#qa-panel');
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    describe('Initialization', () => {
        /**
         * Tests that module initializes with correct container.
         */
        test('should find container by selector', () => {
            expect(module.container).toBe(container);
        });

        /**
         * Tests that module initializes with null currentQuestion.
         */
        test('should initialize with null currentQuestion', () => {
            expect(module.currentQuestion).toBeNull();
        });
    });

    describe('setContainer method', () => {
        /**
         * Tests that container can be changed after initialization.
         */
        test('should update container reference', () => {
            const newContainer = document.createElement('div');
            newContainer.id = 'new-container';
            document.body.appendChild(newContainer);

            module.setContainer('#new-container');

            expect(module.container).toBe(newContainer);
        });
    });

    describe('render method', () => {
        const sampleQuestion = {
            id: 'q1',
            question: 'What is the diagnosis?',
            choices: ['A. Option A', 'B. Option B', 'C. Option C', 'D. Option D'],
            model_answer: 'A',
            model_reasoning: 'The patient presents with classic symptoms.'
        };

        /**
         * Tests that render displays the question text.
         */
        test('should render question text', () => {
            module.render(sampleQuestion);

            expect(container.textContent).toContain('What is the diagnosis?');
        });

        /**
         * Tests that render displays all choices.
         */
        test('should render all choices', () => {
            module.render(sampleQuestion);

            sampleQuestion.choices.forEach(choice => {
                expect(container.textContent).toContain(choice);
            });
        });

        /**
         * Tests that render displays model reasoning.
         */
        test('should render model reasoning', () => {
            module.render(sampleQuestion);

            expect(container.textContent).toContain('The patient presents with classic symptoms.');
        });

        /**
         * Tests that render highlights the model's answer.
         */
        test('should highlight model answer choice', () => {
            module.render(sampleQuestion);

            const modelAnswerDiv = container.querySelector('.model-answer');
            expect(modelAnswerDiv).not.toBeNull();
            expect(modelAnswerDiv.textContent).toContain('A. Option A');
        });

        /**
         * Tests that render stores currentQuestion.
         */
        test('should store currentQuestion', () => {
            module.render(sampleQuestion);

            expect(module.currentQuestion).toBe(sampleQuestion);
        });

        /**
         * Tests that render handles missing container gracefully.
         */
        test('should not throw if container is null', () => {
            module.container = null;

            expect(() => module.render(sampleQuestion)).not.toThrow();
        });
    });

    describe('escapeHtml method', () => {
        /**
         * Tests that HTML special characters are escaped.
         */
        test('should escape < and > characters', () => {
            const result = module.escapeHtml('<script>alert("xss")</script>');

            expect(result).not.toContain('<script>');
            expect(result).toContain('&lt;script&gt;');
        });

        /**
         * Tests that ampersands are escaped.
         */
        test('should escape & character', () => {
            const result = module.escapeHtml('A & B');

            expect(result).toContain('&amp;');
        });

        /**
         * Tests that quotes are preserved (not entity-escaped in text context).
         * Note: DOM's textContent/innerHTML doesn't escape quotes since they're
         * safe in text content - only < > & need escaping for XSS prevention.
         */
        test('should preserve quotes in text', () => {
            const result = module.escapeHtml('He said "hello"');

            // Quotes are preserved as-is (safe in text context)
            expect(result).toContain('"hello"');
        });

        /**
         * Tests that normal text is preserved.
         */
        test('should preserve normal text', () => {
            const result = module.escapeHtml('Normal medical text');

            expect(result).toBe('Normal medical text');
        });
    });

    describe('getCurrentQuestion method', () => {
        /**
         * Tests that getCurrentQuestion returns stored question.
         */
        test('should return current question', () => {
            const question = { id: 'q1', question: 'Test?' };
            module.currentQuestion = question;

            expect(module.getCurrentQuestion()).toBe(question);
        });

        /**
         * Tests that getCurrentQuestion returns null when no question.
         */
        test('should return null when no question', () => {
            expect(module.getCurrentQuestion()).toBeNull();
        });
    });

    describe('getInputText method', () => {
        /**
         * Tests that getInputText combines question and choices.
         */
        test('should combine question and choices', () => {
            module.currentQuestion = {
                question: 'Test question?',
                choices: ['A. First', 'B. Second']
            };

            const result = module.getInputText();

            expect(result).toContain('Test question?');
            expect(result).toContain('A. First');
            expect(result).toContain('B. Second');
        });

        /**
         * Tests that getInputText uses newlines as separators.
         */
        test('should separate with newlines', () => {
            module.currentQuestion = {
                question: 'Q',
                choices: ['A', 'B']
            };

            const result = module.getInputText();

            expect(result).toBe('Q\nA\nB');
        });

        /**
         * Tests that getInputText returns empty string when no question.
         */
        test('should return empty string when no question', () => {
            expect(module.getInputText()).toBe('');
        });
    });

    describe('getOutputText method', () => {
        /**
         * Tests that getOutputText returns model reasoning.
         */
        test('should return model_reasoning', () => {
            module.currentQuestion = {
                model_reasoning: 'This is the reasoning.'
            };

            expect(module.getOutputText()).toBe('This is the reasoning.');
        });

        /**
         * Tests that getOutputText returns empty string when no question.
         */
        test('should return empty string when no question', () => {
            expect(module.getOutputText()).toBe('');
        });
    });

    describe('getChatContext method', () => {
        /**
         * Tests that getChatContext returns correct structure.
         */
        test('should return context object with all fields', () => {
            module.currentQuestion = {
                id: 'q1',
                question: 'Medical question?',
                choices: ['A', 'B', 'C'],
                model_answer: 'A',
                model_reasoning: 'Reasoning text'
            };

            const context = module.getChatContext();

            expect(context.question_id).toBe('q1');
            expect(context.question).toBe('Medical question?');
            expect(context.choices).toBe('A\nB\nC');
            expect(context.model_answer).toBe('A');
            expect(context.model_reasoning).toBe('Reasoning text');
        });

        /**
         * Tests that getChatContext returns empty object when no question.
         */
        test('should return empty object when no question', () => {
            expect(module.getChatContext()).toEqual({});
        });
    });

    describe('showLoading method', () => {
        /**
         * Tests that showLoading displays skeleton UI.
         */
        test('should display skeleton loading UI', () => {
            module.showLoading();

            expect(container.innerHTML).toContain('skeleton');
        });

        /**
         * Tests that showLoading handles missing container.
         */
        test('should not throw if container is null', () => {
            module.container = null;

            expect(() => module.showLoading()).not.toThrow();
        });
    });

    describe('clear method', () => {
        /**
         * Tests that clear empties the container.
         */
        test('should empty container', () => {
            container.innerHTML = '<div>Content</div>';
            module.clear();

            expect(container.innerHTML).toBe('');
        });

        /**
         * Tests that clear resets currentQuestion.
         */
        test('should reset currentQuestion to null', () => {
            module.currentQuestion = { id: 'q1' };
            module.clear();

            expect(module.currentQuestion).toBeNull();
        });
    });
});

describe('Singleton Instance (qaDisplay)', () => {
    /**
     * Tests that global qaDisplay instance exists.
     */
    test('should export singleton as qaDisplay', () => {
        expect(qaDisplay).toBeDefined();
        expect(qaDisplay).toBeInstanceOf(QADisplayModule);
    });
});
