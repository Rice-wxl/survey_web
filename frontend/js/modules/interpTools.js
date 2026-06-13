/**
 * Interpretability Tools Module
 * Renders various interpretability visualizations.
 * Designed to be extensible for different tool types.
 */

class InterpToolsModule {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.currentTool = null;
        this.currentData = null;
        this.isVisible = true;
        
        // Registry of visualization renderers
        this.renderers = {
            'token_highlight': this.renderTokenHighlight.bind(this),
            'heatmap': this.renderHeatmap.bind(this),
            'bar_chart': this.renderBarChart.bind(this),
            // Add more renderers as needed
        };
    }
    
    /**
     * Set the container element.
     */
    setContainer(containerSelector) {
        this.container = document.querySelector(containerSelector);
    }
    
    /**
     * Render interpretability results.
     */
    render(toolName, displayName, data) {
        if (!this.container) {
            console.error('Interp tools container not found');
            return;
        }
        
        this.currentTool = toolName;
        this.currentData = data;
        
        const visualizationType = data.visualization_type || 'token_highlight';
        const renderer = this.renderers[visualizationType];
        
        if (!renderer) {
            console.error(`Unknown visualization type: ${visualizationType}`);
            return;
        }
        
        // Build header
        const headerHtml = `
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-lg font-semibold text-gray-800 flex items-center gap-2">
                    <svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    ${this.escapeHtml(displayName)}
                </h2>
                <button id="btn-toggle-interp" class="text-sm text-blue-600 hover:text-blue-800">
                    ${this.isVisible ? 'Hide' : 'Show'}
                </button>
            </div>
        `;
        
        // Build visualization
        const vizHtml = this.isVisible ? renderer(data) : '<p class="text-gray-500 text-sm">Click "Show" to view the visualization.</p>';
        
        this.container.innerHTML = headerHtml + `<div id="interp-viz-content">${vizHtml}</div>`;
        
        // Attach toggle handler
        document.getElementById('btn-toggle-interp')?.addEventListener('click', () => {
            this.toggleVisibility();
        });
        
        // Attach token hover handlers if applicable
        if (visualizationType === 'token_highlight' && this.isVisible) {
            this.attachTokenHoverHandlers();
        }
        
        // Log tool view event
        window.studyTimer?.logEvent('interp_tool_viewed', {
            tool: toolName,
            visualization_type: visualizationType
        });
    }
    
    /**
     * Render token highlight visualization.
     */
    renderTokenHighlight(data) {
        const { tokens, attributions, method } = data;
        
        if (!tokens || !attributions) {
            return '<p class="text-red-500">Invalid data for token visualization.</p>';
        }
        
        // Generate token HTML
        const tokensHtml = tokens.map((token, idx) => {
            const score = attributions[idx] || 0;
            const bgColor = this.getAttributionColor(score);
            const textColor = score > 0.5 ? 'white' : 'black';
            
            return `
                <span class="token-attribution" 
                      data-score="${score.toFixed(3)}"
                      data-index="${idx}"
                      style="background-color: ${bgColor}; color: ${textColor};">
                    ${this.escapeHtml(token)}
                </span>
            `;
        }).join('');
        
        // Legend
        const legendHtml = `
            <div class="flex items-center gap-4 mt-4 text-sm">
                <span class="text-gray-500">Attribution:</span>
                <div class="flex items-center gap-1">
                    <div class="w-4 h-4 rounded" style="background-color: rgba(59, 130, 246, 0.1)"></div>
                    <span>Low</span>
                </div>
                <div class="flex items-center gap-1">
                    <div class="w-4 h-4 rounded" style="background-color: rgba(59, 130, 246, 0.5)"></div>
                    <span>Medium</span>
                </div>
                <div class="flex items-center gap-1">
                    <div class="w-4 h-4 rounded" style="background-color: rgba(59, 130, 246, 0.9)"></div>
                    <span>High</span>
                </div>
            </div>
        `;
        
        return `
            <p class="text-sm text-gray-500 mb-3">
                Highlighted tokens show their influence on the model's prediction. 
                Hover for exact scores. Method: <strong>${method}</strong>
            </p>
            <div class="bg-gray-50 p-4 rounded-lg">
                <div class="flex flex-wrap gap-1" id="token-container">
                    ${tokensHtml}
                </div>
            </div>
            ${legendHtml}
        `;
    }
    
    /**
     * Render heatmap visualization (placeholder for future implementation).
     */
    renderHeatmap(data) {
        return `
            <p class="text-gray-500">Heatmap visualization coming soon.</p>
            <pre class="text-xs bg-gray-100 p-2 rounded mt-2">${JSON.stringify(data, null, 2)}</pre>
        `;
    }
    
    /**
     * Render bar chart visualization (placeholder for future implementation).
     */
    renderBarChart(data) {
        return `
            <p class="text-gray-500">Bar chart visualization coming soon.</p>
            <pre class="text-xs bg-gray-100 p-2 rounded mt-2">${JSON.stringify(data, null, 2)}</pre>
        `;
    }
    
    /**
     * Get color for attribution score (0-1).
     */
    getAttributionColor(score) {
        // Blue gradient
        const alpha = 0.1 + (score * 0.8);
        return `rgba(59, 130, 246, ${alpha})`;
    }
    
    /**
     * Attach hover handlers for token tooltips.
     */
    attachTokenHoverHandlers() {
        const tokens = document.querySelectorAll('.token-attribution');
        
        tokens.forEach(token => {
            token.addEventListener('mouseenter', (e) => {
                const score = e.target.dataset.score;
                const percentage = (parseFloat(score) * 100).toFixed(1);
                
                // Create tooltip
                const tooltip = document.createElement('div');
                tooltip.className = 'token-tooltip';
                tooltip.textContent = `Attribution: ${percentage}%`;
                tooltip.id = 'token-tooltip';
                
                // Position tooltip
                const rect = e.target.getBoundingClientRect();
                tooltip.style.left = `${rect.left + rect.width / 2}px`;
                tooltip.style.top = `${rect.top - 8}px`;
                tooltip.style.transform = 'translate(-50%, -100%)';
                
                document.body.appendChild(tooltip);
                
                // Log interaction
                window.studyTimer?.logEvent('token_hover', {
                    token: e.target.textContent,
                    score: score,
                    index: e.target.dataset.index
                });
            });
            
            token.addEventListener('mouseleave', () => {
                const tooltip = document.getElementById('token-tooltip');
                if (tooltip) tooltip.remove();
            });
        });
    }
    
    /**
     * Toggle visualization visibility.
     */
    toggleVisibility() {
        this.isVisible = !this.isVisible;
        
        if (this.currentTool && this.currentData) {
            this.render(this.currentTool, this.currentData.display_name || this.currentTool, this.currentData);
        }
        
        // Log toggle event
        window.studyTimer?.logEvent('interp_tool_toggle', {
            tool: this.currentTool,
            visible: this.isVisible
        });
    }
    
    /**
     * Show loading state.
     */
    showLoading() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <h2 class="text-lg font-semibold text-gray-800 mb-4">Interpretability Analysis</h2>
            <div class="flex items-center gap-3">
                <div class="loading-spinner"></div>
                <span class="text-gray-600">Computing analysis...</span>
            </div>
        `;
    }
    
    /**
     * Show error state.
     */
    showError(message) {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <h2 class="text-lg font-semibold text-gray-800 mb-4">Interpretability Analysis</h2>
            <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                <p class="font-medium">Error loading analysis</p>
                <p class="text-sm">${this.escapeHtml(message)}</p>
            </div>
        `;
    }
    
    /**
     * Clear the display.
     */
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.currentTool = null;
        this.currentData = null;
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
const interpTools = new InterpToolsModule('#interp-tool-panel');

// Make globally available
window.InterpToolsModule = InterpToolsModule;
window.interpTools = interpTools;
