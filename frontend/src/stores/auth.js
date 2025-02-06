import { reactive } from 'vue';
import { useSocket } from '../useSocket';

export const authState = reactive({
  isLoggedIn: !!localStorage.getItem('token'), // Sync with localStorage initially
});

export const login = (token) => {
  localStorage.setItem('token', token);
  authState.isLoggedIn = true;
};

export const logout = (router) => {
  if (!router) {
    console.error('Router instance is not passed to logout.');
    return;
  }
  
  // Clean up socket connection
  const { cleanupSocket } = useSocket();
  cleanupSocket();

  // Clear auth state
  localStorage.removeItem('token');
  localStorage.removeItem('username');
  authState.isLoggedIn = false;
  
  // Navigate to login
  router.push('/login').catch(() => {});
};
