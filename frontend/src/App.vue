<script setup>
import { ref } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { Moon, Sunny, DataAnalysis, HomeFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { login, logout, me, register, getCaptcha } from './api'

const router = useRouter()

const isDark = ref(false)
function toggleTheme() {
  isDark.value = !isDark.value
  const root = document.documentElement
  if (isDark.value) root.classList.add('dark')
  else root.classList.remove('dark')
}

// 登录状态
const authed = ref(false)
const username = ref('')
const loginDialog = ref(false)
const registerDialog = ref(false)
const form = ref({ username: '', password: '', captcha: '', captcha_id: '', captcha_img: '' })
const regForm = ref({ username: '', email: '', password: '', captcha: '', captcha_id: '', captcha_img: '' })

async function refreshAuth(){
  try{
    const res = await me()
    authed.value = !!res?.data?.authenticated
    username.value = res?.data?.username || ''
  }catch{
    authed.value = false; username.value=''
  }
}

async function refreshLoginCaptcha(){
  try{
    const res = await getCaptcha()
    form.value.captcha_id = res.data.captcha_id
    form.value.captcha_img = res.data.image
  }catch(e){
    console.error(e)
    ElMessage.error('获取验证码失败')
  }
}

async function refreshRegisterCaptcha(){
  try{
    const res = await getCaptcha()
    regForm.value.captcha_id = res.data.captcha_id
    regForm.value.captcha_img = res.data.image
  }catch(e){
    console.error(e)
    ElMessage.error('获取验证码失败')
  }
}

async function doLogin(){
  if(!form.value.username || !form.value.password || !form.value.captcha){ 
    ElMessage.warning('请输入账号、密码和验证码'); 
    return 
  }
  try{
    await login(form.value.username, form.value.password, form.value.captcha_id, form.value.captcha)
    ElMessage.success('登录成功')
    loginDialog.value = false
    form.value = { username:'', password:'', captcha:'', captcha_id:'', captcha_img:'' }
    await refreshAuth()
    window.dispatchEvent(new CustomEvent('auth-changed', { detail:{ authenticated: authed.value } }))
  }catch(e){
    ElMessage.error(e?.response?.data?.error || '登录失败')
    refreshLoginCaptcha()
  }
}

async function doLogout(){
  try{
    await logout()
    ElMessage.success('已退出')
    await refreshAuth()
    window.dispatchEvent(new CustomEvent('auth-changed', { detail:{ authenticated: authed.value } }))
  }catch{
    // 忽略
  }
}

async function doRegister(){
  if(!regForm.value.username || !regForm.value.password || !regForm.value.captcha){
    ElMessage.warning('请输入用户名、密码和验证码')
    return
  }
  try{
    await register(regForm.value.username, regForm.value.email, regForm.value.password, regForm.value.captcha_id, regForm.value.captcha)
    ElMessage.success('注册并登录成功')
    registerDialog.value = false
    regForm.value = { username:'', email:'', password:'', captcha:'', captcha_id:'', captcha_img:'' }
    await refreshAuth()
    window.dispatchEvent(new CustomEvent('auth-changed', { detail:{ authenticated: authed.value } }))
  }catch(e){
    ElMessage.error(e?.response?.data?.error || '注册失败')
    refreshRegisterCaptcha()
  }
}

refreshAuth()
</script>

<template>
  <div class="app-wrap">
    <div class="bg-gradient" aria-hidden="true" />

    <header class="app-header" v-motion :initial="{y:-8, opacity:0}" :enter="{y:0, opacity:1}">
      <div class="brand">
        <img src="/vite.svg" alt="logo" />
        <span>ShortURL</span>
      </div>
      <nav class="nav">
        <RouterLink to="/" class="link"><el-icon><HomeFilled /></el-icon><span>首页</span></RouterLink>
        <RouterLink to="/analytics" class="link"><el-icon><DataAnalysis /></el-icon><span>分析</span></RouterLink>
        <el-button circle @click="toggleTheme" class="theme-btn">
          <el-icon v-if="!isDark"><Moon /></el-icon>
          <el-icon v-else><Sunny /></el-icon>
        </el-button>
        <el-divider direction="vertical" />
        <template v-if="authed">
          <span style="margin-right:8px">👋 {{ username }}</span>
          <el-button size="small" @click="doLogout">退出</el-button>
        </template>
        <template v-else>
          <el-button size="small" type="primary" @click="loginDialog=true; refreshLoginCaptcha()">登录</el-button>
          <el-button size="small" @click="registerDialog=true; refreshRegisterCaptcha()">注册</el-button>
        </template>
      </nav>
    </header>

    <main class="app-main">
      <RouterView v-slot="{ Component }">
        <transition name="fade-slide" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
    </main>

    <footer class="app-footer">
      <span>Made with Vue 3 · Element Plus · ECharts</span>
    </footer>

    <!-- 登录对话框 -->
    <el-dialog v-model="loginDialog" title="登录" width="420px" append-to-body :align-center="true">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="验证码">
          <div style="display:flex; align-items:center; gap:8px;">
            <el-input
              v-model="form.captcha"
              placeholder="请输入验证码"
              style="flex:1;"
            />
            <img
              v-if="form.captcha_img"
              :src="form.captcha_img"
              alt="验证码"
              style="height:32px; cursor:pointer; border-radius:4px; border:1px solid var(--el-border-color);"
              @click="refreshLoginCaptcha"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="loginDialog=false">取消</el-button>
        <el-button type="primary" @click="doLogin">登录</el-button>
      </template>
    </el-dialog>

    <!-- 注册对话框 -->
    <el-dialog v-model="registerDialog" title="注册" width="420px" append-to-body :align-center="true">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="regForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱（可选）">
          <el-input v-model="regForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="regForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="验证码">
          <div style="display:flex; align-items:center; gap:8px;">
            <el-input
              v-model="regForm.captcha"
              placeholder="请输入验证码"
              style="flex:1;"
            />
            <img
              v-if="regForm.captcha_img"
              :src="regForm.captcha_img"
              alt="验证码"
              style="height:32px; cursor:pointer; border-radius:4px; border:1px solid var(--el-border-color);"
              @click="refreshRegisterCaptcha"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerDialog=false">取消</el-button>
        <el-button type="primary" @click="doRegister">注册</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style>
:root { --bg1: #0ea5e9; --bg2: #8b5cf6; }
html, body, #app { height: 100%; }
.app-wrap { min-height: 100%; position: relative; }
.bg-gradient { position: fixed; inset: -20% -10% auto -10%; height: 380px; filter: blur(70px); background: radial-gradient(50% 50% at 50% 50%, var(--bg1) 0%, rgba(14,165,233,0.2) 60%, transparent 100%), radial-gradient(50% 50% at 60% 40%, var(--bg2) 0%, rgba(139,92,246,0.2) 60%, transparent 100%); pointer-events: none; opacity: .7; }
.app-header { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; backdrop-filter: blur(10px); background: color-mix(in oklab, white 70%, transparent); border-bottom: 1px solid rgba(0,0,0,.06); }
.dark .app-header { background: color-mix(in oklab, #111827 60%, transparent); border-color: rgba(255,255,255,.06); }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 18px; }
.brand img { width: 24px; height: 24px; }
.nav { display: flex; align-items: center; gap: 10px; }
.nav .link { display: inline-flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 8px; color: var(--el-text-color-primary); }
.nav .link.router-link-active { background: color-mix(in oklab, var(--el-color-primary) 16%, transparent); color: var(--el-color-primary); }
.theme-btn { margin-left: 6px; }
.app-main { max-width: 1200px; margin: 16px auto; padding: 0 16px; }
.app-footer { text-align: center; padding: 24px 0 40px; color: var(--el-text-color-secondary); }

/* page transition */
.fade-slide-enter-active, .fade-slide-leave-active { transition: all .22s ease; }
.fade-slide-enter-from { opacity: 0; transform: translateY(6px); }
.fade-slide-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
