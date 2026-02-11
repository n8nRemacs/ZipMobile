<script setup lang="ts">
import { onMounted, ref } from 'vue'

const props = defineProps<{
  botId: string
}>()

const emit = defineEmits<{
  auth: [data: any]
}>()

const containerRef = ref<HTMLDivElement>()

onMounted(() => {
  // Register global callback
  ;(window as any).onTelegramAuth = (user: any) => {
    emit('auth', user)
  }

  // Inject Telegram Login Widget script
  const script = document.createElement('script')
  script.src = 'https://telegram.org/js/telegram-widget.js?22'
  script.setAttribute('data-telegram-login', `zipmobile_bot`)
  script.setAttribute('data-size', 'large')
  script.setAttribute('data-radius', '8')
  script.setAttribute('data-onauth', 'onTelegramAuth(user)')
  script.setAttribute('data-request-access', 'write')
  script.async = true

  containerRef.value?.appendChild(script)
})
</script>

<template>
  <div ref="containerRef" class="telegram-login-container"></div>
</template>

<style scoped>
.telegram-login-container {
  display: flex;
  justify-content: center;
  min-height: 40px;
}
</style>
