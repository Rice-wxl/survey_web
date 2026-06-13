/**
 * Jest setup file for frontend tests.
 *
 * This file runs before each test file and sets up the testing environment.
 * It provides:
 * - DOM mocking utilities
 * - Global window object setup
 * - Common test helpers
 */

// Mock fetch API for API tests
global.fetch = jest.fn();

// Mock window.location
delete window.location;
window.location = {
    origin: 'http://localhost:5000',
    href: 'http://localhost:5000/',
    pathname: '/',
    reload: jest.fn()
};

// Mock localStorage (store reference to check if mocking is needed)
const localStorageMock = {
    store: {},
    getItem: jest.fn((key) => localStorageMock.store[key] || null),
    setItem: jest.fn((key, value) => { localStorageMock.store[key] = value; }),
    removeItem: jest.fn((key) => { delete localStorageMock.store[key]; }),
    clear: jest.fn(() => { localStorageMock.store = {}; })
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock console methods for cleaner test output (optional)
// Uncomment to suppress console output during tests
// global.console = {
//     ...console,
//     log: jest.fn(),
//     warn: jest.fn(),
//     error: jest.fn()
// };

// Helper to reset all mocks between tests
beforeEach(() => {
    fetch.mockClear();
    localStorage.getItem.mockClear();
    localStorage.setItem.mockClear();
    document.body.innerHTML = '';
});

// Helper function to create a mock successful fetch response
global.mockFetchSuccess = (data) => {
    fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(data)
    });
};

// Helper function to create a mock failed fetch response
global.mockFetchError = (status, errorData) => {
    fetch.mockResolvedValueOnce({
        ok: false,
        status: status,
        json: () => Promise.resolve(errorData || { error: 'Error' })
    });
};

// Helper function to create a mock network error
global.mockFetchNetworkError = (errorMessage) => {
    fetch.mockRejectedValueOnce(new Error(errorMessage || 'Network error'));
};

// Helper to wait for all promises to resolve
global.flushPromises = () => new Promise(resolve => setImmediate(resolve));

// Helper to simulate a delay
global.delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
