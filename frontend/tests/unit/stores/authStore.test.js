import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '@/stores/authStore';

// Mock the socket service
jest.mock('@/services/socketService', () => ({
    socketService: {
        connect: jest.fn(),
        emit: jest.fn(),
        on: jest.fn(),
        off: jest.fn()
    }
}));

describe('AuthStore', () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        // Clear localStorage before each test
        localStorage.clear();
    });

    test('initial state', () => {
        const store = useAuthStore();
        expect(store.isLoggedIn).toBe(false);
        expect(store.token).toBeNull();
        expect(store.username).toBeNull();
    });

    test('login sets auth state', () => {
        const store = useAuthStore();
        const testData = {
            token: 'test-token',
            username: 'testuser'
        };
        
        store.login(testData);
        
        expect(store.isLoggedIn).toBe(true);
        expect(store.token).toBe('test-token');
        expect(store.username).toBe('testuser');
        expect(localStorage.getItem('token')).toBe('test-token');
        expect(localStorage.getItem('username')).toBe('testuser');
    });

    test('logout clears auth state', () => {
        const store = useAuthStore();
        store.login({
            token: 'test-token',
            username: 'testuser'
        });
        
        store.logout();
        
        expect(store.isLoggedIn).toBe(false);
        expect(store.token).toBeNull();
        expect(store.username).toBeNull();
        expect(localStorage.getItem('token')).toBeNull();
        expect(localStorage.getItem('username')).toBeNull();
    });

    test('restoreAuth from localStorage', () => {
        localStorage.setItem('token', 'saved-token');
        localStorage.setItem('username', 'saveduser');
        
        const store = useAuthStore();
        const result = store.restoreAuth();
        
        expect(result).toBe(true);
        expect(store.isLoggedIn).toBe(true);
        expect(store.token).toBe('saved-token');
        expect(store.username).toBe('saveduser');
    });

    test('restoreAuth returns false with no stored credentials', () => {
        const store = useAuthStore();
        const result = store.restoreAuth();
        
        expect(result).toBe(false);
        expect(store.isLoggedIn).toBe(false);
    });

    test('login and logout', () => {
        const store = useAuthStore();
        
        store.login({ token: 'test-token', username: 'test' });
        expect(store.isLoggedIn).toBe(true);
        expect(store.token).toBe('test-token');
        
        store.logout();
        expect(store.isLoggedIn).toBe(false);
        expect(store.token).toBeNull();
    });
}); 