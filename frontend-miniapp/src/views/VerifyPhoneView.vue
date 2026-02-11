<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NText, NSpace, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useTelegram } from '../composables/useTelegram'
import { getSharedPhone } from '../api/auth'

const router = useRouter()
const authStore = useAuthStore()
const message = useMessage()
const { getInitData, requestContact, hapticFeedback } = useTelegram()

const loading = ref(false)

function canonicalDigits(raw: string): string {
  let digits = raw.replace(/\D/g, '')
  if (digits.length === 11 && digits.startsWith('8')) {
    digits = '7' + digits.slice(1)
  }
  return digits
}

function formatPhone(raw: string): string {
  return `+${canonicalDigits(raw)}`
}

async function handleVerify() {
  loading.value = true
  let phone: string | null = null

  // Step 1: requestContact
  try {
    const contact = await requestContact()
    phone = formatPhone(contact.phone_number)
  } catch (err: any) {
    if (err.message?.includes('cancelled') || err.message?.includes('denied')) {
      loading.value = false
      message.warning('Для подтверждения необходимо поделиться номером')
      return
    }
    // Fallback: get from bot updates
    try {
      const initData = getInitData()
      await new Promise(r => setTimeout(r, 1500))
      const botPhone = await getSharedPhone(initData)
      if (botPhone) phone = formatPhone(botPhone)
    } catch { /* ignore */ }
  }

  if (!phone) {
    loading.value = false
    message.error('Не удалось получить номер из Telegram')
    return
  }

  // Step 2: Update profile with verified phone
  try {
    const initData = getInitData()
    await authStore.updateAndLogin({
      init_data: initData,
      phone,
    })
    hapticFeedback('success')
    message.success('Номер подтверждён!')
    router.replace('/dashboard')
  } catch (err: any) {
    message.error(err.message || 'Ошибка')
  } finally {
    loading.value = false
  }
}

function handleSkip() {
  router.replace('/dashboard')
}
</script>

<template>
  <div class="verify-view">
    <div class="header">
      <NText tag="h1" style="font-size: 24px; font-weight: 700">ZipMobile</NText>
    </div>

    <NSpace vertical :size="16" style="margin-top: 24px; text-align: center">
      <NText style="font-size: 18px; font-weight: 600; display: block">
        Подтвердите номер телефона
      </NText>

      <NText depth="3" style="display: block; line-height: 1.5">
        Для полного доступа к платформе подтвердите номер через Telegram.
        Нажмите кнопку ниже — Telegram запросит разрешение.
      </NText>

      <NButton
        type="primary"
        block
        strong
        size="large"
        :loading="loading"
        @click="handleVerify"
      >
        Подтвердить номер
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
</template>

<style scoped>
.verify-view {
  padding-top: 8px;
}
.header {
  text-align: center;
  padding: 16px 0;
}
</style>
