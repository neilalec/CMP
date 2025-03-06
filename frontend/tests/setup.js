// No need to import jest - it's already global
// Mock environment variables
Object.defineProperty(window, '__ENV__', {
    value: {
        VITE_SOCKET_URL: 'http://localhost:5000'
    }
});

// Mock localStorage
const localStorageMock = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    clear: jest.fn(),
    removeItem: jest.fn()
};
Object.defineProperty(window, 'localStorage', {
    value: localStorageMock
});

// Mock WebSocket
const mockWebSocket = jest.fn(() => ({
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    send: jest.fn(),
    close: jest.fn()
}));
Object.defineProperty(window, 'WebSocket', {
    value: mockWebSocket
});

// Add to existing setup.js
process.env.VITE_SOCKET_URL = 'http://localhost:5000'; 