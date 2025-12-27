import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// Element Plus UI
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

// Motion for animations
import { MotionPlugin } from '@vueuse/motion'

// Global styles
import './style.css'

const app = createApp(App)
app.use(router)
app.use(ElementPlus)
app.use(MotionPlugin)
app.mount('#app')
