/**
 * Chat Interface Module
 * Handles interactive chat with the model.
 */

class ChatInterfaceModule {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.messages = [];
        this.isLoading = false;
        this.participantId = null;
        this.context = {};
        
        // External model URL (if using separate window/server)
        this.externalModelUrl = null;
    }
    
    /**
     * Set the container element.
     */
    setContainer(containerSelector) {
        this.container = document.querySelector(containerSelector);
    }
    
    /**
     * Initialize chat interface.
     */
    init(participantId, context = {}, externalModelUrl = null) {
        this.participantId = participantId;
        this.context = context;
        this.messages = [];
        this.externalModelUrl = externalModelUrl;
        
        this.render();
    }
    
    /**
     * Render the chat interface.
     */
    render() {
        if (!this.container) {
            console.error('Chat container not found');
            return;
        }
        
        const externalLinkHtml = this.externalModelUrl ? `
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-3">
                <p class="text-sm text-yellow-800">
                    <strong>Note:</strong> For more complex interactions, you can also 
                    <a href="${this.externalModelUrl}" target="_blank" class="underline text-yellow-900 hover:text-yellow-700">
                        open the model in a separate window
                    </a>.
                </p>
            </div>
        ` : '';
        
        const html = `
            <h2 class="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                Interactive Testing
            </h2>
            
            <p class="text-sm text-gray-500 mb-3">
                Test the model with your own inputs to investigate its behavior.
            </p>
            
            ${externalLinkHtml}
            
            <div class="chat-container">
                <div class="chat-messages" id="chat-messages">
                    ${this.renderMessages()}
                </div>
                
                <div class="chat-input-container">
                    <input type="text" 
                           id="chat-input" 
                           class="chat-input"
                           placeholder="Enter a test query..."
                           ${this.isLoading ? 'disabled' : ''}>
                    <button id="chat-send-btn" 
                            class="chat-send-btn"
                            ${this.isLoading ? 'disabled' : ''}>
                        ${this.isLoading ? 
                            '<span class="loading-spinner"></span>' : 
                            `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                            </svg>`
                        }
                    </button>
                </div>
            </div>
        `;
        
        this.container.innerHTML = html;
        this.attachEventListeners();
    }
    
    /**
     * Render chat messages.
     */
    renderMessages() {
        if (this.messages.length === 0) {
            return `
                <div class="text-center text-gray-400 text-sm py-8">
                    Try asking the model about its reasoning or test with modified inputs...
                </div>
            `;
        }
        
        return this.messages.map(msg => `
            <div class="chat-message ${msg.role}">
                ${this.escapeHtml(msg.content)}
            </div>
        `).join('');
    }
    
    /**
     * Attach event listeners.
     */
    attachEventListeners() {
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('chat-send-btn');
        
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !this.isLoading) {
                    this.sendMessage();
                }
            });
        }
        
        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                if (!this.isLoading) {
                    this.sendMessage();
                }
            });
        }
    }
    
    /**
     * Send a message to the model.
     */
    async sendMessage() {
        const input = document.getElementById('chat-input');
        if (!input) return;
        
        const message = input.value.trim();
        if (!message) return;
        
        // Add user message
        this.addMessage('user', message);
        input.value = '';
        
        // Log event
        window.studyTimer?.logEvent('chat_message_sent', {
            message_length: message.length
        });
        
        // Set loading state
        this.isLoading = true;
        this.render();
        
        try {
            // Call API
            const response = await window.API.chatWithModel(
                message,
                this.context,
                this.participantId
            );
            
            // Add assistant response
            this.addMessage('assistant', response.response);
            
            // Log event
            window.studyTimer?.logEvent('chat_response_received', {
                response_length: response.response.length
            });
            
        } catch (error) {
            console.error('Chat error:', error);
            this.addMessage('assistant', `Error: ${error.message}. Please try again.`);
        }
        
        this.isLoading = false;
        this.render();
        
        // Scroll to bottom
        this.scrollToBottom();
    }
    
    /**
     * Add a message to the chat.
     */
    addMessage(role, content) {
        this.messages.push({
            role,
            content,
            timestamp: new Date().toISOString()
        });
    }
    
    /**
     * Scroll chat to bottom.
     */
    scrollToBottom() {
        const messagesContainer = document.getElementById('chat-messages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
    
    /**
     * Get chat history.
     */
    getMessages() {
        return this.messages;
    }
    
    /**
     * Clear chat history.
     */
    clear() {
        this.messages = [];
        this.context = {};
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
    
    /**
     * Update context (e.g., when question changes).
     */
    updateContext(context) {
        this.context = context;
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
const chatInterface = new ChatInterfaceModule('#chat-panel');

// Make globally available
window.ChatInterfaceModule = ChatInterfaceModule;
window.chatInterface = chatInterface;
