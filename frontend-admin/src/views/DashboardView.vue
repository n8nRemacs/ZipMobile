<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NText, NSpace, NSpin, NTag, NGrid, NGridItem } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { getBillingCurrent } from '../api/auth'
import type { BillingCurrentResponse } from '../api/auth'
import AppHeader from '../components/AppHeader.vue'

const authStore = useAuthStore()

const billing = ref<BillingCurrentResponse | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    // Fetch profile if not loaded yet
    if (!authStore.user) {
      await authStore.fetchProfile()
    }
    // Fetch billing
    if (authStore.accessToken) {
      billing.value = await getBillingCurrent(authStore.accessToken)
    }
  } catch { /* silent */ }
  finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <AppHeader />
    <div class="dashboard-view">
      <div v-if="loading" class="center">
        <NSpin size="large" />
      </div>

      <template v-else>
        <div class="welcome">
          <NText tag="h2" style="font-size: 22px; font-weight: 700">
            Добро пожаловать, {{ authStore.user?.name || 'Пользователь' }}!
          </NText>
          <NText depth="3" style="display: block; margin-top: 4px">
            <template v-if="authStore.user?.settings?.company_name">
              {{ authStore.user.settings.company_name }}
            </template>
          </NText>
          <NTag v-if="billing?.plan" size="small" type="info" style="margin-top: 8px">
            Тариф: {{ billing.plan.name }}
          </NTag>
        </div>

        <NGrid :cols="2" :x-gap="12" :y-gap="12" style="margin-top: 24px">
          <NGridItem>
            <NCard size="small" hoverable style="height: 100%">
              <template #header>
                <NText>Поиск запчастей</NText>
              </template>
              <NText depth="3">Скоро</NText>
            </NCard>
          </NGridItem>
          <NGridItem>
            <NCard size="small" hoverable style="height: 100%">
              <template #header>
                <NText>Авито Мессенджер</NText>
              </template>
              <NText depth="3">Скоро</NText>
            </NCard>
          </NGridItem>
          <NGridItem>
            <NCard size="small" hoverable style="height: 100%">
              <template #header>
                <NText>API-ключи</NText>
              </template>
              <NText depth="3">
                {{ billing?.usage?.api_keys_used ?? 0 }} / {{ billing?.usage?.api_keys_limit ?? 1 }}
              </NText>
            </NCard>
          </NGridItem>
          <NGridItem>
            <NCard size="small" hoverable style="height: 100%">
              <template #header>
                <NText>Команда</NText>
              </template>
              <NText depth="3">Скоро</NText>
            </NCard>
          </NGridItem>
        </NGrid>

        <NCard size="small" style="margin-top: 16px">
          <NText depth="3" style="display: block; text-align: center; font-size: 13px">
            Также доступно в Telegram — @zipmobile_bot
          </NText>
        </NCard>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dashboard-view {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}
.welcome {
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
