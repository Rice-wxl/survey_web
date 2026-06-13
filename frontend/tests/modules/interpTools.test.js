/**
 * Unit tests for the Interpretability Tools module (interpTools.js).
 *
 * Tests cover:
 * - Token highlight rendering
 * - Color calculation
 * - Visualization toggling
 * - Loading and error states
 * - Event logging
 */

// Load dependencies
const fs = require('fs');
const path = require('path');

// Mock studyTimer
window.studyTimer = {
    logEvent: jest.fn()
};

// Load the interp tools module
const moduleCode = fs.readFileSync(
    path.join(__dirname, '../../js/modules/interpTools.js'),
    'utf8'
);
eval(moduleCode);

describe('InterpToolsModule', () => {
    let module;
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'interp-tool-panel';
        document.body.appendChild(container);

        module = new InterpToolsModule('#interp-tool-panel');
        window.studyTimer.logEvent.mockClear();
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
         * Tests that visibility defaults to true.
         */
        test('should initialize with isVisible true', () => {
            expect(module.isVisible).toBe(true);
        });

        /**
         * Tests that renderers are registered.
         */
        test('should have renderers for token_highlight, heatmap, bar_chart', () => {
            expect(module.renderers['token_highlight']).toBeDefined();
            expect(module.renderers['heatmap']).toBeDefined();
            expect(module.renderers['bar_chart']).toBeDefined();
        });
    });

    describe('render method', () => {
        const sampleData = {
            tokens: ['The', 'patient', 'has', 'symptoms'],
            attributions: [0.1, 0.8, 0.2, 0.9],
            method: 'gradient',
            visualization_type: 'token_highlight'
        };

        /**
         * Tests that render displays tool name.
         */
        test('should display tool display name', () => {
            module.render('mock_tool', 'Mock Tool', sampleData);

            expect(container.textContent).toContain('Mock Tool');
        });

        /**
         * Tests that render stores current tool.
         */
        test('should store currentTool', () => {
            module.render('mock_tool', 'Mock Tool', sampleData);

            expect(module.currentTool).toBe('mock_tool');
        });

        /**
         * Tests that render stores current data.
         */
        test('should store currentData', () => {
            module.render('mock_tool', 'Mock Tool', sampleData);

            expect(module.currentData).toBe(sampleData);
        });

        /**
         * Tests that render logs view event.
         */
        test('should log interp_tool_viewed event', () => {
            module.render('mock_tool', 'Mock Tool', sampleData);

            expect(window.studyTimer.logEvent).toHaveBeenCalledWith(
                'interp_tool_viewed',
                expect.objectContaining({
                    tool: 'mock_tool',
                    visualization_type: 'token_highlight'
                })
            );
        });

        /**
         * Tests that render includes toggle button.
         */
        test('should include toggle button', () => {
            module.render('mock_tool', 'Mock Tool', sampleData);

            const toggleBtn = container.querySelector('#btn-toggle-interp');
            expect(toggleBtn).not.toBeNull();
        });

        /**
         * Tests that toggle button shows "Hide" when visible.
         */
        test('should show "Hide" button when visible', () => {
            module.isVisible = true;
            module.render('mock_tool', 'Mock Tool', sampleData);

            const toggleBtn = container.querySelector('#btn-toggle-interp');
            expect(toggleBtn.textContent.trim()).toBe('Hide');
        });
    });

    describe('renderTokenHighlight method', () => {
        const tokenData = {
            tokens: ['word1', 'word2', 'word3'],
            attributions: [0.1, 0.5, 0.9],
            method: 'gradient'
        };

        /**
         * Tests that tokens are rendered.
         */
        test('should render all tokens', () => {
            const html = module.renderTokenHighlight(tokenData);

            expect(html).toContain('word1');
            expect(html).toContain('word2');
            expect(html).toContain('word3');
        });

        /**
         * Tests that tokens have data-score attribute.
         */
        test('should include data-score attributes', () => {
            const html = module.renderTokenHighlight(tokenData);

            expect(html).toContain('data-score="0.100"');
            expect(html).toContain('data-score="0.500"');
            expect(html).toContain('data-score="0.900"');
        });

        /**
         * Tests that method is displayed.
         */
        test('should display attribution method', () => {
            const html = module.renderTokenHighlight(tokenData);

            expect(html).toContain('gradient');
        });

        /**
         * Tests that legend is included.
         */
        test('should include legend', () => {
            const html = module.renderTokenHighlight(tokenData);

            expect(html).toContain('Low');
            expect(html).toContain('Medium');
            expect(html).toContain('High');
        });

        /**
         * Tests that invalid data returns error message.
         */
        test('should return error for invalid data', () => {
            const html = module.renderTokenHighlight({});

            expect(html).toContain('Invalid data');
        });
    });

    describe('getAttributionColor method', () => {
        /**
         * Tests that score 0 produces low alpha.
         */
        test('should return low alpha for score 0', () => {
            const color = module.getAttributionColor(0);

            // Should contain low alpha value
            expect(color).toContain('rgba(59, 130, 246,');
            expect(color).toContain('0.1');
        });

        /**
         * Tests that score 1 produces high alpha.
         */
        test('should return high alpha for score 1', () => {
            const color = module.getAttributionColor(1);

            expect(color).toContain('rgba(59, 130, 246,');
            expect(color).toContain('0.9');
        });

        /**
         * Tests that score 0.5 produces medium alpha.
         */
        test('should return medium alpha for score 0.5', () => {
            const color = module.getAttributionColor(0.5);

            expect(color).toContain('rgba(59, 130, 246,');
            expect(color).toContain('0.5');
        });
    });

    describe('toggleVisibility method', () => {
        const sampleData = {
            tokens: ['test'],
            attributions: [0.5],
            method: 'test',
            visualization_type: 'token_highlight'
        };

        /**
         * Tests that toggle changes visibility state.
         */
        test('should toggle isVisible', () => {
            module.isVisible = true;
            module.currentTool = 'mock_tool';
            module.currentData = sampleData;

            module.toggleVisibility();

            expect(module.isVisible).toBe(false);
        });

        /**
         * Tests that toggle logs event.
         */
        test('should log toggle event', () => {
            module.currentTool = 'mock_tool';
            module.currentData = sampleData;

            module.toggleVisibility();

            expect(window.studyTimer.logEvent).toHaveBeenCalledWith(
                'interp_tool_toggle',
                expect.objectContaining({
                    tool: 'mock_tool'
                })
            );
        });
    });

    describe('showLoading method', () => {
        /**
         * Tests that loading state is displayed.
         */
        test('should display loading UI', () => {
            module.showLoading();

            expect(container.innerHTML).toContain('loading-spinner');
            expect(container.textContent).toContain('Computing');
        });
    });

    describe('showError method', () => {
        /**
         * Tests that error message is displayed.
         */
        test('should display error message', () => {
            module.showError('Something went wrong');

            expect(container.textContent).toContain('Error loading analysis');
            expect(container.textContent).toContain('Something went wrong');
        });

        /**
         * Tests that error message is escaped.
         */
        test('should escape error message', () => {
            module.showError('<script>alert(1)</script>');

            expect(container.innerHTML).not.toContain('<script>');
        });
    });

    describe('clear method', () => {
        /**
         * Tests that clear resets state.
         */
        test('should reset state', () => {
            module.currentTool = 'test';
            module.currentData = { data: 'test' };

            module.clear();

            expect(module.currentTool).toBeNull();
            expect(module.currentData).toBeNull();
        });

        /**
         * Tests that clear empties container.
         */
        test('should empty container', () => {
            container.innerHTML = '<div>Content</div>';
            module.clear();

            expect(container.innerHTML).toBe('');
        });
    });

    describe('escapeHtml method', () => {
        /**
         * Tests XSS prevention.
         */
        test('should escape HTML', () => {
            const result = module.escapeHtml('<b>bold</b>');

            expect(result).not.toContain('<b>');
        });
    });

    describe('renderHeatmap method (placeholder)', () => {
        /**
         * Tests that heatmap shows placeholder message.
         */
        test('should show placeholder message', () => {
            const html = module.renderHeatmap({ data: 'test' });

            expect(html).toContain('coming soon');
        });
    });

    describe('renderBarChart method (placeholder)', () => {
        /**
         * Tests that bar chart shows placeholder message.
         */
        test('should show placeholder message', () => {
            const html = module.renderBarChart({ data: 'test' });

            expect(html).toContain('coming soon');
        });
    });
});

describe('Singleton Instance (interpTools)', () => {
    /**
     * Tests that global singleton exists.
     */
    test('should export interpTools singleton', () => {
        expect(interpTools).toBeDefined();
        expect(interpTools).toBeInstanceOf(InterpToolsModule);
    });
});
