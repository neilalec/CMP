<script setup>
import { computed } from 'vue';
import { DISCORD_INVITE_URL } from '../constants/links';
import { useQueueStore } from '../stores/queueStore';

const queueStore = useQueueStore();
const serverName = '4K War Server';
const serverStatus = computed(() => queueStore.activeLobbyCount > 0 ? 'being played on' : 'not being played on');
</script>

<template>
  <div class="static-page content-panel page-shell narrow">
    <section class="static-card surface-card">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Squad Comp Matchmaking</span>
      </div>
      <div class="static-body">
        <section class="static-section">
          <h2 class="static-section-title is-large">How it Works</h2>
          <p>
            Join a queue as solo or part of a group, accept the match when queue is filled, you'll then be moved to a lobby to map vote and receive server info. 
          </p>
            <p>Join the server through the Custom Browser in Squad, once enough players have joined or after 10 minutes the match will start.
          </p>
          <p>
            All server commands will happen automatically, including map rotation, team balancing, and match ending.
          </p>
          <p>
            You'll play two rounds on the layer, one for each faction, once the match ends your ELO will be adjusted based on the outcome.
          </p>
          <p>
            You can then queue for another match if you want.
          </p>
        </section>

        <section class="static-section">
          <h2 class="static-section-title is-large">Purpose</h2>
          <p>
          Competitive matchmaking for Squad, similar to other competitive first person shooters.
          <br>
          Queue for and find a match on competitive layers that differ from vanilla layers, they perform better as they disable shadows, and allow more consistently competitive gameplay due to the linearity of AAS, as opposed to RAAS, Invasion etc.
          <br>
          <br>
          If you are a new you are highly encouraged to queue up for a game and take part, you will learn a lot about Squads meta, which is largely overlooked in public games. 
          This is not meant to be the same experience as a scrim or tournament match, as the only time you'll have to prep your team is within staging phase and you'll play with randoms like in pubs, except the players you group with.
          <br>
          <br>
          Feedback and bug reports are highly appreciated, please use the <a class="static-link" :href="DISCORD_INVITE_URL" target="_blank" rel="noopener noreferrer">discord</a> for that.
          <br>
          This is a hobbyist project, so please be patient with the service :)
          </p>
        </section>

        <p class="notice-tile">
          We currently use one server, the <strong>{{ serverName }}</strong>, which is <strong>{{ serverStatus }}</strong> at the moment.
        </p>
      </div>
    </section>
  </div>
</template>
