<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NText, NSpace, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import MiniAppQR from '../components/MiniAppQR.vue'

const router = useRouter()
const authStore = useAuthStore()
const message = useMessage()
const checking = ref(false)

async function handleCheck() {
  checking.value = true
  try {
    await authStore.fetchProfile()
    if (authStore.phoneVerified) {
      message.success('Номер подтверждён!')
      router.replace('/dashboard')
    } else {
      message.info('Номер ещё не подтверждён. Поделитесь номером в боте и попробуйте снова.')
    }
  } catch (err: any) {
    message.error(err.message || 'Ошибка')
  } finally {
    checking.value = false
  }
}

function handleSkip() {
  // Allow access but mark phone as not verified (bypass router guard)
  authStore.phoneVerified = true
  localStorage.setItem('phone_verified', 'true')
  router.replace('/dashboard')
}
</script>

<template>
  <div class="verify-view">
    <div class="verify-container">
      <NText tag="h1" style="font-size: 24px; font-weight: 700; text-align: center; display: block">
        Подтвердите номер телефона
      </NText>

      <NSpace vertical :size="16" style="margin-top: 24px; text-align: center">
        <NText depth="3" style="display: block; line-height: 1.5">
          Для полного доступа к платформе подтвердите номер через Telegram:
        </NText>

        <div style="display: flex; justify-content: center">
          <MiniAppQR />
        </div>

        <NText depth="3" style="display: block; line-height: 1.5; font-size: 13px">
          Откройте бота, нажмите кнопку Mini App и поделитесь номером телефона.
          После подтверждения нажмите кнопку ниже.
        </NText>

        <NButton
          type="primary"
          block
          strong
          size="large"
          :loading="checking"
          @click="handleCheck"
        >
          Проверить подтверждение
        </NButton>

        <NButton
          block
          quaternary
          size="large"
          @click="handleSkip"
        >
          Пропустить (ограниченный доступ)
        </NButton>
      </NSpace>
    </div>
  </div>
</template>

<style scoped>
.verify-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.verify-container {
  max-width: 480px;
  width: 100%;
}
</style>
