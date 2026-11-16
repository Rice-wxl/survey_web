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
               'or gives its response. Top-20 are shown, ranked: top = strongest and most specific to ' +
               'this case (concepts that show up in any medical text are ranked lower).',
    },
};

// AttnLRP heatmap intensity = log(1 + K|v|) / log(1 + K), |v| in [0, 1] (strongest shown word = 1).
// Smooth and strictly monotone (no clipping); K lifts small values. On the 18 survey items:
// K=60 tints ~41% of vignette words visibly (linear: 3%; K=100: 54% and K=300: 84% were too
// crowded), and 0.22 vs 1.0 reads 0.65 vs 1.0.
const LRP_LOG_K = 60;

class InterpToolsModule {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.readouts = {};
        this.tool = null;
        this.span = 'question';
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
        if (this.tool === 'lrp') return this.drawLrp();
        const pill = (attr, value, label, on) => `
            <button data-${attr}="${value}" class="interp-${attr} px-3 py-1
                ${on ? 'bg-indigo-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}">${label}</button>`;
        const spanToggle = `
            <div class="inline-flex rounded-lg border overflow-hidden mb-3 text-sm">
                ${[['question', 'While reading the question'], ['reasoning', 'While giving the response']].map(([s, label]) => pill('span', s, label, s === this.span)).join('')}
            </div>`;
        // `sae` is the TF-IDF ranking with middle-ground labels in every mode (the tutorial
        // falls back to activation only if its TF-IDF list has not been built).
        const data = this.readouts[this.tool][this.span];
        const body = this.tool === 'jlens' ? this.renderJlens(data) : this.renderSae(data);

        this.container.innerHTML = `
            <h2 class="text-lg font-semibold text-gray-800 mb-2">Extra panel</h2>
            <p class="text-sm text-gray-500 mb-3">${TOOL_INFO[this.tool].blurb}</p>
            <div>${spanToggle}</div>
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
        this.afterDraw?.(this.container);   // tutorial pins its notes here
    }

    /**
     * AttnLRP word heatmap. Values are relevance normalized to [-1, 1] by the
     * largest |R| over the shown words: red = pushed toward the chosen answer, blue = away.
     * Letter labels are not attributed and stay uncolored.
     * Fixed on the MAX contrast (pick vs runner-up option) since 2026-11-05; the mean-contrast
     * comparison is frozen in spurious_detect/whitebox/results/lrp/max_vs_mean/.
     */
    drawLrp() {
        const d = (this.readouts.lrp || {}).max;
        if (!d) return;
        const word = ([w, v]) => {
            const a = Math.log1p(LRP_LOG_K * Math.min(Math.abs(v), 1)) / Math.log1p(LRP_LOG_K) * 0.8;
            const rgb = v >= 0 ? '220, 38, 38' : '37, 99, 235';
            return `<span class="lrp-w rounded px-0.5"
                style="background: rgba(${rgb}, ${a.toFixed(3)})">${this.escapeHtml(w)}</span>`;
        };
        const words = ws => ws.map(word).join(' ');
        this.container.innerHTML = `
            <h2 class="text-lg font-semibold text-gray-800 mb-2">Extra panel</h2>
            <p class="text-sm text-gray-500 mb-3">Which words in the question pushed the model toward the answer
                it selected. <span class="text-red-700 font-medium">Red</span> = pushed toward the chosen answer,
                <span class="text-blue-700 font-medium">blue</span> = pushed away; darker = stronger.</p>
            <p class="text-base leading-loose mb-4">${words(d.question)}</p>
            <div class="space-y-1 text-base leading-loose">
                ${Object.keys(d.options).sort().map(k => `
                    <div><span class="text-gray-500 font-medium">${k}.</span> ${words(d.options[k])}</div>`).join('')}
            </div>
        `;
        this.afterDraw?.(this.container);
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
