import './assets/main.css';
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import { createPinia } from 'pinia';


const app = createApp(App); // Create the app instance
app.use(router, createPinia());
app.mount('#app');
