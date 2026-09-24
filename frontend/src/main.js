import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import SquadApp from './SquadApp.vue';
import router from './router';
import { developmentTarget } from './devTarget';



async function start() {
  if (developmentTarget === 'squad') {
    await import('./assets/legacy/squad-baseline.css');
  } else {
    await import('./assets/main.css');
  }

  const app = createApp(developmentTarget === 'squad' ? SquadApp : App);
  app.use(createPinia());
  app.use(router);
  app.mount('#app');
}

start();
