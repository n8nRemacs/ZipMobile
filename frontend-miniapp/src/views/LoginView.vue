<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NSpin, NText } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useTelegram } from '../composables/useTelegram'

const router = useRouter()
const authStore = useAuthStore()
const { getInitData, isAvailable } = useTelegram()

const loading = ref(true)
const error = ref('')

onMounted(async () => {
  console.log('[Login] mounted, isAvailable:', isAvailable)

  // Telegram WebApp required
  if (!isAvailable) {
    console.log('[Login] Telegram WebApp not available')
    error.value = 'Откройте приложение через Telegram'
    loading.value = false
    return
  }

  const initData = getInitData()
  console.log('[Login] initData length:', initData.length)
  if (!initData) {
    console.log('[Login] no initData, clearing tokens, going to register')
    authStore.clearTokens()
    router.replace('/register')
    return
  }

  // Always verify via auto-login regardless of localStorage state
  const success = await authStore.autoLogin(initData)
  console.log('[Login] autoLogin result:', success, 'phoneVerified:', authStore.phoneVerified)
  if (success) {
    if (authStore.phoneVerified) {
      router.replace('/dashboard')
    } else {
      router.replace('/verify-phone')
    }
  } else {
    // Not registered — clear any stale tokens
    authStore.clearTokens()
    router.replace('/register')
  }
})
</script>

<template>
  <div class="login-view">
    <div v-if="loading" class="center">
      <NSpin size="large" />
      <NText style="margin-top: 16px; display: block">Загрузка...</NText>
    </div>
    <div v-else-if="error" class="center">
      <NText type="error">{{ error }}</NText>
    </div>
  </div>
</template>

<style scoped>
.login-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
.center {
  text-align: center;
}
</style>
