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
  }
})
</script>

<template>
  <div class="team map-vote-team">
    <h3>{{ teamLabel }}</h3>
    <ul>
      <li
        v-for="(group, index) in groups"
        :key="group.id || `solo-${index}`"
        :class="['team-group', { grouped: !!group.id }]"
      >
        <div class="team-group-members">
          <span v-for="member in group.members" :key="member" class="team-group-member">
            <span :class="{ 'current-user': isCurrentUser(member) }">{{ member }}</span>
            <span :class="['connection-flag', getConnectionFlagClass(member)]">
              {{ getConnectionLabel(member) }}
            </span>
            <span v-if="isCaptain(member, teamKey)" class="captain-tag">Captain</span>
          </span>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.team {
  flex: 1;
  margin: 0;
  padding: 20px 12px;
  background: transparent;
  border-radius: 4px;
  min-width: 0;
}

.team h3 {
  text-align: center;
  margin-bottom: 15px;
  color: inherit;
  font-weight: 600;
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
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.map-vote-team li,
.team li {
  font-size: 0.8rem;
  padding: 8px;
  margin: 5px 0;
  background: #243447;
  border-radius: 4px;
  text-align: center;
  color: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: auto;
  max-width: 100%;
}

.team-group {
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 10px;
  width: auto;
  max-width: 100%;
}

.team-group.grouped {
  border: 1px solid rgba(126, 217, 87, 0.25);
}

.team-group-members {
  display: grid;
  grid-template-columns: repeat(2, max-content);
  gap: 6px 12px;
  width: auto;
  margin: 0 auto;
  justify-content: center;
  justify-items: center;
}

.team-group-member {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  text-align: center;
  min-width: 0;
  padding: 2px 4px;
  width: fit-content;
  max-width: 100%;
  margin: 0 auto;
}

.current-user {
  font-weight: 700;
}

.connection-flag {
  font-family: "Courier New", Courier, monospace;
  font-size: 0.68rem;
  line-height: 1;
  text-transform: lowercase;
  white-space: nowrap;
  text-align: center;
}

.connection-flag.is-connected {
  color: #7ed957;
}

.connection-flag.is-missing {
  color: #ff6b6b;
}

.connection-flag.is-unavailable {
  color: #f1c40f;
}

.captain-tag {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: #1f1f1f;
  color: inherit;
  padding: 2px 6px;
  border-radius: 999px;
}

@media (max-width: 640px) {
  .team {
    padding: 14px;
    min-width: 0;
  }

  .team-group-members {
    grid-template-columns: 1fr;
  }
}
</style>
