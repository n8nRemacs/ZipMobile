<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NText, NCard, NDivider, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import TelegramLoginButton from '../components/TelegramLoginButton.vue'
import MiniAppQR from '../components/MiniAppQR.vue'

const router = useRouter()
const authStore = useAuthStore()
const message = useMessage()
const loading = ref(false)

async function onTelegramAuth(data: any) {
  console.log('[Landing] Telegram auth data:', data)
  loading.value = true
  try {
    await authStore.loginViaTelegram(data)
    if (authStore.phoneVerified) {
      router.replace('/dashboard')
    } else {
      router.replace('/verify-phone')
    }
  } catch (err: any) {
    console.error('[Landing] login error:', err)
    if (err.status === 404) {
      message.warning('Аккаунт не найден. Зарегистрируйтесь через бота @zipmobile_bot')
    } else {
      message.error(err.message || 'Ошибка входа')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="landing-view">
    <div class="landing-container">
      <div class="hero">
        <NText tag="h1" class="hero-title">ZipMobile</NText>
        <NText depth="3" class="hero-subtitle">Платформа для сервисных центров</NText>
      </div>

      <NCard class="feature-card">
        <NText style="font-size: 15px; line-height: 1.5">
          Поиск запчастей по лучшим ценам от поставщиков
        </NText>
      </NCard>

      <NCard class="login-card">
        <NText tag="h3" style="font-size: 16px; font-weight: 600; margin-bottom: 16px; display: block; text-align: center">
          Войти через Telegram
        </NText>
        <TelegramLoginButton bot-id="8060922295" @auth="onTelegramAuth" />
      </NCard>

      <NDivider>или</NDivider>

      <div class="register-section">
        <NText depth="2" style="font-size: 15px; font-weight: 600; display: block; margin-bottom: 4px">
          Новый пользователь?
        </NText>
        <NText depth="3" style="display: block; margin-bottom: 16px; line-height: 1.5">
          Зарегистрируйтесь в нашем боте:
        </NText>

        <MiniAppQR />

        <NText depth="3" style="display: block; margin-top: 16px; font-size: 13px; line-height: 1.5">
          После регистрации в боте вернитесь сюда и нажмите "Войти через Telegram"
        </NText>
      </div>
    </div>
  </div>
</template>

<style scoped>
.landing-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.landing-container {
  max-width: 480px;
  width: 100%;
}
.hero {
  text-align: center;
  margin-bottom: 32px;
}
.hero-title {
  font-size: 36px;
  font-weight: 800;
}
.hero-subtitle {
  display: block;
  margin-top: 8px;
  font-size: 16px;
}
.feature-card {
  margin-bottom: 24px;
}
.login-card {
  margin-bottom: 0;
}
.register-section {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>
