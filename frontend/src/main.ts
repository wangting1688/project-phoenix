import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)

// 注册所有图标组件（同时注册原名和 I 前缀版本，兼容模板中的 <IXxx> 写法）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
  // 仅对首字母大写的导出添加 I 前缀（过滤 default 导出等）
  if (/^[A-Z]/.test(key)) {
    app.component(`I${key}`, component)
  }
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
