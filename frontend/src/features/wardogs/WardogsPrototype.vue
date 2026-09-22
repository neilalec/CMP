<script setup>
import { computed, ref } from 'vue';
import { fixtureOptions, wardogsFixtures } from './fixtures';

const selectedFixture = ref('partial');
const fixture = computed(() => wardogsFixtures[selectedFixture.value]);
const isRosterState = computed(() => ['lobby', 'partial', 'ready'].includes(fixture.value.state));
const totals = computed(() => {
  const players = fixture.value.factions.flatMap((faction) => faction.players);
  return { connected: players.filter((player) => player.connected).length, ready: players.filter((player) => player.ready).length, total: players.length };
});
const rankedFactions = computed(() => [...fixture.value.factions].sort((a, b) => (fixture.value.scores?.[b.id] || 0) - (fixture.value.scores?.[a.id] || 0)));
const titleFor = (key) => wardogsFixtures[key].label;
</script>

<template>
  <main class="wardogs-demo">
    <header class="demo-header">
      <div>
        <p class="eyebrow">WARDOGS / CMP feasibility prototype</p>
        <h1>Three-faction match room</h1>
        <p class="demo-copy">Local mock UI only. It is not connected to WDRCON, CMP matchmaking, or authoritative match lifecycle data.</p>
      </div>
      <label class="fixture-picker">
        <span>Prototype state</span>
        <select v-model="selectedFixture">
          <option v-for="option in fixtureOptions" :key="option" :value="option">{{ titleFor(option) }}</option>
        </select>
      </label>
    </header>

    <section class="overview window-panel">
      <div class="window-titlebar"><span>Match overview</span><span class="window-titlebar-meta">MOCK DATA</span></div>
      <div class="overview-body">
        <div class="summary-tile"><span class="data-card-label">Server</span><strong>{{ fixture.server }}</strong></div>
        <div class="summary-tile"><span class="data-card-label">Map</span><strong>{{ fixture.map }}</strong></div>
        <div class="summary-tile"><span class="data-card-label">Configuration</span><strong>{{ fixture.config }}</strong></div>
        <div class="summary-tile"><span class="data-card-label">Roster readiness</span><strong>{{ totals.connected }}/{{ totals.total }} connected · {{ totals.ready }}/{{ totals.total }} ready</strong></div>
      </div>
    </section>

    <section v-if="isRosterState" class="roster-section">
      <div class="section-heading"><div><p class="section-kicker">Faction readiness</p><h2>{{ fixture.label }}</h2></div><span class="scale-note">Roster cards scroll independently for larger factions</span></div>
      <div class="faction-grid">
        <article v-for="faction in fixture.factions" :key="faction.id" class="faction-card" :style="{ '--faction-color': faction.color }">
          <header class="faction-header"><div><span class="faction-swatch"></span><h3>{{ faction.name }}</h3></div><strong>{{ faction.players.filter((player) => player.ready).length }}/{{ faction.players.length }} ready</strong></header>
          <div class="roster-list">
            <div v-for="player in faction.players" :key="player.id" class="player-card" :class="{ disconnected: !player.connected }">
              <div><strong>{{ player.name }}</strong><span>{{ player.group }} <b v-if="player.captain">· Commander</b></span></div>
              <div class="player-status"><span :class="player.connected ? 'online' : 'offline'">{{ player.connected ? 'Steam linked · connected' : 'Steam linked · absent' }}</span><span :class="player.ready ? 'ready' : 'waiting'">{{ player.ready ? 'Ready' : 'Waiting' }}</span></div>
            </div>
          </div>
          <footer>{{ faction.players.length }} shown · expandable squad groups proposed</footer>
        </article>
      </div>
    </section>

    <section v-else-if="fixture.state === 'live'" class="live-section">
      <div class="section-heading"><div><p class="section-kicker">Observed status presentation</p><h2>{{ fixture.label }}</h2></div><span class="demo-pill">Scores are mock/demo values</span></div>
      <div class="score-grid">
        <article v-for="faction in rankedFactions" :key="faction.id" class="score-card" :style="{ '--faction-color': faction.color }"><span>{{ faction.name }}</span><strong>{{ fixture.scores[faction.id] }}</strong><small>{{ faction.players.filter((player) => player.connected).length }} connected</small></article>
      </div>
      <div class="events window-panel"><div class="window-titlebar"><span>Recent observed events</span><span class="window-titlebar-meta">DEMO</span></div><ol><li v-for="event in fixture.events" :key="event">{{ event }}</li></ol></div>
    </section>

    <section v-else class="results-section">
      <div class="section-heading"><div><p class="section-kicker">No rating or outcome policy implied</p><h2>{{ fixture.label }}</h2></div><span class="demo-pill">Ranks based on mock scores</span></div>
      <div class="result-grid">
        <article v-for="(faction, index) in rankedFactions" :key="faction.id" class="result-card" :style="{ '--faction-color': faction.color }"><span class="place">{{ ['1st', '2nd', '3rd'][index] }}</span><h3>{{ faction.name }}</h3><strong>{{ fixture.scores[faction.id] }}</strong><span>Mock faction score</span></article>
      </div>
      <div class="stat-list window-panel"><div class="window-titlebar"><span>Sample player statistics</span><span class="window-titlebar-meta">PRESENTATION ONLY</span></div><div v-for="faction in rankedFactions" :key="faction.id" class="stat-row"><strong>{{ fixture.stats[faction.id][0] }}</strong><span>{{ faction.name }}</span><span>K {{ fixture.stats[faction.id][1] }} · D {{ fixture.stats[faction.id][2] }} · A {{ fixture.stats[faction.id][3] }}</span></div></div>
    </section>
  </main>
</template>

<style scoped>
.wardogs-demo { width: min(1180px, 100%); margin: 0 auto; padding: clamp(16px, 3vw, 34px); display: grid; gap: 18px; }
.demo-header, .section-heading, .faction-header, .player-card, .stat-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.demo-header { align-items: flex-end; }.demo-header h1, h2, h3, p { margin: 0; }.demo-header h1 { font-family: var(--font-display); font-size: clamp(1.55rem, 3vw, 2.35rem); }.demo-copy { max-width: 700px; margin-top: 7px; color: var(--text-muted); line-height: 1.45; }.fixture-picker { display: grid; gap: 5px; min-width: 220px; color: var(--text-muted); font: 700 .7rem var(--font-mono); text-transform: uppercase; letter-spacing: .06em; }.fixture-picker select { width: 100%; text-transform: none; letter-spacing: normal; font-family: var(--font-body); }
.overview-body { padding: 12px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }.summary-tile strong { font-size: .86rem; line-height: 1.35; }.section-heading { align-items: flex-end; }.section-heading h2 { font-family: var(--font-display); font-size: 1.22rem; }.scale-note, .demo-pill { color: var(--text-muted); font: 700 .68rem var(--font-mono); text-transform: uppercase; letter-spacing: .05em; }.demo-pill { padding: 6px 8px; background: var(--warning-soft); border: 1px solid var(--surface-border); }
.faction-grid, .score-grid, .result-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; }.faction-card, .score-card, .result-card { border: 1px solid color-mix(in srgb, var(--faction-color) 65%, var(--surface-border)); border-top: 5px solid var(--faction-color); background: var(--card-bg); box-shadow: var(--card-shadow); min-width: 0; }.faction-header { padding: 11px 12px; background: color-mix(in srgb, var(--faction-color) 18%, var(--panel-bg-strong)); }.faction-header > div { display: flex; align-items: center; gap: 8px; }.faction-header h3 { font-family: var(--font-display); font-size: 1.05rem; }.faction-header strong { font: 800 .72rem var(--font-mono); }.faction-swatch { width: 10px; height: 10px; background: var(--faction-color); border: 1px solid rgba(0,0,0,.25); }
.roster-list { display: grid; gap: 7px; max-height: 290px; overflow: auto; padding: 9px; }.player-card { padding: 8px; border: 1px solid var(--card-inner-border); background: var(--card-inner-bg); box-shadow: var(--card-inner-shadow); }.player-card strong, .player-card span { display: block; }.player-card strong { font-size: .82rem; }.player-card span { margin-top: 2px; color: var(--text-muted); font-size: .66rem; }.player-card b { color: var(--faction-color); }.player-card.disconnected { opacity: .67; }.player-status { text-align: right; white-space: nowrap; }.player-status .online, .player-status .ready { color: var(--success); }.player-status .offline { color: var(--danger); }.player-status .waiting { color: var(--warning); }.faction-card footer { padding: 8px 11px; border-top: 1px solid var(--surface-border); color: var(--text-muted); font: 700 .62rem var(--font-mono); text-transform: uppercase; }
.live-section, .results-section { display: grid; gap: 13px; }.score-card, .result-card { display: grid; gap: 5px; padding: 17px; }.score-card span, .score-card small, .result-card > span:not(.place) { color: var(--text-muted); font: 700 .66rem var(--font-mono); text-transform: uppercase; letter-spacing: .05em; }.score-card strong, .result-card > strong { color: var(--faction-color); font: 800 clamp(2rem, 5vw, 3rem) var(--font-display); }.events ol { margin: 0; padding: 12px 12px 12px 31px; display: grid; gap: 8px; color: var(--text-muted); font-size: .82rem; }.result-card { min-height: 150px; }.result-card h3 { font-family: var(--font-display); }.place { color: var(--faction-color); font: 800 .85rem var(--font-mono); }.stat-row { padding: 10px 12px; border-bottom: 1px solid var(--surface-border); font-size: .82rem; }.stat-row:last-child { border-bottom: 0; }.stat-row span { color: var(--text-muted); }
@media (max-width: 840px) { .overview-body { grid-template-columns: repeat(2, minmax(0, 1fr)); }.faction-grid, .score-grid, .result-grid { grid-template-columns: 1fr; }.faction-card { max-height: none; } }
@media (max-width: 560px) { .wardogs-demo { padding: 13px; }.demo-header, .section-heading, .player-card, .stat-row { align-items: stretch; flex-direction: column; }.fixture-picker { width: 100%; }.player-status { text-align: left; }.stat-row { gap: 4px; } }
</style>
