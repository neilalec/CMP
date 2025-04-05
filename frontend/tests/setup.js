// Mock environment variables
Object.defineProperty(window, '__ENV__', {
    value: {
        VITE_SOCKET_URL: 'http://localhost:5000'
    }
});

// Mock localStorage with state management
const localStorageMock = (() => {
    let store = {};
    return {
        getItem: jest.fn(key => store[key] || null),
        setItem: jest.fn((key, value) => {
            store[key] = value.toString();  // Ensure string storage
        }),
        removeItem: jest.fn(key => {
            delete store[key];
        }),
        clear: jest.fn(() => {
            store = {};
        }),
        _store: store  // For testing purposes
    };
})();

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

process.env.VITE_SOCKET_URL = 'http://localhost:5000'; 