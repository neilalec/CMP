<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';
import { useSocketStore } from '../stores/socketStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';

const router = useRouter();
const authStore = useAuthStore();
const rootStore = useRootStore();
const socketStore = useSocketStore();

const formType = ref('login'); // 'login' or 'register'
const username = ref('');
const password = ref('');
const loading = ref(false);

const handleSubmit = async () => {
  loading.value = true;
  rootStore.clearError();

  try {
    // First, ensure socket connection with username
    if (!socketStore.isConnected) {
      console.log('Socket not connected, attempting to connect...');
      await socketStore.initSocket(null, username.value);
    }

    // Login/Register
    const response = await socketStore.emit(
      formType.value === 'login' ? SOCKET_EVENTS.AUTH.LOGIN : SOCKET_EVENTS.AUTH.REGISTER,
      {
        username: username.value,
        password: password.value
      }
    );

    if (response.success) {
      console.log('Authentication successful');
      await authStore.login(response.access_token, username.value);
      router.push('/');
    } else {
      throw new Error(response.message || 'Authentication failed');
    }
  } catch (error) {
    console.error('Authentication error:', error);
    rootStore.setError(error.message);
  } finally {
    loading.value = false;
  }
};

const toggleForm = () => {
  formType.value = formType.value === 'login' ? 'register' : 'login';
  rootStore.clearError();
  username.value = '';  // Clear form
  password.value = '';  // Clear form
  loading.value = false;  // Reset loading state
};
</script>

<template>
  <div class="auth-container">
    <h2>{{ formType === 'login' ? 'Login' : 'Register' }}</h2>
    <form @submit.prevent="handleSubmit">
      <input
        v-model="username"
        type="text"
        placeholder="Username"
        required
      />
      <input
        v-model="password"
        type="password"
        placeholder="Password"
        required
      />
      <button type="submit" :disabled="loading">
        {{ loading ? 'Processing...' : (formType === 'login' ? 'Login' : 'Register') }}
      </button>
    </form>
    
    <div class="toggle-form">
      {{ formType === 'login' ? "Don't have an account?" : 'Already have an account?' }}
      <a href="#" @click.prevent="toggleForm">
        {{ formType === 'login' ? 'Register' : 'Login' }}
      </a>
    </div>
  </div>
</template>

<style scoped>
.auth-container {
  max-width: 300px;
  margin: 2rem auto;
  padding: 1rem;
}

form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

input, button {
  padding: 0.5rem;
  width: 100%;
}

button:disabled {
  opacity: 0.5;
}

.toggle-form {
  margin-top: 1rem;
  text-align: center;
}
</style>