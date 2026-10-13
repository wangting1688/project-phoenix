import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 180000,
})

request.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    const res = response.data
    // 业务错误默认弹全局提示；调用方需要自己引导（如缺素材要跳上传页）时，
    // 可在请求配置里传 skipErrorToast: true，避免出现"红字 + 引导弹窗"双重提示。
    const skipToast = (response.config as any)?.skipErrorToast === true
    // 后端存在两种响应格式, 统一在此解包为业务数据:
    //   1) ApiResponse: { code: number, message: string, data: any }
    //   2) 部分模块:    { success: boolean, data: any, message?: string }
    // 通过类型+结构双重判断，避免业务数据包含 code/success 字段时被误判
    if (
      res &&
      typeof res === 'object' &&
      typeof res.code === 'number' &&
      'data' in res
    ) {
      if (res.code === 200) {
        return res.data
      }
      // 把业务码与 data 挂到 error 上：调用方需要靠 data 里的标记做分支
      // （例如 compose 缺素材时后端返回 data.need_footage = true）
      const bizErr = new Error(res.message || '请求失败') as any
      bizErr.code = res.code
      bizErr.data = res.data
      bizErr.apiMessage = res.message
      if (!skipToast) ElMessage.error(res.message || '请求失败')
      return Promise.reject(bizErr)
    }
    if (
      res &&
      typeof res === 'object' &&
      typeof res.success === 'boolean' &&
      'data' in res
    ) {
      if (res.success) {
        return res.data
      }
      const bizErr = new Error(res.message || res.detail || '请求失败') as any
      bizErr.data = res.data
      if (!skipToast) ElMessage.error(res.message || res.detail || '请求失败')
      return Promise.reject(bizErr)
    }
    // 无包装结构 (如直接返回数组/字符串) 原样透传
    return res
  },
  (error) => {
    if (error.response?.status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      router.push({ name: 'Login' })
      ElMessage.error('登录已过期，请重新登录')
    } else {
      ElMessage.error(error.response?.data?.message || error.message || '网络错误')
    }
    return Promise.reject(error)
  }
)

export default request
