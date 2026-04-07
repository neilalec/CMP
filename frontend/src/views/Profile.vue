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
    <p class="profile-name">{{ authStore.username }}</p>
    <p class="profile-note">Profile details coming soon.</p>
    <div class="profile-actions">
      <button @click="handleLogout">Logout</button>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  width: 100%;
  max-width: 520px;
  margin: 1rem auto;
  text-align: center;
}

.profile-name {
  font-weight: 700;
  font-size: 1.3rem;
  color: #ffffff;
  margin: 0.5rem 0 0.75rem;
}

.profile-note {
  color: #cccccc;
}

.profile-actions {
  margin-top: 1.5rem;
  display: flex;
  justify-content: center;
}
</style>
