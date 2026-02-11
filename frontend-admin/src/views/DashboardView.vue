<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NCard, NText, NSpin, NTag, NGrid, NGridItem, NButton, useMessage } from 'naive-ui'
import { useAuth } from '../composables/useAuth'
import { getBillingV2My, getBillingV2Usage } from '../api/auth'
import type { BillingV2Summary, UsageServiceInfo } from '../api/auth'
import AppHeader from '../components/AppHeader.vue'

const { user, fetchProfile } = useAuth()
const message = useMessage()

const billing = ref<BillingV2Summary | null>(null)
const usage = ref<UsageServiceInfo[]>([])
const loading = ref(true)

const icons: Record<string, string> = {
  parts_search: '\u{1F50D}',
  avito_messenger: '\u{1F4AC}',
  api_access: '\u{1F517}',
}

const counterLabels: Record<string, string> = {
  search_queries: 'Запросов сегодня',
  messages_sent: 'Сообщений сегодня',
  api_calls: 'Запросов сегодня',
}

function getUsageForService(slug: string): { key: string; used: number; limit: number | string } | null {
  const svc = usage.value.find(u => u.service_slug === slug)
  if (!svc) return null
  const keys = Object.keys(svc.counters)
  if (!keys.length) return null
  const c = svc.counters[keys[0]]
  return { key: keys[0], used: c.used, limit: c.limit }
}

function getPercent(used: number, limit: number | string): number {
  if (limit === 'unlimited' || limit === -1) return 0
  return Math.min(100, (used / (limit as number)) * 100)
}

function getProgressColor(percent: number): string {
  if (percent >= 90) return '#EF4444'
  if (percent >= 70) return '#EAB308'
  return '#22C55E'
}

function formatUsage(used: number, limit: number | string): string {
  if (limit === 'unlimited' || limit === -1) return `${used} / \u221E`
  return `${used} / ${limit}`
}

function showComingSoon() {
  message.info('Скоро')
}

onMounted(async () => {
  try {
    if (!user.value) {
      await fetchProfile()
    }
    const [b, u] = await Promise.all([
      getBillingV2My(),
      getBillingV2Usage(),
    ])
    billing.value = b
    usage.value = u
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
        <!-- Welcome -->
        <div class="welcome">
          <NText tag="h2" class="welcome-title">
            Добро пожаловать, {{ user?.telegram_first_name || user?.name || 'Пользователь' }}!
          </NText>
          <NText depth="3" class="welcome-sub">
            <template v-if="user?.settings?.company_name">
              {{ user.settings.company_name }} &middot;
            </template>
            План: <NTag size="small" type="info" style="vertical-align: middle">
              {{ billing && billing.total_monthly > 0 ? billing.total_monthly + ' \u20BD/\u043C\u0435\u0441' : 'Free' }}
            </NTag>
          </NText>
        </div>

        <!-- Service cards -->
        <NGrid :cols="3" :x-gap="16" :y-gap="16" responsive="screen" style="margin-top: 24px" cols-s="1" cols-m="2">
          <NGridItem v-for="sub in billing?.subscriptions || []" :key="sub.service_slug">
            <NCard size="small" hoverable class="service-card">
              <div class="sc-header">
                <span class="sc-icon">{{ icons[sub.service_slug] || '\u{1F4E6}' }}</span>
                <NText strong>{{ sub.service_name }}</NText>
              </div>
              <div class="sc-plan">
                <NTag size="tiny" :type="sub.plan_slug === 'free' ? 'default' : 'success'">
                  План: {{ sub.plan_name }}
                </NTag>
              </div>

              <!-- Usage with progress bar -->
              <div class="sc-usage-section" v-if="getUsageForService(sub.service_slug)">
                <NText depth="3" style="font-size: 12px; display: block; margin-bottom: 4px">
                  {{ counterLabels[getUsageForService(sub.service_slug)!.key] || 'Использование' }}
                </NText>
                <div class="progress-row">
                  <div class="progress-bar">
                    <div
                      class="progress-fill"
                      :style="{
                        width: getPercent(getUsageForService(sub.service_slug)!.used, getUsageForService(sub.service_slug)!.limit) + '%',
                        backgroundColor: getProgressColor(getPercent(getUsageForService(sub.service_slug)!.used, getUsageForService(sub.service_slug)!.limit)),
                      }"
                    />
                  </div>
                  <NText depth="3" style="font-size: 12px; white-space: nowrap">
                    {{ formatUsage(getUsageForService(sub.service_slug)!.used, getUsageForService(sub.service_slug)!.limit) }}
                  </NText>
                </div>
                <NText depth="3" style="font-size: 11px; display: block; text-align: right">
                  {{ Math.round(getPercent(getUsageForService(sub.service_slug)!.used, getUsageForService(sub.service_slug)!.limit)) }}%
                </NText>
              </div>
              <div v-else class="sc-usage-section">
                <NText depth="3" style="font-size: 13px">—</NText>
              </div>

              <div class="sc-actions">
                <NButton size="tiny" quaternary disabled>Открыть</NButton>
                <NButton size="tiny" text type="primary" @click="showComingSoon">Улучшить план</NButton>
              </div>
            </NCard>
          </NGridItem>
        </NGrid>

        <!-- Team -->
        <div class="team-row" v-if="billing">
          <div class="team-info">
            <NText style="font-size: 15px">
              <span style="margin-right: 6px">\u{1F465}</span>Команда
            </NText>
            <NText depth="3" style="font-size: 13px">
              Использовано: {{ billing.seats_used }} / {{ billing.seats_total }} мест (Free)
            </NText>
          </div>
          <NButton size="small" text type="primary" @click="showComingSoon">Управление</NButton>
        </div>
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
.welcome-title {
  font-size: 22px;
  font-weight: 700;
}
.welcome-sub {
  display: block;
  margin-top: 6px;
}
.center {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 40vh;
}

.service-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.sc-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sc-icon {
  font-size: 24px;
}
.sc-plan {
  margin-top: 8px;
}
.sc-usage-section {
  margin-top: 12px;
}
.progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-bar {
  flex: 1;
  height: 8px;
  background: #f3f4f6;
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease, background-color 0.3s ease;
  min-width: 0;
}
.sc-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.team-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.team-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
</style>
