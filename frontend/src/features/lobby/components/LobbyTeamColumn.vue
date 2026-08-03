<script setup>
defineProps({
  teamLabel: {
    type: String,
    required: true
  },
  groups: {
    type: Array,
    default: () => []
  },
  teamKey: {
    type: String,
    required: true
  },
  isCurrentUser: {
    type: Function,
    required: true
  },
  isCaptain: {
    type: Function,
    required: true
  },
  getConnectionFlagClass: {
    type: Function,
    required: true
  },
  getConnectionLabel: {
    type: Function,
    required: true
  },
  getDisplayName: {
    type: Function,
    default: (username) => username
  },
  showConnectionStatus: {
    type: Boolean,
    default: false
  }
})
</script>

<template>
  <div class="team map-vote-team window-panel">
    <div class="window-titlebar">
      <span class="window-titlebar-label">{{ teamLabel }}</span>
      <span class="window-titlebar-meta">{{ groups.reduce((count, group) => count + group.members.length, 0) }} players</span>
    </div>
    <div class="team-body">
      <ul>
        <li
          v-for="(group, index) in groups"
          :key="group.id || `solo-${index}`"
          :class="['team-group', 'player-row', 'is-centered', { grouped: !!group.id }]"
        >
          <div class="team-group-members">
            <span
              v-for="member in group.members"
              :key="member"
              :class="['team-group-member', { 'is-current-user': isCurrentUser(member) }]"
              :title="member"
            >
              <span :class="['player-name', { 'current-user': isCurrentUser(member) }]">{{ getDisplayName(member) }}</span>
              <span v-if="showConnectionStatus" :class="['connection-label', getConnectionFlagClass(member)]">
                {{ getConnectionLabel(member) }}
              </span>
              <span v-if="isCaptain(member, teamKey)" class="captain-tag">Captain</span>
            </span>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.team {
  flex: 1;
  margin: 0;
  min-width: 0;
  overflow: hidden;
}

.team-body {
  padding: 12px;
}

.map-vote-team {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  margin-top: 0;
}

.map-vote-team ul,
.team ul {
  list-style: none;
  padding: 0;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  justify-content: stretch;
  align-items: start;
  gap: 8px;
  width: 100%;
}

.map-vote-team li,
.team li {
  font-size: 0.8rem;
  margin: 0;
  text-align: center;
  gap: 6px;
  width: 100%;
  max-width: 100%;
}

.team-group {
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 7px 9px;
  width: 100%;
  max-width: 100%;
}

.team-group.grouped {
  border: 1px solid var(--accent-border);
}

.team-group-members {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  align-items: start;
  column-gap: 5px;
  row-gap: 14px;
  width: 100%;
  margin: 0 auto;
  justify-content: stretch;
}

.team-group-member {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  text-align: center;
  min-width: 0;
  padding: 2px 6px;
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
}

.player-name {
  display: block;
  width: 100%;
  max-width: 128px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--lobby-player-name-text, var(--text-main));
  font-weight: 700;
  letter-spacing: 0.01em;
}

.player-name.current-user {
  width: auto;
  max-width: 100%;
  margin-inline: auto;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--accent-border);
  background: var(--accent-soft);
  color: var(--accent-strong);
  font-weight: 800;
  box-shadow: none;
  text-shadow: none;
}

.team-group-member.is-current-user {
  gap: 4px;
}

.connection-label {
  color: var(--lobby-player-status-text, var(--text-muted));
  font-size: 0.64rem;
  line-height: 1;
  white-space: nowrap;
  text-align: center;
  font-weight: 750;
}

.connection-label.is-connected {
  color: var(--lobby-player-status-connected, var(--success));
}

.connection-label.is-missing {
  color: var(--lobby-player-status-missing, var(--danger));
}

.connection-label.is-misaligned {
  color: var(--lobby-player-status-warning, var(--warning));
}

.connection-label.is-unavailable {
  color: var(--lobby-player-status-warning, var(--warning));
}

.captain-tag {
  font-size: 0.75rem;
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-weight: 700;
}

@media (max-width: 640px) {
  .team {
    padding: 14px;
    min-width: 0;
  }

  .team-group-members {
    width: 100%;
  }

  .map-vote-team ul,
  .team ul {
    grid-template-columns: repeat(auto-fit, minmax(124px, 1fr));
  }
}
</style>
