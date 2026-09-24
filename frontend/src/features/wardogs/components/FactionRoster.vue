<script setup>
import { computed } from 'vue';

const props = defineProps({ faction: { type: Object, required: true }, summary: { type: Object, required: true }, observationState: { type: String, default: 'none' }, myGroupId: { type: String, default: null }, myPlayerId: { type: String, default: null } });
const groupsFor = (status) => props.faction.groups.map((group) => ({
  ...group, players: group.players.filter((player) => player.rosterStatus === status)
})).filter((group) => group.players.length);
const activeGroups = computed(() => groupsFor('active'));
const reserveGroups = computed(() => groupsFor('reserve'));
const commander = computed(() => props.faction.groups.flatMap((group) => group.players).find((player) => player.id === props.faction.commanderId));
const playerPresence = (player) => {
  if (['none', 'unavailable'].includes(props.observationState)) return 'Server presence unknown';
  if (props.observationState === 'stale') return player.connected === true
    ? `Last seen connected${player.observedFactionId && player.observedFactionId !== props.faction.id ? ` on ${player.observedFactionName || player.observedFactionId}; planned ${props.faction.name}` : ''}; current presence unknown`
    : player.connected === false ? 'Last seen absent; current presence unknown' : 'Current presence unknown';
  if (player.connected === false) return 'Not observed on server';
  if (player.connected !== true) return 'Connection unknown';
  if (!player.observedFactionId) return 'Connected · faction unknown';
  return player.observedFactionId === props.faction.id ? 'Connected · on faction'
    : `Connected · Faction mismatch · observed ${player.observedFactionName || player.observedFactionId}`;
};
const playerTone = (player) => {
  if (props.observationState === 'stale' || ['none', 'unavailable'].includes(props.observationState)) return 'cmp-status--stale';
  if (player.connected === true && player.observedFactionId && player.observedFactionId !== props.faction.id) return 'cmp-status--danger';
  if (player.connected === false || player.connected == null || !player.observedFactionId) return 'cmp-status--warning';
  return 'cmp-status--success';
};
</script>

<template>
  <article class="wardogs-faction-card cmp-surface" :class="`cmp-faction--${faction.id}`">
    <header class="wardogs-faction-header">
      <div><h3>{{ faction.name }}</h3><p>{{ summary.active }} active · {{ summary.reserves }} reserve{{ summary.reserves === 1 ? '' : 's' }}<span v-if="faction.mockCapacity"> · sample target {{ faction.mockCapacity }}</span></p></div>
      <strong>{{ summary.ready }}/{{ summary.active }} CMP ready</strong>
    </header>
    <p class="wardogs-faction-meta">
      <span v-if="observationState === 'stale'">{{ summary.connected }}/{{ summary.active }} last seen connected; current presence unknown</span>
      <span v-else-if="observationState === 'none' || observationState === 'unavailable'">Connection observation unavailable</span>
      <span v-else>{{ summary.connected }}/{{ summary.active }} connected<span v-if="observationState === 'fresh'"> · {{ summary.aligned }} aligned</span></span>
      <span v-if="summary.missing && observationState === 'fresh'"> · {{ summary.missing }} not observed</span>
      <span v-if="summary.unknown"> · {{ summary.unknown }} unknown</span>
      <span> · Commander: {{ commander?.displayName || 'Unassigned' }}</span>
    </p>
    <div class="wardogs-groups">
      <section v-for="section in [{ label: 'Active roster', groups: activeGroups }, { label: 'Reserves', groups: reserveGroups }]" :key="section.label" class="wardogs-roster-section">
        <h4>{{ section.label }}</h4>
        <p v-if="!section.groups.length" class="wardogs-empty">None</p>
        <div v-for="group in section.groups" :key="`${section.label}-${group.id}`" class="wardogs-group" :class="{ 'is-my-group': group.id === myGroupId }">
          <div class="wardogs-group-heading"><strong>{{ group.name }}</strong><span v-if="group.id === myGroupId">Your group · </span><span>{{ group.type }} · {{ group.players.length }}</span></div>
          <ul class="wardogs-player-list">
            <li v-for="player in group.players" :key="player.id" class="wardogs-player" :class="{ 'is-me': player.id === myPlayerId }">
              <div class="wardogs-player-identity"><strong>{{ player.displayName }}<small v-if="player.id === myPlayerId"> · You</small></strong><small v-if="player.id === group.leaderId">Group leader</small></div>
              <p class="cmp-status wardogs-player-presence" :class="playerTone(player)">{{ playerPresence(player) }}</p>
              <p v-if="player.rosterStatus === 'active'" class="wardogs-player-ready">{{ player.ready ? 'CMP ready' : 'Not CMP ready' }}</p>
              <p v-if="!player.registered || !player.steamId || player.devSimulated || player.devSynthetic" class="wardogs-player-notes"><span v-if="!player.registered">CMP registration pending</span><span v-if="!player.steamId">Identity pending</span><span v-if="player.devSimulated">DEV simulated presence</span><span v-else-if="player.devSynthetic">DEV test account</span></p>
            </li>
          </ul>
        </div>
      </section>
    </div>
  </article>
</template>
