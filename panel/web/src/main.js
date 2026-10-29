import { createApp } from 'vue'
import '@fontsource/newsreader/600.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import './style.css'
import App from './App.vue'

createApp(App).mount('#app')
document.documentElement.classList.add('cg-ready')
