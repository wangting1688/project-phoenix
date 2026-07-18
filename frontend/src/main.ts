import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 命令式 API 的样式需手动按需引入（模板组件样式由 ElementPlusResolver 自动处理）
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'

import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
