<script setup lang="ts">
import { NButton, NText, NSpace } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

function goProfile() {
  router.push('/profile')
}

function doLogout() {
  authStore.logout()
  router.replace('/')
}
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <NText tag="span" class="logo" @click="router.push('/dashboard')" style="cursor: pointer">
        ZipMobile
      </NText>
      <NSpace :size="8">
        <NButton size="small" quaternary @click="goProfile">Профиль</NButton>
        <NButton size="small" quaternary @click="doLogout">Выйти</NButton>
      </NSpace>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
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
.logo {
  font-size: 20px;
  font-weight: 700;
}
</style>
