<script setup>
import { computed } from 'vue';

const props = defineProps({ faction: { type: Object, required: true }, summary: { type: Object, required: true }, observationState: { type: String, default: 'none' }, myGroupId: { type: String, default: null }, myPlayerId: { type: String, default: null } });
const groupsFor = (status) => props.faction.groups.map((group) => ({
  ...group, players: group.players.filter((player) => player.rosterStatus === status)
})).filter((group) => group.players.length);
const activeGroups = computed(() => groupsFor('active'));
const reserveGroups = computed(() => groupsFor('reserve'));
const commander = computed(() => props.faction.groups.flatMap((group) => group.players).find((player) => player.id === props.faction.commanderId));
const alignment = (player) => player.connected !== true ? 'Faction unknown' :
  !player.observedFactionId ? 'Faction unknown' :
    player.observedFactionId === props.faction.id
      ? (props.observationState === 'stale' ? 'Last seen on faction' : 'On faction')
      : (props.observationState === 'stale'
        ? `Last seen on ${player.observedFactionName || player.observedFactionId}; planned ${props.faction.name}`
        : `Faction mismatch · observed on ${player.observedFactionName || player.observedFactionId}`);
const connectionLabel = (player) => {
  if (player.connected === null) return 'Connection unknown';
  if (props.observationState === 'stale') return player.connected ? 'Last seen connected' : 'Last seen absent';
  return player.connected ? 'Connected' : 'Absent';
};
</script>

<template>
  <article class="wardogs-faction-card" :class="`cmp-faction--${faction.id}`">
    <header class="wardogs-faction-header">
      <div><h3>{{ faction.name }}</h3><span>{{ summary.active }} active · {{ summary.reserves }} reserves<span v-if="faction.mockCapacity"> · mock target {{ faction.mockCapacity }}</span></span></div>
      <strong>{{ summary.ready }}/{{ summary.active }} ready</strong>
    </header>
    <div class="wardogs-faction-meta">
      <span v-if="observationState === 'stale'">{{ summary.connected }}/{{ summary.active }} last seen connected</span>
      <span v-else-if="observationState === 'none' || observationState === 'unavailable'">Connection observation unavailable</span>
      <span v-else>{{ summary.connected }}/{{ summary.active }} connected</span>
      <span v-if="summary.missing && observationState === 'fresh'">{{ summary.missing }} not observed</span>
      <span v-if="summary.unknown">{{ summary.unknown }} connection unknown</span>
      <span v-if="observationState === 'fresh'">{{ summary.aligned }}/{{ summary.active }} on faction</span>
      <span v-if="observationState === 'stale'">Last known presence</span>
      <span>Commander: {{ commander?.displayName || 'Unassigned' }}</span>
    </div>
    <div class="wardogs-groups">
      <div v-for="section in [{ label: 'Active roster', groups: activeGroups }, { label: 'Reserves', groups: reserveGroups }]" :key="section.label">
        <h4>{{ section.label }}</h4>
        <p v-if="!section.groups.length" class="wardogs-empty">None</p>
        <details v-for="(group, index) in section.groups" :key="`${section.label}-${group.id}`" class="wardogs-group" :class="{ 'is-my-group': group.id === myGroupId }" :open="group.id === myGroupId || (index === 0 && section.label === 'Active roster')">
          <summary><span><strong>{{ group.name }}</strong><b v-if="group.id === myGroupId">Your group</b><small>{{ group.players.map((player) => player.displayName).join(', ') }}</small></span><span>{{ group.type }} · {{ group.players.length }}</span></summary>
          <div class="wardogs-player-list">
            <div v-for="player in group.players" :key="player.id" class="wardogs-player" :class="{ 'is-me': player.id === myPlayerId }">
              <div><strong>{{ player.displayName }}<small v-if="player.id === myPlayerId"> · You</small></strong><span v-if="player.id === group.leaderId">Group leader</span></div>
              <div class="wardogs-player-flags">
                <span v-if="!player.registered" class="wardogs-warning">CMP registration pending</span>
                <span v-if="player.devSimulated">DEV simulated presence</span>
                <span v-else-if="player.devSynthetic">DEV test account</span>
                <span v-if="!player.steamId">Identity pending</span>
                <span :class="{ 'wardogs-warning': player.connected === false && observationState === 'fresh' }">{{ connectionLabel(player) }}</span>
                <span v-if="player.connected === true" :class="{ 'wardogs-warning': observationState === 'fresh' && player.observedFactionId && player.observedFactionId !== faction.id }">{{ alignment(player) }}</span>
                <span v-if="player.rosterStatus === 'active'" :class="{ 'wardogs-ready': player.ready }">{{ player.ready ? 'Ready' : 'Waiting' }}</span>
              </div>
            </div>
          </div>
        </details>
      </div>
    </div>
  </article>
</template>
