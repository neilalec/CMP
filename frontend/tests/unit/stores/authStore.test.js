import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore, isTokenExpired } from '@/stores/authStore';

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
    const createJwt = (payload) => {
        const encode = (value) => Buffer.from(JSON.stringify(value)).toString('base64url');
        return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.signature`;
    };

    beforeEach(() => {
        setActivePinia(createPinia());
        localStorage.clear();
    });

    test('initial state', () => {
        const store = useAuthStore();
        expect(store.isLoggedIn).toBe(false);
        expect(store.token).toBeNull();
        expect(store.username).toBeNull();
    });

    test('setAuth sets auth state', async () => {
        const store = useAuthStore();
        const testToken = 'test-token';
        const testUsername = 'testuser';
        
        await store.setAuth(testToken, testUsername);
        
        expect(store.isLoggedIn).toBe(true);
        expect(store.token).toBe(testToken);
        expect(store.username).toBe(testUsername);
        expect(localStorage.getItem('token')).toBe(testToken);
        expect(localStorage.getItem('username')).toBe(testUsername);
    });

    test('login sets auth state', async () => {
        const store = useAuthStore();
        const testToken = 'test-token';
        const testUsername = 'testuser';
        
        await store.login(testToken, testUsername);
        
        expect(store.isLoggedIn).toBe(true);
        expect(store.token).toBe(testToken);
        expect(store.username).toBe(testUsername);
        expect(localStorage.getItem('token')).toBe(testToken);
        expect(localStorage.getItem('username')).toBe(testUsername);
    });

    test('logout clears auth state', async () => {
        const store = useAuthStore();
        await store.setAuth('test-token', 'testuser');
        
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

    test('restoreAuth clears expired stored token', () => {
        const expiredToken = createJwt({ sub: 'saveduser', exp: Math.floor(Date.now() / 1000) - 60 });
        localStorage.setItem('token', expiredToken);
        localStorage.setItem('username', 'saveduser');

        const store = useAuthStore();
        const result = store.restoreAuth();

        expect(result).toBe(false);
        expect(store.isLoggedIn).toBe(false);
        expect(store.token).toBeNull();
        expect(localStorage.getItem('token')).toBeNull();
        expect(localStorage.getItem('username')).toBeNull();
    });

    test('isTokenExpired reads jwt exp claim', () => {
        expect(isTokenExpired(createJwt({ exp: 100 }), 101)).toBe(true);
        expect(isTokenExpired(createJwt({ exp: 100 }), 99)).toBe(false);
        expect(isTokenExpired('opaque-dev-token', 101)).toBe(false);
    });

    test('restoreAuth returns false with no stored credentials', () => {
        const store = useAuthStore();
        const result = store.restoreAuth();
        
        expect(result).toBe(false);
        expect(store.isLoggedIn).toBe(false);
    });
}); 
