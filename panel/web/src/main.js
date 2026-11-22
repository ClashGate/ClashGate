import './boot.js'
import { createApp } from 'vue'
import './fonts.css'
import './style.css'
import './theme-christmas.css'
import './theme-dark.css'
import App from './App.vue'

createApp(App).mount('#app')
document.documentElement.classList.add('cg-ready')
