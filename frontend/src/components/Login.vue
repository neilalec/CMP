<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useSocket } from '../useSocket';
import { login as authLogin, authState } from '../stores/auth'; // Use the global auth state


const router = useRouter();
const { socket } = useSocket();
const username = ref('');
const password = ref('');
const loading = ref(false);
const errorMsg = ref('');



const handleLogin = async () => {
  // Reset error message
  errorMsg.value = '';
  console.log('Login attempt');
  
  // Basic validation
  if (!username.value || !password.value) {
    errorMsg.value = 'Please enter both username and password.';
    return;
  }

  loading.value = true; // Set loading state
  console.log('Socket instance:', socket.value);

  try {

    if (socket.value) {
      console.log('Emitting login');

 // Create a Promise to handle the login response
      const loginPromise = new Promise((resolve, reject) => {
              socket.value.emit('login', { 
                username: username.value,
                password: password.value
              });

      socket.value.once('login_success', (data) => {
        console.log('Login success:', data);
        resolve(data);
      });

      socket.value.once('login_error', (data) => {
        console.log('Login error:', data);
        reject(new Error(data.msg || 'Login failed'));
      });

      // Add timeout
      setTimeout(() => reject(new Error('Login timeout')), 5000);
    });

    const data = await loginPromise;
    authLogin(data.access_token);
    localStorage.setItem('username', username.value);
    router.push('/');

    }else {
      throw new Error('Unable to establish socket connection');
    }
  } catch (error) {
    console.error('Login error:', error);
    errorMsg.value = error.message || 'Unable to connect to the server. Please try again later.';
  } finally {
    loading.value = false;
  }
};


</script>

<template>
  <div class="form-container">
    <h2>Login</h2>
    <input v-model="username" placeholder="Username" />
    <input v-model="password" type="password" placeholder="Password" />
    <button @click="handleLogin" :disabled="loading">{{ loading ? 'Logging in...' : 'Login' }}</button>
    <p v-if="errorMsg" class="error-message">{{ errorMsg }}</p>
  </div>
</template>

<style scoped>
.form-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  margin: 0 auto;
  width: 100%;
  max-width: 500px;
  text-align: center;
}
</style>