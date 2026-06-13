/**
 * Unit tests for the Chat Interface module (chatInterface.js).
 *
 * Tests cover:
 * - Chat initialization
 * - Message rendering
 * - Message sending
 * - HTML escaping
 * - Loading states
 */

// Load dependencies
const fs = require('fs');
const path = require('path');

// Mock the API module and studyTimer
window.API = {
    chatWithModel: jest.fn()
};
window.studyTimer = {
    logEvent: jest.fn()
};

// Load the chat interface module
const moduleCode = fs.readFileSync(
    path.join(__dirname, '../../js/modules/chatInterface.js'),
    'utf8'
);
eval(moduleCode);

describe('ChatInterfaceModule', () => {
    let module;
    let container;

    beforeEach(() => {
        // Create container
        container = document.createElement('div');
        container.id = 'chat-panel';
        document.body.appendChild(container);

        module = new ChatInterfaceModule('#chat-panel');

        // Reset mocks
        window.API.chatWithModel.mockClear();
        window.studyTimer.logEvent.mockClear();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    describe('Initialization', () => {
        /**
         * Tests that module initializes with correct defaults.
         */
        test('should initialize with empty messages array', () => {
            expect(module.messages).toEqual([]);
        });

        /**
         * Tests that loading state starts as false.
         */
        test('should initialize with isLoading false', () => {
            expect(module.isLoading).toBe(false);
        });

        /**
         * Tests that participant ID starts null.
         */
        test('should initialize with null participantId', () => {
            expect(module.participantId).toBeNull();
        });
    });

    describe('init method', () => {
        /**
         * Tests that init sets up the chat correctly.
         */
        test('should set participantId and context', () => {
            const context = { question: 'Test?' };
            module.init('participant_1', context, null);

            expect(module.participantId).toBe('participant_1');
            expect(module.context).toBe(context);
        });

        /**
         * Tests that init clears previous messages.
         */
        test('should clear previous messages', () => {
            module.messages = [{ role: 'user', content: 'old' }];
            module.init('p1', {}, null);

            expect(module.messages).toEqual([]);
        });

        /**
         * Tests that init renders the chat interface.
         */
        test('should render chat interface', () => {
            module.init('p1', {}, null);

            expect(container.innerHTML).toContain('Interactive Testing');
            expect(container.innerHTML).toContain('chat-input');
        });

        /**
         * Tests that external model URL is stored.
         */
        test('should store external model URL', () => {
            module.init('p1', {}, 'http://external.model');

            expect(module.externalModelUrl).toBe('http://external.model');
        });
    });

    describe('render method', () => {
        /**
         * Tests that render shows placeholder when no messages.
         */
        test('should show placeholder when no messages', () => {
            module.init('p1', {}, null);

            expect(container.textContent).toContain('Try asking the model');
        });

        /**
         * Tests that render shows external link when URL provided.
         */
        test('should show external link when URL provided', () => {
            module.init('p1', {}, 'http://external.com');

            expect(container.innerHTML).toContain('http://external.com');
            expect(container.innerHTML).toContain('separate window');
        });

        /**
         * Tests that render shows loading spinner when loading.
         */
        test('should show loading spinner when isLoading', () => {
            module.init('p1', {}, null);
            module.isLoading = true;
            module.render();

            expect(container.innerHTML).toContain('loading-spinner');
        });

        /**
         * Tests that input is disabled when loading.
         */
        test('should disable input when loading', () => {
            module.init('p1', {}, null);
            module.isLoading = true;
            module.render();

            const input = container.querySelector('#chat-input');
            expect(input.disabled).toBe(true);
        });
    });

    describe('renderMessages method', () => {
        /**
         * Tests that messages are rendered with correct classes.
         */
        test('should render messages with role classes', () => {
            module.messages = [
                { role: 'user', content: 'Hello' },
                { role: 'assistant', content: 'Hi there' }
            ];

            const html = module.renderMessages();

            expect(html).toContain('class="chat-message user"');
            expect(html).toContain('class="chat-message assistant"');
        });

        /**
         * Tests that message content is escaped.
         */
        test('should escape message content', () => {
            module.messages = [
                { role: 'user', content: '<script>alert(1)</script>' }
            ];

            const html = module.renderMessages();

            expect(html).not.toContain('<script>');
        });
    });

    describe('addMessage method', () => {
        /**
         * Tests that addMessage adds message to array.
         */
        test('should add message to messages array', () => {
            module.addMessage('user', 'Test message');

            expect(module.messages).toHaveLength(1);
            expect(module.messages[0].role).toBe('user');
            expect(module.messages[0].content).toBe('Test message');
        });

        /**
         * Tests that addMessage includes timestamp.
         */
        test('should add timestamp to message', () => {
            module.addMessage('user', 'Test');

            expect(module.messages[0].timestamp).toBeDefined();
        });
    });

    describe('sendMessage method', () => {
        beforeEach(() => {
            module.init('participant_1', { question: 'Q' }, null);
        });

        /**
         * Tests that sendMessage adds user message.
         */
        test('should add user message', async () => {
            window.API.chatWithModel.mockResolvedValue({
                response: 'Model response'
            });

            // Set input value
            const input = container.querySelector('#chat-input');
            input.value = 'User question';

            await module.sendMessage();

            const userMessage = module.messages.find(m => m.role === 'user');
            expect(userMessage.content).toBe('User question');
        });

        /**
         * Tests that sendMessage clears input after sending.
         */
        test('should clear input after sending', async () => {
            window.API.chatWithModel.mockResolvedValue({
                response: 'Response'
            });

            const input = container.querySelector('#chat-input');
            input.value = 'Test';

            await module.sendMessage();

            expect(input.value).toBe('');
        });

        /**
         * Tests that sendMessage calls API with correct parameters.
         */
        test('should call API with message and context', async () => {
            window.API.chatWithModel.mockResolvedValue({
                response: 'Response'
            });

            const input = container.querySelector('#chat-input');
            input.value = 'My question';

            await module.sendMessage();

            expect(window.API.chatWithModel).toHaveBeenCalledWith(
                'My question',
                { question: 'Q' },
                'participant_1'
            );
        });

        /**
         * Tests that sendMessage adds assistant response.
         */
        test('should add assistant response', async () => {
            window.API.chatWithModel.mockResolvedValue({
                response: 'Model answer'
            });

            const input = container.querySelector('#chat-input');
            input.value = 'Question';

            await module.sendMessage();

            const assistantMessage = module.messages.find(m => m.role === 'assistant');
            expect(assistantMessage.content).toBe('Model answer');
        });

        /**
         * Tests that sendMessage logs events.
         */
        test('should log chat events', async () => {
            window.API.chatWithModel.mockResolvedValue({
                response: 'Response'
            });

            const input = container.querySelector('#chat-input');
            input.value = 'Test';

            await module.sendMessage();

            expect(window.studyTimer.logEvent).toHaveBeenCalledWith(
                'chat_message_sent',
                expect.any(Object)
            );
            expect(window.studyTimer.logEvent).toHaveBeenCalledWith(
                'chat_response_received',
                expect.any(Object)
            );
        });

        /**
         * Tests that sendMessage handles API errors.
         */
        test('should add error message on API failure', async () => {
            window.API.chatWithModel.mockRejectedValue(new Error('Network error'));

            const input = container.querySelector('#chat-input');
            input.value = 'Test';

            await module.sendMessage();

            const assistantMessage = module.messages.find(m => m.role === 'assistant');
            expect(assistantMessage.content).toContain('Error');
        });

        /**
         * Tests that empty messages are not sent.
         */
        test('should not send empty messages', async () => {
            const input = container.querySelector('#chat-input');
            input.value = '   '; // Whitespace only

            await module.sendMessage();

            expect(window.API.chatWithModel).not.toHaveBeenCalled();
        });
    });

    describe('getMessages method', () => {
        /**
         * Tests that getMessages returns copy of messages.
         */
        test('should return messages array', () => {
            module.messages = [{ role: 'user', content: 'Test' }];

            expect(module.getMessages()).toEqual(module.messages);
        });
    });

    describe('clear method', () => {
        /**
         * Tests that clear resets chat state.
         */
        test('should clear messages and context', () => {
            module.messages = [{ role: 'user', content: 'Test' }];
            module.context = { question: 'Q' };

            module.clear();

            expect(module.messages).toEqual([]);
            expect(module.context).toEqual({});
        });

        /**
         * Tests that clear empties container.
         */
        test('should empty container', () => {
            module.init('p1', {}, null);
            module.clear();

            expect(container.innerHTML).toBe('');
        });
    });

    describe('updateContext method', () => {
        /**
         * Tests that context can be updated.
         */
        test('should update context', () => {
            const newContext = { question: 'New question' };
            module.updateContext(newContext);

            expect(module.context).toBe(newContext);
        });
    });

    describe('escapeHtml method', () => {
        /**
         * Tests XSS prevention.
         */
        test('should escape HTML characters', () => {
            const result = module.escapeHtml('<script>');

            expect(result).not.toContain('<script>');
        });
    });
});

describe('Singleton Instance (chatInterface)', () => {
    /**
     * Tests that global singleton exists.
     */
    test('should export chatInterface singleton', () => {
        expect(chatInterface).toBeDefined();
        expect(chatInterface).toBeInstanceOf(ChatInterfaceModule);
    });
});
