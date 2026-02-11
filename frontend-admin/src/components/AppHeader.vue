<script setup lang="ts">
import { NButton, NText, NSpace, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { user, logout } = useAuth()
const message = useMessage()

function showComingSoon() {
  message.info('Скоро')
}

async function doLogout() {
  await logout()
}

function getUserDisplayName(): string {
  if (user.value?.name) return user.value.name
  if (user.value?.telegram_first_name) {
    let name = user.value.telegram_first_name
    if (user.value.telegram_last_name) name += ` ${user.value.telegram_last_name}`
    return name
  }
  return 'Пользователь'
}
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="header-left">
        <NText tag="span" class="logo" @click="router.push('/dashboard')" style="cursor: pointer">
          ZipMobile
        </NText>
        <nav class="nav-links">
          <NButton size="small" text type="primary" @click="router.push('/dashboard')">Дашборд</NButton>
          <NButton size="small" text @click="showComingSoon">Биллинг</NButton>
          <NButton size="small" text @click="showComingSoon">Команда</NButton>
          <NButton size="small" text @click="showComingSoon">API-ключи</NButton>
        </nav>
      </div>
      <NSpace :size="12" align="center">
        <NText depth="2" style="font-size: 13px">{{ getUserDisplayName() }}</NText>
        <NButton size="small" quaternary @click="doLogout">Выйти</NButton>
      </NSpace>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 0 24px;
}
.header-inner {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 24px;
}
.logo {
  font-size: 20px;
  font-weight: 700;
}
.nav-links {
  display: flex;
  gap: 4px;
}
@media (max-width: 640px) {
  .nav-links {
    display: none;
  }
}
</style>
