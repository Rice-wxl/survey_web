/**
 * Unit tests for the API utility module (api.js).
 *
 * Tests cover:
 * - Request building and headers
 * - All API endpoint wrappers
 * - Error handling
 * - JSON body serialization
 */

// Load the API module
const fs = require('fs');
const path = require('path');

// Read and evaluate the API module in our test environment
const apiCode = fs.readFileSync(
    path.join(__dirname, '../../js/utils/api.js'),
    'utf8'
);
eval(apiCode);

describe('API Utility Module', () => {
    // Reset fetch mock before each test
    beforeEach(() => {
        fetch.mockClear();
        window.API.baseUrl = 'http://localhost:5000';
    });

    describe('request method', () => {
        /**
         * Tests that requests are made to the correct URL with /api prefix.
         */
        test('should make request to correct URL with /api prefix', async () => {
            mockFetchSuccess({ data: 'test' });

            await API.request('/test/endpoint');

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/test/endpoint',
                expect.any(Object)
            );
        });

        /**
         * Tests that Content-Type header is set to JSON by default.
         */
        test('should set Content-Type to application/json by default', async () => {
            mockFetchSuccess({});

            await API.request('/test');

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Content-Type': 'application/json'
                    })
                })
            );
        });

        /**
         * Tests that object bodies are automatically JSON stringified.
         */
        test('should stringify object bodies to JSON', async () => {
            mockFetchSuccess({});

            await API.request('/test', {
                method: 'POST',
                body: { key: 'value', number: 42 }
            });

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    body: JSON.stringify({ key: 'value', number: 42 })
                })
            );
        });

        /**
         * Tests that custom headers are merged with defaults.
         */
        test('should merge custom headers with defaults', async () => {
            mockFetchSuccess({});

            await API.request('/test', {
                headers: { 'X-Custom-Header': 'custom-value' }
            });

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Content-Type': 'application/json',
                        'X-Custom-Header': 'custom-value'
                    })
                })
            );
        });

        /**
         * Tests that successful responses are parsed as JSON.
         */
        test('should return parsed JSON on success', async () => {
            const responseData = { success: true, data: [1, 2, 3] };
            mockFetchSuccess(responseData);

            const result = await API.request('/test');

            expect(result).toEqual(responseData);
        });

        /**
         * Tests that HTTP errors throw with error message from response.
         */
        test('should throw error with message from failed response', async () => {
            mockFetchError(400, { error: 'Bad request message' });

            await expect(API.request('/test')).rejects.toThrow('Bad request message');
        });

        /**
         * Tests that HTTP errors include status code when no error message.
         */
        test('should throw error with status code when no error message', async () => {
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                json: () => Promise.resolve({})
            });

            await expect(API.request('/test')).rejects.toThrow('HTTP 500');
        });

        /**
         * Tests that network errors are propagated.
         */
        test('should propagate network errors', async () => {
            mockFetchNetworkError('Connection refused');

            await expect(API.request('/test')).rejects.toThrow('Connection refused');
        });
    });

    describe('Session Endpoints', () => {
        /**
         * Tests starting a session without participant ID.
         */
        test('startSession should POST without participant_id', async () => {
            mockFetchSuccess({ participant_id: 'P_123', success: true });

            const result = await API.startSession();

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/session/start',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({ participant_id: null })
                })
            );
            expect(result.participant_id).toBe('P_123');
        });

        /**
         * Tests starting a session with custom participant ID.
         */
        test('startSession should use provided participant_id', async () => {
            mockFetchSuccess({ participant_id: 'custom_id', success: true });

            await API.startSession('custom_id');

            expect(fetch).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    body: JSON.stringify({ participant_id: 'custom_id' })
                })
            );
        });

        /**
         * Tests assigning a tool to a session.
         */
        test('assignTool should POST tool name to correct endpoint', async () => {
            mockFetchSuccess({ success: true, assigned_tool: 'mock_tool' });

            await API.assignTool('participant_123', 'mock_tool');

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/session/participant_123/assign_tool',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({ tool_name: 'mock_tool' })
                })
            );
        });
    });

    describe('QA Endpoints', () => {
        /**
         * Tests getting spurious types list.
         */
        test('getSpuriousTypes should GET from correct endpoint', async () => {
            mockFetchSuccess({ spurious_types: [] });

            await API.getSpuriousTypes();

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/qa/spurious_types',
                expect.not.objectContaining({ method: 'POST' })
            );
        });

        /**
         * Tests getting questions by spurious type.
         */
        test('getQuestions should include spurious type in URL', async () => {
            mockFetchSuccess({ question_ids: ['q1', 'q2'] });

            await API.getQuestions('demographic_bias');

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/qa/questions/demographic_bias',
                expect.any(Object)
            );
        });

        /**
         * Tests getting a specific question by ID.
         */
        test('getQuestion should include question ID in URL', async () => {
            mockFetchSuccess({ id: 'q1', question: 'Test?' });

            await API.getQuestion('demo_001');

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/qa/question/demo_001',
                expect.any(Object)
            );
        });
    });

    describe('Model Endpoints', () => {
        /**
         * Tests chat with model endpoint.
         */
        test('chatWithModel should POST message with context', async () => {
            mockFetchSuccess({ response: 'Model response' });

            const context = { question: 'Original question' };
            await API.chatWithModel('User message', context, 'participant_1');

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/model/chat',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({
                        message: 'User message',
                        context: context,
                        participant_id: 'participant_1'
                    })
                })
            );
        });
    });

    describe('Interpretability Endpoints', () => {
        /**
         * Tests computing interpretation endpoint.
         */
        test('computeInterpretation should POST with all required fields', async () => {
            mockFetchSuccess({
                tool_name: 'mock_tool',
                result: { tokens: [], attributions: [] }
            });

            await API.computeInterpretation(
                'mock_tool',
                'q1',
                'model input text',
                'model output text'
            );

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/interp/compute',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({
                        tool_name: 'mock_tool',
                        question_id: 'q1',
                        model_input: 'model input text',
                        model_output: 'model output text'
                    })
                })
            );
        });

        /**
         * Tests getting available tools endpoint.
         */
        test('getAvailableTools should GET tools list', async () => {
            mockFetchSuccess({ tools: [{ name: 'mock_tool' }] });

            const result = await API.getAvailableTools();

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/interp/tools',
                expect.any(Object)
            );
            expect(result.tools).toHaveLength(1);
        });
    });

    describe('Survey Endpoints', () => {
        /**
         * Tests getting survey questions endpoint.
         */
        test('getSurveyQuestions should GET survey template', async () => {
            mockFetchSuccess({
                per_question: [],
                batch: []
            });

            await API.getSurveyQuestions();

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/survey/questions',
                expect.any(Object)
            );
        });

        /**
         * Tests submitting survey responses.
         */
        test('submitSurvey should POST with all survey data', async () => {
            mockFetchSuccess({ success: true });

            const responses = { q1: 'Yes', q2: 4 };
            const timingData = { total_seconds: 120 };

            await API.submitSurvey('participant_1', 'q1', responses, timingData);

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/survey/submit',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({
                        participant_id: 'participant_1',
                        question_id: 'q1',
                        responses: responses,
                        timing_data: timingData
                    })
                })
            );
        });

        /**
         * Tests submitting batch survey.
         */
        test('submitBatchSurvey should POST batch completion data', async () => {
            mockFetchSuccess({ success: true });

            await API.submitBatchSurvey(
                'participant_1',
                'demographic_bias',
                'mock_tool',
                4,
                'Good tool'
            );

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/survey/batch_complete',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({
                        participant_id: 'participant_1',
                        spurious_type: 'demographic_bias',
                        tool_name: 'mock_tool',
                        usefulness_rating: 4,
                        comments: 'Good tool'
                    })
                })
            );
        });
    });

    describe('End-of-Study Survey Endpoint', () => {
        test('submitEndOfStudySurvey should POST interface choice and comments', async () => {
            mockFetchSuccess({ success: true });

            await API.submitEndOfStudySurvey(
                'participant_1',
                'input_attribution',
                'Great study'
            );

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/survey/end_of_study',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({
                        participant_id: 'participant_1',
                        most_helpful_interface: 'input_attribution',
                        comments: 'Great study'
                    })
                })
            );
        });
    });

    describe('Export Endpoint', () => {
        /**
         * Tests exporting session data.
         */
        test('exportSession should GET with participant ID', async () => {
            mockFetchSuccess({
                participant_id: 'p1',
                responses: []
            });

            await API.exportSession('p1');

            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:5000/api/export/p1',
                expect.any(Object)
            );
        });
    });
});
