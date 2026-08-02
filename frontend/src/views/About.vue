<script setup>
import { computed } from 'vue';
import { DISCORD_INVITE_URL } from '../constants/links';
import { useQueueStore } from '../stores/queueStore';

const queueStore = useQueueStore();
const serverName = '4K War Server';
const serverStatus = computed(() => queueStore.activeLobbyCount > 0 ? 'in use' : 'available');
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
            Join a queue as solo or part of a group, accept the match when queue is filled, then you'll move to a lobby to map vote and receive server info. 
          </p>
            <p>You'll then have to join the server through the Custom Browser in Squad, the server info will be within your lobby, once enough players have joined or after 10 minutes the match will start.
          </p>
          <p>
            You'll play one round on the layer, at the end of which the score will save to the results section of this app, and you'll be able to queue for another match if you wish.
          </p>
        </section>

        <section class="static-section">
          <h2 class="static-section-title is-large">Purpose</h2>
          <p>
            To bridge the gap between public games and competitive scrims.
              Players can queue for a match on classic and competitive layers, with other like minded players who want to play in a more competitive setting. 
              <br>Team sizes range from 20v20 to 46v46, which are the formats used in competitive scrims and tournaments.
          </p>
          <p>
            If you are looking for a more challenging experience to Squad this will hopefully be your best option without having to organize your own server and players, such as in scrims.
          </p>
          <p>If you are a new player to competitive Squad you are highly encouraged to queue up for a game and take part, you will learn alot about Squads meta, which is largely overlooked in public games.
            This is not meant to be the same experience as a scrim or tournament match, as the only time you'll have to prep your team is within staging phase and you'll play with randoms like in pubs, except the players you group with
          </p>
          <p>
            Feedback and bug reports are highly appreciated please use the <a class="static-link" :href="DISCORD_INVITE_URL" target="_blank" rel="noopener noreferrer">discord</a> for that
          </p>
          <p>This is a hobbyist project, so please be patient with the service :)</p>
        </section>

        <p class="notice-tile">
          We are currently using one singular server: <strong>{{ serverName }}</strong> and its currently <strong>{{ serverStatus }}</strong>.
        </p>
      </div>
    </section>
  </div>
</template>
