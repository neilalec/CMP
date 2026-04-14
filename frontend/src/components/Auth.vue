<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';
import { useSocketStore } from '../stores/socketStore';
import { useLobbyStore } from '../stores/lobbyStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';

const router = useRouter();
const authStore = useAuthStore();
const rootStore = useRootStore();
const socketStore = useSocketStore();
const lobbyStore = useLobbyStore();

const formType = ref('login');
const username = ref('');
const password = ref('');
const loading = ref(false);

const handleSubmit = async () => {
  loading.value = true;
  rootStore.clearError();

  try {
    const eventType = formType.value === 'login' ? 'login' : 'register';
    
    const response = await socketStore.emit(eventType, {
      username: username.value,
      password: password.value
    });

    if (response.success) {
      console.log(`${formType.value} successful`);
      // Set auth state
      await authStore.setAuth(response.access_token, username.value, response.profile);
      
      // Check for active lobby in response
      if (response.active_lobby) {
        console.log('Active lobby found:', response.active_lobby);
        localStorage.setItem('currentLobby', response.active_lobby);
        router.push(`/lobby/${response.active_lobby}`);
      } else {
        lobbyStore.leaveLobby();
        router.push('/');
      }
    } else {
      throw new Error(response.message || `${formType.value} failed`);
    }
  } catch (error) {
    console.error(`${formType.value} error:`, error);
    rootStore.setError(error.message);
  } finally {
    loading.value = false;
  }
};

const toggleForm = () => {
  formType.value = formType.value === 'login' ? 'register' : 'login';
  rootStore.clearError();
  username.value = '';
  password.value = '';
  loading.value = false;
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
  width: min(100%, 360px);
  margin: 0 auto;
  padding: 1.5rem;
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 14px;
  box-shadow: var(--surface-shadow);
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
