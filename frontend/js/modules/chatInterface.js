/**
 * Chat Interface Module
 * Live chat with the current organism (served by vLLM; no interpretability readouts).
 *
 * The conversation starts pre-seeded with the item's own exchange (question prompt +
 * cached response), so follow-ups are grounded in what the clinician just read.
 * "New conversation" clears it, for writing a fresh probe case.
 */

class ChatInterfaceModule {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.messages = [];
        this.seedLength = 0;
        this.isLoading = false;
        this.batch = null;
        this.itemId = null;
    }

    setContainer(containerSelector) {
        this.container = document.querySelector(containerSelector);
    }

    init(batch, itemId, seedMessages = []) {
        this.batch = batch;
        this.itemId = itemId;
        this.messages = [...seedMessages];
        this.seedLength = seedMessages.length;
        this.expanded = new Set();
        this.render();
    }

    newConversation() {
        this.messages = [];
        this.seedLength = 0;
        window.studyTimer?.logEvent('chat_new_conversation');
        this.render();
    }

    /**
     * Webchat layout: user turns right, model turns left. The seeded question/response
     * pair is shown as ordinary turns so the conversation visibly continues from it; both
     * are collapsed to a preview (they are shown in full in the panels above).
     */
    render() {
        if (!this.container) return;
        const PREVIEW = 220;
        const bubble = (m, idx) => {
            let text = this.escapeHtml(m.content);
            let more = '';
            if (idx < this.seedLength && !this.expanded.has(idx) && m.content.length > PREVIEW) {
                text = this.escapeHtml(m.content.slice(0, PREVIEW)) + '…';
                more = `<button data-expand="${idx}" class="chat-expand block mt-1 text-xs underline opacity-80">show full ${m.role === 'user' ? 'question' : 'response'}</button>`;
            }
            const who = m.role === 'user' ? 'You' : 'Model';
            return `
                <div class="chat-row ${m.role}">
                    <div class="text-xs text-gray-400 mb-1 ${m.role === 'user' ? 'text-right' : ''}">${who}</div>
                    <div class="chat-message ${m.role} whitespace-pre-wrap">${text}${more}</div>
                </div>`;
        };
        const empty = this.messages.length ? '' : `
            <div class="text-center text-gray-400 text-sm py-8">
                New conversation: the model has no prior context.
            </div>`;

        this.container.innerHTML = `
            <div class="flex justify-between items-center mb-3">
                <h2 class="text-lg font-semibold text-gray-800">Conversation</h2>
                <button id="chat-new-btn" class="text-sm text-blue-600 hover:text-blue-800" ${this.isLoading ? 'disabled' : ''}>
                    New conversation
                </button>
            </div>
            <div class="chat-container">
                <div class="chat-messages" id="chat-messages">
                    ${empty}
                    ${this.messages.map(bubble).join('')}
                    ${this.isLoading ? '<div class="chat-row assistant"><div class="chat-message assistant"><span class="loading-spinner"></span></div></div>' : ''}
                </div>
                <div class="chat-input-container">
                    <textarea id="chat-input" rows="2" class="chat-input resize-y"
                              placeholder="Continue the conversation. Enter to send, Shift+Enter for a new line"
                              ${this.isLoading ? 'disabled' : ''}></textarea>
                    <button id="chat-send-btn" class="chat-send-btn" ${this.isLoading ? 'disabled' : ''}>Send</button>
                </div>
            </div>
        `;

        const input = document.getElementById('chat-input');
        input?.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        document.getElementById('chat-send-btn')?.addEventListener('click', () => this.sendMessage());
        document.getElementById('chat-new-btn')?.addEventListener('click', () => this.newConversation());
        this.container.querySelectorAll('.chat-expand').forEach(b => b.addEventListener('click', () => {
            this.expanded.add(Number(b.dataset.expand));
            this.render();
        }));
        if (this.messages.length > this.seedLength) this.scrollToBottom();
    }

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input?.value.trim();
        if (!message || this.isLoading) return;

        this.messages.push({ role: 'user', content: message });
        window.studyTimer?.logEvent('chat_message_sent', { message_length: message.length });
        this.isLoading = true;
        this.render();

        try {
            const res = await window.API.chatWithModel(this.batch, this.itemId, this.messages);
            this.messages.push({ role: 'assistant', content: res.response });
        } catch (error) {
            this.messages.pop();  // keep the history valid for the next attempt
            alert(error.message);
            this.isLoading = false;
            this.render();
            document.getElementById('chat-input').value = message;
            return;
        }
        this.isLoading = false;
        this.render();
    }

    scrollToBottom() {
        const el = document.getElementById('chat-messages');
        if (el) el.scrollTop = el.scrollHeight;
    }

    getMessages() {
        return this.messages;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

const chatInterface = new ChatInterfaceModule('#chat-panel');
window.ChatInterfaceModule = ChatInterfaceModule;
window.chatInterface = chatInterface;
