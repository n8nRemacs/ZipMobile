<script setup lang="ts">
import { computed } from 'vue'
import { NText, NButton, NDivider, useMessage } from 'naive-ui'
import { useAuth } from '../composables/useAuth'
import TelegramLoginButton from '../components/TelegramLoginButton.vue'

const { loginWithTelegram, devLogin } = useAuth()
const message = useMessage()

const isLocalhost = computed(() => {
  const h = window.location.hostname
  return h === 'localhost' || h === '127.0.0.1'
})

async function onTelegramAuth(data: any) {
  try {
    await loginWithTelegram(data)
  } catch (err: any) {
    message.error(err.message || 'Ошибка авторизации')
  }
}

async function onDevLogin() {
  try {
    await devLogin()
  } catch (err: any) {
    message.error(err.message || 'Ошибка входа')
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-container">
      <!-- Header -->
      <div class="hero">
        <NText tag="h1" class="hero-title">ZipMobile</NText>
        <NText depth="3" class="hero-subtitle">Платформа для сервисных центров</NText>
      </div>

      <div class="card">
        <!-- Mode A: Production — Telegram Widget -->
        <template v-if="!isLocalhost">
          <div class="telegram-section">
            <TelegramLoginButton bot-id="zipmobile_bot" @auth="onTelegramAuth" />
          </div>

          <NText depth="3" class="hint-text">
            Нажмите кнопку выше — вам придёт запрос подтверждения в Telegram.
            Аккаунт создастся автоматически.
          </NText>

          <NDivider />

          <div class="fallback">
            <NText depth="3" style="font-size: 13px">Нет Telegram?</NText>
            <NButton
              text
              type="primary"
              tag="a"
              href="https://telegram.org"
              target="_blank"
              size="small"
            >
              Скачайте: telegram.org
            </NButton>
          </div>
        </template>

        <!-- Mode B: Localhost — Dev Login -->
        <template v-else>
          <div class="dev-notice">
            <NText depth="2" strong style="font-size: 14px">
              Разработка (localhost)
            </NText>
            <NText depth="3" style="font-size: 13px; margin-top: 4px; display: block">
              Telegram Widget недоступен на localhost.
            </NText>
          </div>

          <div class="bot-instructions">
            <NText depth="3" style="font-size: 14px">Войдите через бота:</NText>
            <ol class="steps-list">
              <li>Откройте @zipmobile_bot</li>
              <li>Нажмите /start</li>
              <li>Бот выдаст ссылку для входа</li>
            </ol>
            <NButton
              type="primary"
              tag="a"
              href="https://t.me/zipmobile_bot"
              target="_blank"
              block
              strong
              size="large"
            >
              Открыть бота
            </NButton>
          </div>

          <NDivider>или для тестирования</NDivider>

          <NButton
            block
            size="large"
            @click="onDevLogin"
          >
            Dev Login
          </NButton>
          <NText depth="3" style="font-size: 12px; text-align: center; display: block; margin-top: 6px">
            Вход тестовым пользователем
          </NText>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, #f0f4ff 0%, #f5f5f5 100%);
}
.login-container {
  max-width: 440px;
  width: 100%;
}
.hero {
  text-align: center;
  margin-bottom: 32px;
}
.hero-title {
  font-size: 36px;
  font-weight: 800;
  color: #1a1a2e;
}
.hero-subtitle {
  display: block;
  margin-top: 8px;
  font-size: 16px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 32px 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}
.telegram-section {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}
.hint-text {
  display: block;
  text-align: center;
  font-size: 13px;
  line-height: 1.5;
}
.fallback {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.dev-notice {
  text-align: center;
  padding: 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  margin-bottom: 20px;
}
.bot-instructions {
  margin-bottom: 8px;
}
.steps-list {
  margin: 8px 0 16px 20px;
  padding: 0;
  font-size: 14px;
  color: #6B7280;
  line-height: 1.8;
}
</style>
