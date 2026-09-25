import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import SquadApp from './SquadApp.vue';
import router from './router';
import { developmentTarget } from './devTarget';
import { mountAfterRouterReady } from './utils/mountAfterRouterReady';



async function start() {
  if (developmentTarget === 'squad') {
    await import('./assets/legacy/squad-baseline.css');
  } else {
    await import('./assets/main.css');
  }

  const app = createApp(developmentTarget === 'squad' ? SquadApp : App);
  app.use(createPinia());
  app.use(router);
  // Resolve the browser's initial URL before App's mount hook bootstraps auth
  // and sockets. Steam callback routes must reach their callback component
  // before an unauthenticated startup can redirect them to /auth.
  await mountAfterRouterReady(app, router, '#app');
}

start();
