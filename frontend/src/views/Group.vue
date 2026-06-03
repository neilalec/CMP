<script setup>
import { useGroupView } from '../features/group/composables/useGroupView';

const {
  authStore,
  groupStore,
  handleCreate,
  handleJoin,
  handleLeave,
  joinCode
} = useGroupView();

</script>

<template>
  <div class="group-page content-panel">
    <h1>Group</h1>
    &nbsp
    &nbsp
    <div v-if="!groupStore.inGroup" class="group-card">
      <p class="group-note">
        Create a group to queue together, or join with a code.
      </p>
      <div class="group-actions">
        <button @click="handleCreate" :disabled="groupStore.loading">
          Create Group
        </button>
      </div>
      <div class="group-join">
        <input
          v-model="joinCode"
          type="text"
          placeholder="Enter group code"
          maxlength="8"
        />
        <button @click="handleJoin" :disabled="groupStore.loading">
          Join Group
        </button>
      </div>
    </div>

    <div v-else class="group-card">
      <div class="group-header">
        <p class="group-code">
          Group Code <strong>{{ groupStore.code }}</strong>
        </p>
        <p class="group-leader">
          Leader <strong :class="{ 'current-user': groupStore.leader === authStore.username }">{{ groupStore.leader }}</strong>
        </p>
      </div>
      <div class="group-members">
        <h3>Members</h3>
        <ul>
          <li v-for="member in groupStore.members" :key="member">
            <span :class="{ 'leader-name': member === groupStore.leader, 'current-user': member === authStore.username }">
              {{ member }}
            </span>
            <span v-if="member === groupStore.leader"></span>
          </li>
        </ul>
      </div>
      <div class="group-actions">
        <button @click="handleLeave" :disabled="groupStore.loading">
          Leave Group
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
h1 {
  color: inherit;
  font-weight: 500;
}

.group-page {
  width: min(100%, 960px);
  max-width: 960px;
  margin: clamp(20px, 5vw, 56px) auto 0;
  text-align: center;
}

.group-name {
  font-weight: 600;
  font-size: 1.15rem;
  color: inherit;
  margin: 0.5rem 0 1rem;
}

.group-card {
  max-width: 720px;
  margin: 0 auto;
  padding: 1rem 1.5rem 1.5rem;
  background: var(--panel-bg);
  border-radius: 10px;
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 1rem;
}

.group-header {
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: center;
}

.group-note {
  color: inherit;
  margin-bottom: 1rem;
}

.group-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin: 1rem 0;
}

.group-join {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 0.5rem;
}

.group-join input {
  padding: 0.6rem 0.8rem;
  border-radius: 6px;
  border: 1px solid #2d2d2d;
  background: #1f1f1f;
  color: inherit;
  width: 180px;
  text-align: center;
}

.group-code,
.group-leader {
  margin: 0;
  font-size: 1.05rem;
}

.group-code strong,
.group-leader strong {
  color: #4CAF50;
  font-weight: 700;
}

.group-leader strong.current-user {
  color: #d4af37;
}

.group-code {
  text-align: left;
}

.group-leader {
  text-align: right;
}

.group-members {
  margin: 0;
  text-align: center;
}

.group-members h3 {
  margin-bottom: 0.5rem;
  color: inherit;
  font-weight: 500;
}

.group-members ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.group-members li {
  padding: 0.2rem 0;
}

.leader-name {
  color: #4CAF50;
  font-weight: 700;
}

.leader-name.current-user {
  color: #d4af37;
}

.group-hint {
  color: #888;
  margin-top: 0.5rem;
}

button {
  display: inline-block;
  padding: 0.7rem 1.2rem;
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

@media (max-width: 768px) {
  .group-header {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .group-code,
  .group-leader {
    text-align: center;
  }

  .group-actions,
  .group-join {
    flex-direction: column;
    align-items: center;
  }

  .group-join input,
  .group-join button,
  .group-actions button {
    width: min(100%, 260px);
  }
}
</style>
