/**
 * Chat Interface Module
 * Live chat with the current organism (served by vLLM; no interpretability readouts).
 *
 * Each question has its own list of conversations (sidebar), kept while the page is open:
 *   Original       pre-seeded with the item's own exchange (question prompt + cached
 *                  response), so follow-ups are grounded in what the clinician just read.
 *   fresh          "New conversation": empty, for writing a fresh probe case.
 *   counterfactual "Ask counterfactual": the clinician edits the vignette / option text
 *                  (letters fixed) and the server re-asks it with the item's own template,
 *                  in a new conversation that never sees the original.
 * Conversations after the Original share one numbering (2, 3, ...). An unsent
 * counterfactual draft is dropped as soon as the clinician leaves it; nothing about it is saved.
 */

const MAX_TURNS = 15;   // = backend Config.CHAT_MAX_TURNS (user turns per conversation)
const PREVIEW = 220;

/** Word-level diff of two strings: [{type: 'same'|'del'|'add', text}] (LCS over words). */
function wordDiff(a, b) {
    const x = a.split(/(\s+)/), y = b.split(/(\s+)/);
    const n = x.length, m = y.length;
    const L = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--)
        for (let j = m - 1; j >= 0; j--)
            L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    const ops = [];
    const push = (type, text) => {
        const last = ops[ops.length - 1];
        if (last && last.type === type) last.text += text; else ops.push({ type, text });
    };
    let i = 0, j = 0;
    while (i < n && j < m) {
        if (x[i] === y[j]) { push('same', x[i]); i++; j++; }
        else if (L[i + 1][j] >= L[i][j + 1]) push('del', x[i++]);
        else push('add', y[j++]);
    }
    while (i < n) push('del', x[i++]);
    while (j < m) push('add', y[j++]);
    return ops;
}

/** Changed spans of a diff: [{del, add}], one per run of edits between unchanged text. */
function diffHunks(ops) {
    const hunks = [];
    let cur = null;
    for (const op of ops) {
        if (op.type === 'same' && op.text.trim()) { cur = null; continue; }
        if (op.type === 'same') { if (cur) cur.del += op.text, cur.add += op.text; continue; }
        if (!cur) hunks.push(cur = { del: '', add: '' });
        cur[op.type] += op.text;
    }
    return hunks.map(h => ({ del: h.del.trim(), add: h.add.trim() }));
}

let _convSeq = 0;
const newConvId = () => `${Date.now().toString(36)}-${(_convSeq++).toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

class ChatInterfaceModule {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.sessions = {};     // "batch:itemId" -> {convs, activeId, nextIndex}
        this.session = null;
        this.isLoading = false; // one pending reply at a time, across all conversations
        this.batch = null;
        this.itemId = null;
        this.item = null;
    }

    setContainer(containerSelector) {
        this.container = document.querySelector(containerSelector);
    }

    get conv() {
        return this.session?.convs.find(c => c.id === this.session.activeId);
    }

    get messages() {
        return this.conv ? this.conv.messages : [];
    }

    /** Open the conversations of one question (restored if it was visited before). */
    init(batch, itemId, seedMessages = []) {
        if (this.session) this.dropDraft();
        this.batch = batch;
        this.itemId = itemId;
        this.item = window.qaDisplay?.getCurrentQuestion?.();
        const key = `${batch}:${itemId}`;
        if (!this.sessions[key]) {
            const original = this.makeConv('original', seedMessages);
            original.index = 1;
            this.sessions[key] = { convs: [original], activeId: original.id, nextIndex: 2 };
        }
        this.session = this.sessions[key];
        this.render();
    }

    makeConv(kind, messages = []) {
        return { id: newConvId(), index: null, kind, messages: [...messages],
                 seedLength: messages.length, cf: null, draft: false, label: '',
                 pending: false, expanded: new Set() };
    }

    activate(conv) {
        if (conv.id !== this.session.activeId) this.dropDraft();
        if (!this.session.convs.includes(conv)) this.session.convs.push(conv);
        this.session.activeId = conv.id;
        this.render();
    }

    /** Leaving an unsent counterfactual discards it. */
    dropDraft() {
        this.session.convs = this.session.convs.filter(c => !c.draft);
        if (!this.conv) this.session.activeId = this.session.convs[0].id;
    }

    newConversation() {
        const conv = this.makeConv('fresh');
        this.dropDraft();
        conv.index = this.session.nextIndex++;
        window.studyTimer?.logEvent('chat_new_conversation');
        this.activate(conv);
    }

    askCounterfactual() {
        if (!this.item) return;
        const conv = this.makeConv('counterfactual');
        conv.draft = true;
        conv.cf = { question: this.item.question, options: { ...this.item.options } };
        this.activate(conv);
    }

    // ---------- counterfactual edits ----------

    cfChanges(cf) {
        const out = [];
        const q = diffHunks(wordDiff(this.item.question, cf.question));
        q.forEach(h => out.push({ where: null, ...h }));
        Object.keys(this.item.options).sort().forEach(k => {
            diffHunks(wordDiff(this.item.options[k], cf.options[k]))
                .forEach(h => out.push({ where: k, ...h }));
        });
        return out;
    }

    cfLabel(cf) {
        const changes = this.cfChanges(cf);
        if (!changes.length) return 'no edits';
        const c = changes[0];
        const cut = s => s.length > 24 ? s.slice(0, 23) + '…' : s;
        let text = c.del && c.add ? `${cut(c.del)} → ${cut(c.add)}` : c.add ? `+ ${cut(c.add)}` : `− ${cut(c.del)}`;
        if (c.where) text = `${c.where}: ${text}`;
        return changes.length > 1 ? `${text} (+${changes.length - 1} more)` : text;
    }

    /** Inline diff markup (removed struck through in red, added in green). */
    diffHtml(a, b) {
        return wordDiff(a, b).map(op => op.type === 'same' ? this.escapeHtml(op.text)
            : `<${op.type === 'del' ? 'del' : 'ins'} class="cf-${op.type}">${this.escapeHtml(op.text)}</${op.type === 'del' ? 'del' : 'ins'}>`).join('');
    }

    cfDiffHtml(cf) {
        const parts = [];
        if (cf.question !== this.item.question) parts.push(`<p>${this.diffHtml(this.item.question, cf.question)}</p>`);
        Object.keys(this.item.options).sort().forEach(k => {
            if (cf.options[k] !== this.item.options[k])
                parts.push(`<p>${k}. ${this.diffHtml(this.item.options[k], cf.options[k])}</p>`);
        });
        return parts.join('') || '<p class="text-gray-400">No changes: the original question will be asked again.</p>';
    }

    // ---------- rendering ----------

    sidebarLabel(c) {
        if (c.kind === 'original') return 'Original';
        if (c.draft) return 'Counterfactual (editing)';
        return c.kind === 'counterfactual' ? `${c.index} · CF: ${c.label}` : `${c.index}`;
    }

    render() {
        if (!this.container || !this.session) return;
        const conv = this.conv;
        const convs = [this.session.convs[0], ...this.session.convs.slice(1).reverse()];  // Original, then newest first
        const spinner = '<span class="loading-spinner cf-mini-spinner"></span>';
        const sidebar = convs.map(c => `
            <button type="button" class="chat-conv ${c.id === conv.id ? 'active' : ''}" data-conv="${c.id}"
                    title="${this.escapeHtml(this.sidebarLabel(c))}">
                <span class="truncate">${this.escapeHtml(this.sidebarLabel(c))}</span>${c.pending ? spinner : ''}
            </button>`).join('');
        const dropdown = convs.map(c =>
            `<option value="${c.id}" ${c.id === conv.id ? 'selected' : ''}>${this.escapeHtml(this.sidebarLabel(c))}${c.pending ? ' …' : ''}</option>`).join('');

        this.container.innerHTML = `
            <div class="flex justify-between items-center mb-3 gap-3">
                <h2 class="text-lg font-semibold text-gray-800">Conversation</h2>
                <div class="flex gap-4">
                    <button id="chat-new-btn" class="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-40" ${this.isLoading ? 'disabled' : ''}>
                        New conversation
                    </button>
                    <button id="chat-cf-btn" class="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-40" ${this.isLoading || !this.item ? 'disabled' : ''}
                            title="Edit the question and ask it again in a new conversation">
                        Ask counterfactual
                    </button>
                </div>
            </div>
            <div class="chat-body">
                <aside class="chat-sidebar">${sidebar}</aside>
                <div class="chat-main">
                    <select id="chat-conv-select" class="chat-conv-select">${dropdown}</select>
                    ${conv.draft ? this.editorHtml(conv) : this.conversationHtml(conv)}
                </div>
            </div>
        `;

        this.container.querySelectorAll('.chat-conv').forEach(b => b.addEventListener('click', () =>
            this.activate(this.session.convs.find(c => c.id === b.dataset.conv))));
        document.getElementById('chat-conv-select')?.addEventListener('change', e =>
            this.activate(this.session.convs.find(c => c.id === e.target.value)));
        document.getElementById('chat-new-btn')?.addEventListener('click', () => this.newConversation());
        document.getElementById('chat-cf-btn')?.addEventListener('click', () => this.askCounterfactual());
        if (conv.draft) this.attachEditor(conv); else this.attachConversation(conv);
    }

    conversationHtml(conv) {
        const bubble = (m, idx) => {
            let text = this.escapeHtml(m.content);
            let more = '';
            if (conv.kind === 'counterfactual' && idx === 0) {
                text = conv.expanded.has(0) ? text
                    : `<span class="block text-xs font-semibold uppercase tracking-wide opacity-70 mb-1">Counterfactual question</span>${this.cfDiffHtml(conv.cf)}`;
                more = `<button data-expand="0" class="chat-expand block mt-1 text-xs underline opacity-80">${conv.expanded.has(0) ? 'show changes only' : 'show full question'}</button>`;
            } else if (idx < conv.seedLength && !conv.expanded.has(idx) && m.content.length > PREVIEW) {
                text = this.escapeHtml(m.content.slice(0, PREVIEW)) + '…';
                more = `<button data-expand="${idx}" class="chat-expand block mt-1 text-xs underline opacity-80">show full ${m.role === 'user' ? 'question' : 'response'}</button>`;
            }
            const who = m.role === 'user' ? 'You' : 'Model';
            return `
                <div class="chat-row ${m.role}">
                    <div class="text-xs text-gray-400 mb-1 ${m.role === 'user' ? 'text-right' : ''}">${who}</div>
                    <div class="chat-message ${m.role} ${conv.kind === 'counterfactual' && idx === 0 && !conv.expanded.has(0) ? '' : 'whitespace-pre-wrap'}">${text}${more}</div>
                </div>`;
        };
        const empty = conv.messages.length ? '' : `
            <div class="text-center text-gray-400 text-sm py-8">
                New conversation: the model has no prior context.
            </div>`;
        const full = conv.messages.filter(m => m.role === 'user').length >= MAX_TURNS;
        const placeholder = full ? 'Message limit reached. Start a new conversation.'
                                 : 'Continue the conversation. Enter to send, Shift+Enter for a new line';
        return `
            <div class="chat-container">
                <div class="chat-messages" id="chat-messages">
                    ${empty}
                    ${conv.messages.map(bubble).join('')}
                    ${conv.pending ? '<div class="chat-row assistant"><div class="chat-message assistant"><span class="loading-spinner"></span></div></div>' : ''}
                </div>
                <div class="chat-input-container">
                    <textarea id="chat-input" rows="2" class="chat-input resize-y"
                              placeholder="${placeholder}" ${full ? 'disabled' : ''}></textarea>
                    <button id="chat-send-btn" class="chat-send-btn" ${this.isLoading || full ? 'disabled' : ''}>Send</button>
                </div>
            </div>`;
    }

    attachConversation(conv) {
        const input = document.getElementById('chat-input');
        input?.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        document.getElementById('chat-send-btn')?.addEventListener('click', () => this.sendMessage());
        this.container.querySelectorAll('.chat-expand').forEach(b => b.addEventListener('click', () => {
            const idx = Number(b.dataset.expand);
            if (conv.expanded.has(idx)) conv.expanded.delete(idx); else conv.expanded.add(idx);
            this.render();
        }));
        if (conv.messages.length > conv.seedLength) this.scrollToBottom();
    }

    editorHtml(conv) {
        const letters = Object.keys(this.item.options).sort();
        return `
            <div class="cf-editor">
                <p class="text-sm text-gray-500 mb-3">Edit the question or the answer options, then send.</p>
                <label class="cf-label" for="cf-question">Medical question</label>
                <textarea id="cf-question" class="cf-question" rows="7">${this.escapeHtml(conv.cf.question)}</textarea>
                <p class="cf-label mt-3">Answer options</p>
                <div class="space-y-2">
                    ${letters.map(k => `
                        <div class="cf-option-row">
                            <span class="font-medium text-gray-600">${k}.</span>
                            <input type="text" class="cf-option" data-letter="${k}" value="${this.escapeHtml(conv.cf.options[k])}">
                        </div>`).join('')}
                </div>
                <div class="cf-diff-box">
                    <p class="cf-label">Changes</p>
                    <div id="cf-diff" class="cf-diff">${this.cfDiffHtml(conv.cf)}</div>
                </div>
                <p id="cf-error" class="text-sm text-red-600 mt-2"></p>
                <div class="flex justify-between items-center mt-3">
                    <button type="button" id="cf-reset" class="text-sm text-gray-500 hover:text-gray-800 underline">Reset to original</button>
                    <button type="button" id="cf-send" class="chat-send-btn" ${this.isLoading ? 'disabled' : ''}>Send</button>
                </div>
            </div>`;
    }

    attachEditor(conv) {
        const refresh = () => {
            document.getElementById('cf-diff').innerHTML = this.cfDiffHtml(conv.cf);
            document.getElementById('cf-error').textContent = '';
        };
        document.getElementById('cf-question').addEventListener('input', e => {
            conv.cf.question = e.target.value;
            refresh();
        });
        this.container.querySelectorAll('.cf-option').forEach(el => el.addEventListener('input', () => {
            conv.cf.options[el.dataset.letter] = el.value;
            refresh();
        }));
        document.getElementById('cf-reset').addEventListener('click', () => {
            conv.cf = { question: this.item.question, options: { ...this.item.options } };
            this.render();
        });
        document.getElementById('cf-send').addEventListener('click', () => this.sendCounterfactual(conv));
    }

    // ---------- sending ----------

    async sendCounterfactual(conv) {
        if (this.isLoading) return;
        if (!conv.cf.question.trim() || Object.values(conv.cf.options).some(v => !v.trim())) {
            document.getElementById('cf-error').textContent = 'The question and every answer option must be filled in.';
            return;
        }
        conv.draft = false;
        conv.index = this.session.nextIndex++;
        conv.label = this.cfLabel(conv.cf);
        conv.messages = [{ role: 'user', content: '' }];  // the server builds the templated prompt
        const ok = await this.request(conv);
        if (!ok && conv.messages.length === 0) {           // first turn failed: back to the editor
            conv.draft = true;
            this.session.nextIndex = conv.index;
            conv.index = null;
            if (this.conv !== conv) this.dropDraft();      // ... unless they already moved on
            this.render();
        }
    }

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input?.value.trim();
        const conv = this.conv;
        if (!message || this.isLoading || !conv) return;
        conv.messages.push({ role: 'user', content: message });
        window.studyTimer?.logEvent('chat_message_sent', { message_length: message.length });
        if (!await this.request(conv) && this.conv === conv) {
            document.getElementById('chat-input').value = message;
        }
    }

    /** Send `conv` and append the reply; it lands in `conv` even if another is open by then. */
    async request(conv) {
        this.isLoading = true;
        conv.pending = true;
        this.render();
        let ok = true;
        try {
            const res = await window.API.chatWithModel(this.batch, this.itemId, conv.messages, {
                conversation_id: conv.id, conversation_index: conv.index, kind: conv.kind,
                ...(conv.kind === 'counterfactual' ? { cf: conv.cf } : {}),
            });
            if (conv.kind === 'counterfactual' && res.prompt) conv.messages[0].content = res.prompt;
            conv.messages.push({ role: 'assistant', content: res.response });
        } catch (error) {
            conv.messages.pop();  // keep the history valid for the next attempt
            alert(error.message);
            ok = false;
        }
        this.isLoading = false;
        conv.pending = false;
        this.render();
        return ok;
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
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML.replace(/"/g, '&quot;');
    }
}

const chatInterface = new ChatInterfaceModule('#chat-panel');
window.ChatInterfaceModule = ChatInterfaceModule;
window.chatInterface = chatInterface;
