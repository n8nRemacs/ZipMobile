<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider, darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import { computed, onMounted } from 'vue'
import { useTelegram } from './composables/useTelegram'

const { ready, expand, webApp } = useTelegram()

const isDark = computed(() => webApp?.colorScheme === 'dark')
const theme = computed(() => isDark.value ? darkTheme : null)

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2196F3',
    primaryColorHover: '#1976D2',
    primaryColorPressed: '#0D47A1',
    borderRadius: '12px',
  },
}

onMounted(() => {
  ready()
  expand()
})
</script>

<template>
  <NConfigProvider :theme="theme" :theme-overrides="themeOverrides">
    <NMessageProvider>
      <NDialogProvider>
        <router-view />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--tg-theme-bg-color, #ffffff);
  color: var(--tg-theme-text-color, #000000);
  min-height: 100vh;
}
#app {
  padding: 16px;
  max-width: 480px;
  margin: 0 auto;
}
</style>
