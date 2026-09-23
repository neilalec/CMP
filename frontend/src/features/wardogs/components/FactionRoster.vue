<script setup>
import { computed } from 'vue';

const props = defineProps({ faction: { type: Object, required: true }, summary: { type: Object, required: true } });
const groupsFor = (status) => props.faction.groups.map((group) => ({
  ...group, players: group.players.filter((player) => player.rosterStatus === status)
})).filter((group) => group.players.length);
const activeGroups = computed(() => groupsFor('active'));
const reserveGroups = computed(() => groupsFor('reserve'));
const commander = computed(() => props.faction.groups.flatMap((group) => group.players).find((player) => player.id === props.faction.commanderId));
const alignment = (player) => player.connected !== true ? 'Not observed' :
  !player.observedFactionId ? 'Faction unknown' :
    player.observedFactionId === props.faction.id ? 'On faction' : 'Faction mismatch';
</script>

<template>
  <article class="wardogs-faction-card" :style="{ '--faction-color': faction.color }">
    <header class="wardogs-faction-header">
      <div><h3>{{ faction.name }}</h3><span>{{ summary.active }} active · {{ summary.reserves }} reserves<span v-if="faction.mockCapacity"> · mock target {{ faction.mockCapacity }}</span></span></div>
      <strong>{{ summary.ready }}/{{ summary.active }} ready</strong>
    </header>
    <div class="wardogs-faction-meta">
      <span>{{ summary.connected }}/{{ summary.active }} connected</span>
      <span>{{ summary.missing }} missing</span>
      <span v-if="summary.unknown">{{ summary.unknown }} connection unknown</span>
      <span>{{ summary.aligned }}/{{ summary.active }} on faction</span>
      <span>Commander: {{ commander?.displayName || 'Unassigned' }}</span>
    </div>
    <div class="wardogs-groups">
      <div v-for="section in [{ label: 'Active roster', groups: activeGroups }, { label: 'Reserves', groups: reserveGroups }]" :key="section.label">
        <h4>{{ section.label }}</h4>
        <p v-if="!section.groups.length" class="wardogs-empty">None</p>
        <details v-for="(group, index) in section.groups" :key="`${section.label}-${group.id}`" class="wardogs-group" :open="index === 0 && section.label === 'Active roster'">
          <summary><strong>{{ group.name }}</strong><span>{{ group.type }} · {{ group.players.length }}</span></summary>
          <div class="wardogs-player-list">
            <div v-for="player in group.players" :key="player.id" class="wardogs-player">
              <div><strong>{{ player.displayName }}</strong><span v-if="player.id === group.leaderId">Group leader</span></div>
              <div class="wardogs-player-flags">
                <span>{{ player.registered ? 'CMP registered' : 'CMP registration pending' }}</span>
                <span>{{ player.steamId ? 'Steam linked' : 'Identity pending' }}</span>
                <span :class="{ 'wardogs-warning': player.connected === false }">{{ player.connected === null ? 'Connection unknown' : player.connected ? 'Connected' : 'Absent' }}</span>
                <span :class="{ 'wardogs-warning': player.connected === true && player.observedFactionId && player.observedFactionId !== faction.id }">{{ alignment(player) }}</span>
                <span :class="{ 'wardogs-ready': player.ready }">{{ player.ready ? 'Ready' : 'Waiting' }}</span>
              </div>
            </div>
          </div>
        </details>
      </div>
    </div>
  </article>
</template>
