<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-header">
        <h1 class="app-title text-gradient">AI短视频操作系统</h1>
        <p class="app-subtitle">让不会做短视频的人，也拥有一个AI内容团队</p>
      </div>

      <el-form
        ref="loginForm"
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
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Iphone, ILock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

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

const loginForm = ref<FormInstance>()
const loading = ref(false)

async function handleLogin() {
  if (!loginForm.value) return
  try {
    await loginForm.value.validate()
    loading.value = true
    await userStore.login(loginForm.phone, loginForm.password)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/home'
    router.push(redirect)
  } catch (error) {
    console.error('登录失败:', error)
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

.register-link {
  color: #667eea;
  cursor: pointer;
  font-size: 14px;
}

.register-link:hover {
  text-decoration: underline;
}
</style>
