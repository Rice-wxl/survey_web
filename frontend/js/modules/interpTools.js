/**
 * Interpretability readouts panel (precomputed J-lens / SAE).
 *
 * Content is exactly what the LLM auditor saw (same spans, depths, top-k, filters, rank
 * order only -- no scores); only the presentation differs.
 * One tool at a time, picked by the app's right-column tab, so the prototype's per-tool
 * tabs render exactly the real-mode panel.
 */

const TOOL_INFO = {
    jlens: {
        name: 'J-lens',
        blurb: 'Words the model is internally "thinking" while it reads the question ' +
               'or gives its response, at different depths of processing. ' +
               'Each row is ranked: leftmost = strongest.',
    },
    sae: {
        name: 'SAE features',
        blurb: 'Abstract concepts the model is internally "thinking" while it reads the question ' +
               'or gives its response. Top-25 are shown, ranked: top = strongest.',
    },
};

class InterpToolsModule {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.readouts = {};
        this.tool = null;
        this.span = 'question';
        this.saeSource = 'activation';   // free mode: 'activation' | 'tfidf' | 'mean' (gradient)
        this.saeLabels = 'middle';       // free mode: 'middle' | 'original' explainer-prompt labels
    }

    setContainer(containerSelector) {
        this.container = document.querySelector(containerSelector);
    }

    /** @param readouts {jlens?: {question, reasoning}, sae?: {question, reasoning}} */
    render(readouts) {
        this.readouts = readouts || {};
        this.pinned = null;
        this.tool = null;
    }

    show(tool) {
        this.tool = tool;
        this.draw();
    }

    draw() {
        if (!this.container || !this.tool) return;
        const pill = (attr, value, label, on) => `
            <button data-${attr}="${value}" class="interp-${attr} px-3 py-1
                ${on ? 'bg-indigo-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}">${label}</button>`;
        const spanToggle = `
            <div class="inline-flex rounded-lg border overflow-hidden mb-3 text-sm">
                ${[['question', 'While reading the question'], ['reasoning', 'While giving the response']].map(([s, label]) => pill('span', s, label, s === this.span)).join('')}
            </div>`;
        // Free mode also ships the original-prompt SAE labels (same features, older text);
        // offer them as a label switch.
        const hasOrig = this.tool === 'sae' && Object.keys(this.readouts.sae_orig || {}).length > 0;
        const orig = hasOrig && this.saeLabels === 'original';
        const labelToggle = hasOrig ? `
            <div class="inline-flex rounded-lg border overflow-hidden mb-3 ml-2 text-sm">
                ${[['middle', 'Middle-ground labels'], ['original', 'Original-prompt labels']].map(([k, label]) => pill('labels', k, label, k === this.saeLabels)).join('')}
            </div>` : '';
        // Free mode ships gradient-ranked SAE panels too; offer them as a source toggle.
        const grad = this.tool === 'sae' ? ((orig ? this.readouts.sae_grad_orig : this.readouts.sae_grad) || {}) : {};
        const tfidf = this.tool === 'sae' ? ((orig ? this.readouts.sae_tfidf_orig : this.readouts.sae_tfidf) || {}) : {};
        // Gradient = vs the mean of the other options; the vs-best variant stays on disk only.
        const sources = [['activation', 'Activation'], ['tfidf', 'TF-IDF'], ['mean', 'Gradient']]
            .filter(([k]) => k === 'activation' || (k === 'tfidf' ? tfidf.question : grad[k]));
        if (!sources.some(([k]) => k === this.saeSource)) this.saeSource = 'activation';
        const sourceToggle = sources.length > 1 ? `
            <div class="inline-flex rounded-lg border overflow-hidden mb-3 ml-2 text-sm">
                ${sources.map(([k, label]) => pill('source', k, label, k === this.saeSource)).join('')}
            </div>` : '';
        const data = this.tool === 'sae' && this.saeSource === 'tfidf' ? tfidf[this.span]
            : this.tool === 'sae' && this.saeSource !== 'activation'
            ? grad[this.saeSource][this.span]
            : (orig ? this.readouts.sae_orig : this.readouts[this.tool])[this.span];
        const body = this.tool === 'jlens' ? this.renderJlens(data) : this.renderSae(data);

        this.container.innerHTML = `
            <h2 class="text-lg font-semibold text-gray-800 mb-2">Extra panel</h2>
            <p class="text-sm text-gray-500 mb-3">${this.tool === 'sae' && this.saeSource === 'tfidf'
                ? 'SAE features ranked by average activation over the text, weighted by how rare the ' +
                  'feature is in ordinary clinical notes (TF-IDF): features that fire on any medical ' +
                  'text are pushed down. Ranked: top = highest score.'
                : this.tool === 'sae' && this.saeSource !== 'activation'
                ? 'SAE features ranked by how much they pushed the model toward the answer it chose, ' +
                  'over the average other option (gradient attribution). Ranked: top = largest push.'
                : TOOL_INFO[this.tool].blurb}</p>
            <div>${spanToggle}${sourceToggle}${labelToggle}</div>
            ${body}
        `;
        // Hover a token: light up the same token at every depth (recurrence spotting).
        // Click pins it, so the highlight survives scrolling / moving the mouse away; click
        // it again (or empty space in the grid) to unpin. A pin overrides hover.
        const grid = this.container.querySelector('.jl-grid');
        const light = tok => {
            if (!grid) return;   // SAE tab: no J-lens grid
            grid.classList.toggle('jl-hovering', !!tok);
            grid.querySelectorAll('.jl-tok').forEach(el => el.classList.toggle('jl-hit', el.dataset.tok === tok));
        };
        light(this.pinned);
        let unpinned = null;   // token just unpinned: don't re-light it until the mouse leaves it
        grid?.addEventListener('mouseover', e => {
            const tok = e.target.closest('.jl-tok')?.dataset.tok;
            if (tok !== unpinned) unpinned = null;
            if (!this.pinned && !unpinned) light(tok);
        });
        grid?.addEventListener('mouseleave', () => { unpinned = null; light(this.pinned); });
        grid?.addEventListener('click', e => {
            const tok = e.target.closest('.jl-tok')?.dataset.tok || null;
            unpinned = tok && tok === this.pinned ? tok : null;   // second click = clear now
            this.pinned = tok === this.pinned ? null : tok;
            window.studyTimer?.logEvent('jlens_pin', { tok: this.pinned });
            light(this.pinned);
        });
        this.container.querySelectorAll('.interp-span').forEach(b => b.addEventListener('click', () => {
            this.span = b.dataset.span;
            this.pinned = null;
            window.studyTimer?.logEvent('interp_span', { tool: this.tool, span: this.span });
            this.draw();
        }));
        this.container.querySelectorAll('.interp-source').forEach(b => b.addEventListener('click', () => {
            this.saeSource = b.dataset.source;
            window.studyTimer?.logEvent('interp_sae_source', { source: this.saeSource, span: this.span });
            this.draw();
        }));
        this.container.querySelectorAll('.interp-labels').forEach(b => b.addEventListener('click', () => {
            this.saeLabels = b.dataset.labels;
            window.studyTimer?.logEvent('interp_sae_labels', { labels: this.saeLabels, span: this.span });
            this.draw();
        }));
        this.afterDraw?.(this.container);   // tutorial pins its notes here
    }

    /** depths x ranked tokens grid. */
    renderJlens(depths) {
        // One row per depth, all (<=10) tokens on one line at this size; a genuinely long
        // row wraps rather than truncating.
        return `
            <div class="jl-grid text-sm">
                ${depths.map((toks, i) => `
                    <div class="flex items-center gap-2 py-1.5 border-b border-gray-100">
                        <div class="w-14 shrink-0 text-right text-xs text-gray-400">depth ${i + 1}</div>
                        <div class="flex flex-wrap gap-1 min-w-0">
                            ${toks.map((t, r) => `<span class="jl-tok cursor-pointer whitespace-nowrap px-1.5 py-0.5 rounded text-indigo-950 font-semibold"
                                data-tok="${this.escapeHtml(t.toLowerCase())}"
                                style="background: rgba(99, 102, 241, ${(0.42 - 0.025 * r).toFixed(3)})">${this.escapeHtml(t)}</span>`).join('')}
                        </div>
                    </div>`).join('')}
            </div>`;
    }

    /** ranked feature descriptions. */
    /** Numbered, rank-faded cards; first clause (to the first comma) as a bold headline. */
    renderSae(descriptions) {
        return `
            <ol class="space-y-2">
                ${descriptions.map((d, r) => {
                    const cut = d.indexOf(',');
                    const head = cut > 0 ? d.slice(0, cut + 1) : d;
                    const rest = cut > 0 ? d.slice(cut + 1) : '';
                    return `
                    <li class="flex gap-3 items-start p-3 rounded-lg border border-gray-100">
                        <span class="shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-sm font-semibold text-indigo-950"
                              style="background: rgba(99, 102, 241, ${Math.max(0.42 - 0.008 * r, 0.06).toFixed(3)})">${r + 1}</span>
                        <p class="text-base leading-relaxed">
                            <span class="font-semibold text-gray-900">${this.escapeHtml(head)}</span><span class="text-gray-600">${this.escapeHtml(rest)}</span>
                        </p>
                    </li>`;
                }).join('')}
            </ol>`;
    }

    showLoading() {
        if (!this.container) return;
        this.container.innerHTML = '<div class="loading-spinner"></div>';
    }

    showError(message) {
        if (!this.container) return;
        this.container.innerHTML = `<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">${this.escapeHtml(message)}</div>`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

const interpTools = new InterpToolsModule('#interp-tool-panel');
window.InterpToolsModule = InterpToolsModule;
window.interpTools = interpTools;
