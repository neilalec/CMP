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
  <div class="group-page content-panel page-shell narrow">
    <div v-if="!groupStore.inGroup" class="group-card window-panel">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Group</span>
      </div>
      <div class="group-card-body panel-body">
        <div class="group-actions action-row">
          <button @click="handleCreate" :disabled="groupStore.loading">
            New
          </button>
        </div>
        <div class="group-join">
          <input
            v-model="joinCode"
            type="text"
            placeholder="Code"
            maxlength="8"
          />
          <button @click="handleJoin" :disabled="groupStore.loading">
            Join
          </button>
        </div>
      </div>
    </div>

    <div v-else class="group-card window-panel">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Group</span>
        <span class="window-titlebar-meta">{{ groupStore.code }}</span>
      </div>
      <div class="group-card-body panel-body">
      <div class="group-header">
        <p class="group-code"><strong>{{ groupStore.code }}</strong></p>
        <p class="group-leader">
          <strong :class="{ 'current-user': groupStore.leader === authStore.username }">{{ groupStore.leader }}</strong>
        </p>
      </div>
      <div class="group-members">
        <ul>
          <li v-for="member in groupStore.members" :key="member">
            <span :class="{ 'leader-name': member === groupStore.leader, 'current-user': member === authStore.username }">
              {{ member }}
            </span>
            <span v-if="member === groupStore.leader"></span>
          </li>
        </ul>
      </div>
      <div class="group-actions action-row">
        <button @click="handleLeave" :disabled="groupStore.loading">
          Leave
        </button>
      </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.group-page {
  width: min(100%, 960px);
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
  overflow: hidden;
}

.group-card-body {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 1rem;
}

.group-header {
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: center;
}

.group-actions {
  margin: 1rem 0;
}

.group-join {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 0.5rem;
}

.group-join input {
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
  color: var(--accent-strong);
  font-weight: 700;
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
  color: var(--accent-strong);
  font-weight: 700;
}

.leader-name.current-user {
  color: var(--gold-strong);
}

.group-hint {
  color: #888;
  margin-top: 0.5rem;
}

button {
  display: inline-block;
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
