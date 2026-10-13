<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-header">
        <h1 class="app-title text-gradient">AI短视频操作系统</h1>
        <p class="app-subtitle">让不会做短视频的人，也拥有一个AI内容团队</p>
      </div>

      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
      >
        <el-form-item prop="phone">
          <el-input
            v-model="loginForm.phone"
            placeholder="请输入手机号"
            size="large"
            :prefix-icon="Iphone"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            :prefix-icon="ILock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>

        <div class="login-divider"><span>或</span></div>
        <el-button
          size="large"
          class="wechat-btn"
          @click="handleWechatLogin"
        >
          微信登录
        </el-button>

        <div class="login-footer">
          <span class="register-link" @click="goRegister">
            没有账号？去注册
          </span>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Iphone, ILock } from '@/utils/icons'
import { useUserStore } from '@/stores/user'
import { wechatConfig, wechatLoginUrl } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loginForm = reactive({
  phone: '',
  password: '',
})

const loginRules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

const formRef = ref<FormInstance>()
const loading = ref(false)
const wechatEnabled = ref(false)

onMounted(async () => {
  const code = route.query.code
  if (code) {
    // 微信授权回调：用 code 换 token 后跳转
    try {
      await userStore.loginWithWechat(String(code))
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/home'
      router.replace(redirect)
      return
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '微信登录失败')
    }
  }
  try {
    const cfg = await wechatConfig()
    wechatEnabled.value = !!cfg?.enabled
  } catch {
    wechatEnabled.value = false
  }
})

async function handleWechatLogin() {
  if (!wechatEnabled.value) {
    ElMessage.warning('微信登录暂未开通，配置后即可使用')
    return
  }
  try {
    const redirectUri = `${window.location.origin}/login`
    const res = await wechatLoginUrl(redirectUri)
    if (res?.url) window.location.href = res.url
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '微信登录未配置')
  }
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    loading.value = true
    await userStore.login(loginForm.phone, loginForm.password)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/home'
    router.push(redirect)
  } catch (error) {
    console.error('登录失败:', error)
    ElMessage.error((error as any)?.response?.data?.detail || '登录失败，请检查账号或密码')
  } finally {
    loading.value = false
  }
}

function goRegister() {
  router.push('/register')
}
</script>

<style scoped>
.login-page {
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.login-container {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 20px;
  padding: 40px 30px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.app-title {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 10px;
}

.app-subtitle {
  font-size: 14px;
  color: #909399;
}

.login-form {
  margin-top: 30px;
}

.login-btn {
  width: 100%;
  height: 50px;
  font-size: 16px;
  margin-top: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.login-footer {
  text-align: center;
  margin-top: 20px;
}

.login-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 18px 0 12px;
  color: #909399;
  font-size: 13px;
}

.login-divider::before,
.login-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e4e7ed;
}

.wechat-btn {
  width: 100%;
  height: 48px;
  font-size: 15px;
  color: #07c160;
  border-color: #07c160;
}

.wechat-btn:hover {
  color: #fff;
  background: #07c160;
  border-color: #07c160;
}

.register-link {
  color: #667eea;
  cursor: pointer;
  font-size: 14px;
}

.register-link:hover {
  text-decoration: underline;
}
</style>
