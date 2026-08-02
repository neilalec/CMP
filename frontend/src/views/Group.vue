<script setup>
import { useGroupView } from '../features/group/composables/useGroupView';

const {
  authStore,
  groupStore,
  handleCreate,
  handleJoin,
  handleKickMember,
  handleLeave,
  handleTransferOwnership,
  getMemberDisplayName,
  isGroupLeader,
  joinCode
} = useGroupView();

</script>

<template>
  <div class="group-page content-panel page-shell narrow">
    <div v-if="!groupStore.inGroup" class="group-card">
      <div class="group-option-grid">
        <section class="group-option surface-card">
          <div class="window-titlebar group-option-titlebar">
            <span class="window-titlebar-label">Create</span>
          </div>
          <div class="group-option-body">
            <button class="group-create-button" @click="handleCreate" :disabled="groupStore.loading">
              Create Group
            </button>
          </div>
        </section>

        <section class="group-option surface-card">
          <div class="window-titlebar group-option-titlebar">
            <span class="window-titlebar-label">Join</span>
          </div>
          <div class="group-option-body">
            <div class="group-join-control">
              <input
                v-model="joinCode"
                type="text"
                placeholder="Code"
                maxlength="8"
              />
              <button @click="handleJoin" :disabled="groupStore.loading">
                Join Group
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>

    <div v-else class="group-card group-card-active surface-card">
      <div class="group-summary">
        <div class="group-code-panel summary-tile">
          <span class="eyebrow">Group Code</span>
          <strong>{{ groupStore.code }}</strong>
        </div>
        <div class="group-leader-panel summary-tile">
          <span class="eyebrow">Leader</span>
          <strong :title="groupStore.leader">{{ getMemberDisplayName(groupStore.leader) }}</strong>
        </div>
      </div>

      <div class="group-members">
        <div class="group-members-heading">
          <span class="eyebrow">Members</span>
          <strong>{{ groupStore.members.length }}</strong>
        </div>
        <ul>
          <li
            v-for="member in groupStore.members"
            :key="member"
            class="player-row is-between"
          >
            <span
              :class="{
                'leader-name': member === groupStore.leader,
                'current-user-name': member === authStore.username
              }"
              :title="member"
            >
              {{ getMemberDisplayName(member) }}
            </span>
            <span v-if="member === groupStore.leader" class="member-role">Leader</span>
            <div v-else-if="isGroupLeader" class="member-actions">
              <button
                type="button"
                class="transfer-leader-button"
                :disabled="groupStore.loading"
                @click="handleTransferOwnership(member)"
              >
                Make Leader
              </button>
              <button
                type="button"
                class="kick-member-button"
                :disabled="groupStore.loading"
                @click="handleKickMember(member)"
              >
                Kick
              </button>
            </div>
            <span v-else class="member-role">Member</span>
          </li>
        </ul>
      </div>

      <div class="group-actions action-row">
        <button class="leave-group-button" @click="handleLeave" :disabled="groupStore.loading">
          Leave Group
        </button>
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
  max-width: 560px;
  margin: 0 auto;
}

.group-card-active {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 14px;
  padding: 14px;
  text-align: left;
}

.group-option-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-items: stretch;
}

.group-option {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 0;
  align-content: start;
  overflow: hidden;
  padding: 0;
}

.group-option-titlebar {
  min-height: 36px;
}

.group-option-body {
  display: grid;
  align-items: center;
  padding: 14px;
}

.group-create-button,
.group-join-control {
  min-height: 44px;
}

.group-create-button {
  width: 100%;
}

.group-join-control {
  display: grid;
  grid-template-columns: minmax(84px, 1fr) auto;
  gap: 8px;
}

.group-join-control input {
  min-width: 0;
  text-align: center;
}

.group-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.group-code-panel,
.group-leader-panel {
  min-width: 0;
  background: var(--titlebar-bg);
  border-color: var(--titlebar-divider);
  box-shadow:
    inset 1px 1px 0 rgba(255, 255, 255, 0.32),
    inset -1px -1px 0 rgba(34, 32, 24, 0.16),
    var(--card-inner-shadow);
  color: var(--blue-banner-text);
}

.group-code-panel .eyebrow,
.group-leader-panel .eyebrow {
  color: var(--blue-banner-text);
}

.group-code-panel strong {
  font-family: var(--font-mono);
  font-size: 1.62rem;
  letter-spacing: 0.08em;
  color: var(--blue-banner-text);
  line-height: 1;
}

.group-leader-panel strong {
  color: var(--blue-banner-text);
  font-size: 1.12rem;
  font-weight: 700;
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.group-actions {
  margin: 0;
}

.group-members {
  margin: 0;
  display: grid;
  gap: 8px;
  text-align: left;
}

.group-members-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 2px;
}

.group-members-heading strong {
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: 1rem;
}

.group-members ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.group-members li {
  margin: 0;
}

.group-members li > span:first-child {
  font-size: 1.02rem;
  line-height: 1.2;
}

.leader-name {
  color: var(--accent-strong);
  font-weight: 700;
}

.current-user-name {
  font-weight: 900;
}

.member-role {
  flex: 0 0 auto;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.member-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 7px;
}

.transfer-leader-button,
.kick-member-button {
  min-height: 28px;
  padding: 0.25rem 0.55rem;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.kick-member-button {
  border-color: color-mix(in srgb, var(--danger) 42%, var(--surface-border));
  color: var(--danger);
}

.leave-group-button {
  width: 100%;
}

button {
  display: inline-block;
}

@media (max-width: 768px) {
  .group-summary {
    grid-template-columns: 1fr;
  }

  .group-actions {
    flex-direction: column;
    align-items: center;
  }

  .group-option-grid,
  .group-join-control {
    grid-template-columns: 1fr;
  }

  .group-create-button,
  .group-join-control button,
  .group-join-control input,
  .group-actions button {
    width: 100%;
    justify-self: center;
  }

  .member-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}
</style>
