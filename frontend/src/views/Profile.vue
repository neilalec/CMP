<script setup>
import { useAuthStore } from '../stores/authStore';
import { useSocketStore } from '../stores/socketStore';
import { useRootStore } from '../stores/rootStore';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const router = useRouter();

const handleLogout = async () => {
  try {
    await socketStore.cleanupSocket();
    authStore.logout();
    localStorage.removeItem('currentLobby');
    await socketStore.initSocket();
    router.push('/auth');
  } catch (error) {
    rootStore.setError('Logout failed');
  }
};
</script>

<template>
  <div class="profile-page content-panel">
    <h1>Profile</h1>
    <p class="profile-name current-user">{{ authStore.username }}</p>
    <p class="profile-note">Profile details coming soon.</p>
    <div class="profile-actions">
      <button @click="handleLogout">Logout</button>
    </div>
  </div>
</template>

<style scoped>
h1 {
  color: inherit;
  font-weight: 500;
}
.profile-page {
  width: 100%;
  max-width: 100%;
  margin: 0;
  text-align: center;
}

.profile-name {
  font-weight: 700;
  font-size: 1.3rem;
  color: inherit;
  margin: 0.5rem 0 0.75rem;
}

.profile-note {
  color: inherit;
}

.profile-actions {
  margin-top: 1.5rem;
}

button {
  display: block;
  width: 200px;
  margin: 1rem auto;
  padding: 0.8rem;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

button:hover {
  background: #4a4f56;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
