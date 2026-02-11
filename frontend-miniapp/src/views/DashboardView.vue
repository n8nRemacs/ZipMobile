<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NText, NSpace, NSpin, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { getProfile, getBillingV2My } from '../api/auth'
import type { ProfileResponse, BillingV2Summary } from '../api/auth'

const authStore = useAuthStore()

const profile = ref<ProfileResponse | null>(null)
const billing = ref<BillingV2Summary | null>(null)
const loading = ref(true)

function formatLimit(limits: Record<string, number>, key: string): string {
  const val = limits[key]
  if (val === undefined) return ''
  if (val === -1) return 'безлимит'
  return String(val)
}

function planLabel(sub: BillingV2Summary['subscriptions'][0]): string {
  const parts: string[] = []
  for (const [key, val] of Object.entries(sub.limits)) {
    const label = val === -1 ? 'безлимит' : String(val) + '/день'
    parts.push(label)
  }
  return `${sub.plan_name}${parts.length ? ' (' + parts[0] + ')' : ''}`
}

onMounted(async () => {
  try {
    const token = authStore.accessToken!
    const [p, b] = await Promise.all([
      getProfile(token),
      getBillingV2My(token),
    ])
    profile.value = p
    billing.value = b
  } catch {
    // silent fail
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
        <NTag v-if="billing" size="small" type="info" style="margin-top: 8px">
          {{ billing.total_monthly > 0 ? billing.total_monthly + ' ₽/мес' : 'Free' }}
        </NTag>
      </div>

      <NSpace vertical :size="12" style="margin-top: 24px">
        <NCard
          v-for="sub in billing?.subscriptions || []"
          :key="sub.service_slug"
          size="small"
          hoverable
        >
          <template #header>
            <NText>{{ sub.service_name }}</NText>
          </template>
          <NText depth="3">{{ planLabel(sub) }}</NText>
        </NCard>

        <NCard v-if="billing" size="small" hoverable>
          <template #header>
            <NText>Команда</NText>
          </template>
          <NText depth="3">
            {{ billing.seats_used }} / {{ billing.seats_total }} мест
          </NText>
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
