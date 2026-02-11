<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NText, NSpace, NSpin, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { getProfile, getBillingCurrent } from '../api/auth'
import type { ProfileResponse, BillingCurrentResponse } from '../api/auth'

const authStore = useAuthStore()

const profile = ref<ProfileResponse | null>(null)
const billing = ref<BillingCurrentResponse | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const token = authStore.accessToken!
    const [p, b] = await Promise.all([
      getProfile(token),
      getBillingCurrent(token),
    ])
    profile.value = p
    billing.value = b
  } catch {
    // silent fail — data will be null
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="dashboard-view">
    <div v-if="loading" class="center">
      <NSpin size="large" />
    </div>

    <template v-else-if="profile">
      <div class="user-info">
        <NText tag="h2" style="font-size: 20px; font-weight: 700">
          {{ profile.name || 'ZipMobile' }}
        </NText>
        <NText depth="3" style="display: block; margin-top: 4px">
          {{ profile.phone }}
        </NText>
        <NTag v-if="billing?.plan" size="small" type="info" style="margin-top: 8px">
          {{ billing.plan.name }}
        </NTag>
      </div>

      <NSpace vertical :size="12" style="margin-top: 24px">
        <NCard size="small" hoverable>
          <template #header>
            <NText>Поиск запчастей</NText>
          </template>
          <NText depth="3">Скоро</NText>
        </NCard>

        <NCard size="small" hoverable>
          <template #header>
            <NText>Авито Мессенджер</NText>
          </template>
          <NText depth="3">Скоро</NText>
        </NCard>

        <NCard size="small" hoverable>
          <template #header>
            <NText>API-ключи</NText>
          </template>
          <NText depth="3">
            {{ billing?.usage?.api_keys_used ?? 0 }} / {{ billing?.usage?.api_keys_limit ?? 1 }}
          </NText>
        </NCard>

        <NCard size="small" hoverable>
          <template #header>
            <NText>Команда</NText>
          </template>
          <NText depth="3">Скоро</NText>
        </NCard>

        <NCard size="small">
          <NText depth="3" style="display: block; text-align: center; font-size: 13px">
            Личный кабинет также доступен на app.zipmobile.ru
          </NText>
        </NCard>
      </NSpace>
    </template>
  </div>
</template>

<style scoped>
.dashboard-view {
  padding-top: 8px;
}
.user-info {
  text-align: center;
  padding: 16px 0;
}
.center {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 40vh;
}
</style>
