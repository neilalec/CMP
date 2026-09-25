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
const playerAlert = (player) => props.observationState === 'fresh' &&
  (player.connected === false || (player.connected === true &&
    player.observedFactionId && player.observedFactionId !== props.faction.id));
</script>

<template>
  <article class="wardogs-faction-card cmp-surface" :class="`cmp-faction--${faction.id}`">
    <header class="wardogs-faction-header">
      <div><h3>{{ faction.name }}</h3><p>{{ summary.active }} active<span v-if="summary.reserves"> · {{ summary.reserves }} reserve{{ summary.reserves === 1 ? '' : 's' }}</span><span v-if="faction.mockCapacity"> · sample target {{ faction.mockCapacity }}</span></p></div>
    </header>
    <div class="wardogs-groups">
      <section v-for="section in [{ label: 'Active roster', groups: activeGroups }, { label: 'Reserves', groups: reserveGroups }]" v-show="section.label !== 'Reserves' || section.groups.length" :key="section.label" class="wardogs-roster-section">
        <h4>{{ section.label }}</h4>
        <p v-if="!section.groups.length" class="wardogs-empty">None</p>
        <div v-for="group in section.groups" :key="`${section.label}-${group.id}`" class="wardogs-group" :class="{ 'is-my-group': group.id === myGroupId }">
          <div v-if="group.type !== 'solo' || group.players.length > 1" class="wardogs-group-heading"><strong>{{ group.name }}</strong><span v-if="group.id === myGroupId">Your group · </span><span>{{ group.type }} · {{ group.players.length }} player{{ group.players.length === 1 ? '' : 's' }}</span></div>
          <ul class="wardogs-player-list">
            <li v-for="player in group.players" :key="player.id" class="wardogs-player" :class="{ 'is-me': player.id === myPlayerId }">
              <div class="wardogs-player-identity"><strong>{{ player.displayName }}<small v-if="player.id === myPlayerId"> · You</small></strong><small v-if="player.id === group.leaderId">Group leader</small></div>
              <p v-if="playerAlert(player)" class="cmp-status wardogs-player-presence" :class="playerTone(player)">{{ playerPresence(player) }}</p>
            </li>
          </ul>
        </div>
      </section>
      <details class="wardogs-roster-detail cmp-disclosure">
        <summary>Roster status</summary>
        <p>{{ summary.ready }}/{{ summary.active }} CMP ready · Commander: {{ commander?.displayName || 'Unassigned' }}</p>
        <p v-if="observationState === 'fresh'">{{ summary.connected }}/{{ summary.active }} connected · {{ summary.aligned }} aligned</p>
        <p v-else-if="observationState === 'stale'">Last server observation is stale; current presence is unknown.</p>
        <p v-else>Server presence unknown.</p>
        <ul>
          <li v-for="player in faction.groups.flatMap((group) => group.players)" :key="player.id">
            {{ player.displayName }} · {{ playerPresence(player) }} · {{ player.ready ? 'CMP ready' : 'Not CMP ready' }}<template v-if="player.devSimulated"> · DEV simulated presence</template><template v-else-if="player.devSynthetic"> · DEV test account</template><template v-if="!player.registered"> · CMP registration pending</template><template v-if="!player.steamId"> · Identity pending</template>
          </li>
        </ul>
      </details>
    </div>
  </article>
</template>
