<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NText, NCard, NSpin, NCheckbox } from 'naive-ui'
import { useAuth } from '../composables/useAuth'
import { getBillingV2Services, getBillingV2My } from '../api/auth'
import type { PlatformServiceInfo, BillingV2Summary } from '../api/auth'

const router = useRouter()
const { user, fetchProfile } = useAuth()

const step = ref(1)
const loading = ref(true)
const services = ref<PlatformServiceInfo[]>([])
const billing = ref<BillingV2Summary | null>(null)
const selectedServices = ref<Set<string>>(new Set())

const icons: Record<string, string> = {
  parts_search: '\u{1F50D}',
  avito_messenger: '\u{1F4AC}',
  api_access: '\u{1F517}',
}

onMounted(async () => {
  try {
    if (!user.value) {
      await fetchProfile()
    }
    const [svcList, billingSummary] = await Promise.all([
      getBillingV2Services(),
      getBillingV2My(),
    ])
    services.value = svcList
    billing.value = billingSummary

    for (const sub of billingSummary.subscriptions) {
      selectedServices.value.add(sub.service_slug)
    }
  } catch { /* silent */ }
  finally {
    loading.value = false
  }
})

function toggleService(slug: string) {
  if (selectedServices.value.has(slug)) {
    selectedServices.value.delete(slug)
  } else {
    selectedServices.value.add(slug)
  }
}

function goToDashboard() {
  router.replace('/dashboard')
}

function getFirstName(): string {
  return user.value?.telegram_first_name || user.value?.name || 'User'
}

function subscribedServiceNames(): string[] {
  if (!billing.value) return []
  return billing.value.subscriptions
    .filter(s => selectedServices.value.has(s.service_slug))
    .map(s => s.service_name)
}
</script>

<template>
  <div class="onboarding-page">
    <div class="onboarding-container">
      <!-- Step indicator -->
      <div class="steps-header">
        <div class="steps">
          <div v-for="s in 3" :key="s" class="step-dot" :class="{ active: s === step, done: s < step }" />
        </div>
        <NText depth="3" style="font-size: 13px">{{ `\u0428\u0430\u0433 ${step} \u0438\u0437 3` }}</NText>
      </div>

      <div v-if="loading" class="center">
        <NSpin size="large" />
      </div>

      <!-- Step 1: Welcome -->
      <Transition name="slide" mode="out-in">
        <div v-if="!loading && step === 1" key="s1" class="step-card">
          <div class="step-icon">&#127881;</div>
          <NText tag="h2" class="step-title">
            {{ `\u0414\u043E\u0431\u0440\u043E \u043F\u043E\u0436\u0430\u043B\u043E\u0432\u0430\u0442\u044C, ${getFirstName()}!` }}
          </NText>
          <NText depth="3" class="step-desc">
            Ваш аккаунт создан. Давайте настроим рабочее пространство.
          </NText>

          <div class="features">
            <NText strong style="display: block; margin-bottom: 8px">Что такое ZipMobile?</NText>
            <div class="feature-item">Поиск запчастей по базе поставщиков</div>
            <div class="feature-item">Управление чатами Авито</div>
            <div class="feature-item">API для интеграции с CRM</div>
          </div>

          <div class="step-actions-right">
            <NButton type="primary" size="large" strong @click="step = 2">
              Далее
            </NButton>
          </div>
        </div>

        <!-- Step 2: Select services -->
        <div v-else-if="!loading && step === 2" key="s2" class="step-card">
          <NText tag="h2" class="step-title">Какие сервисы вам нужны?</NText>
          <NText depth="3" class="step-desc" style="margin-bottom: 20px">
            Можно изменить позже в настройках
          </NText>

          <div class="services-list">
            <NCard
              v-for="svc in services"
              :key="svc.slug"
              size="small"
              hoverable
              class="service-card"
              :class="{ selected: selectedServices.has(svc.slug) }"
              @click="toggleService(svc.slug)"
            >
              <div class="service-row">
                <div class="service-info">
                  <div class="service-icon">{{ icons[svc.slug] || '\u{1F4E6}' }}</div>
                  <div>
                    <NText strong>{{ svc.name }}</NText>
                    <NText depth="3" style="display: block; font-size: 13px; margin-top: 2px">
                      {{ svc.description }}
                    </NText>
                  </div>
                </div>
                <NCheckbox :checked="selectedServices.has(svc.slug)" />
              </div>
              <div class="service-badge">
                {{ selectedServices.has(svc.slug) ? '\u2705 \u041F\u043E\u0434\u043A\u043B\u044E\u0447\u0435\u043D\u043E \u2014 Free' : '\u2610 \u041F\u043E\u0434\u043A\u043B\u044E\u0447\u0438\u0442\u044C \u0431\u0435\u0441\u043F\u043B\u0430\u0442\u043D\u043E' }}
              </div>
            </NCard>
          </div>

          <div class="step-actions">
            <NButton @click="step = 1">Назад</NButton>
            <NButton type="primary" strong @click="step = 3">Далее</NButton>
          </div>
        </div>

        <!-- Step 3: Done -->
        <div v-else-if="!loading && step === 3" key="s3" class="step-card">
          <div class="step-icon">&#9989;</div>
          <NText tag="h2" class="step-title">Всё готово!</NText>

          <div class="summary">
            <div class="summary-row">
              <NText depth="3">Ваш план</NText>
              <NText strong>Free</NText>
            </div>
            <div class="summary-row">
              <NText depth="3">Подключённые сервисы</NText>
              <div>
                <NText v-for="name in subscribedServiceNames()" :key="name" style="display: block; text-align: right" strong>
                  {{ name }}
                </NText>
              </div>
            </div>
            <div class="summary-row">
              <NText depth="3">Команда</NText>
              <NText strong>{{ billing?.seats_total || 1 }} место</NText>
            </div>
          </div>

          <NText depth="3" class="step-desc" style="margin-top: 16px">
            Вы можете обновить план в любое время в разделе "Биллинг".
          </NText>

          <div class="step-actions-center" style="margin-top: 20px">
            <NButton type="primary" size="large" strong @click="goToDashboard">
              Перейти в панель
            </NButton>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.onboarding-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, #f0f4ff 0%, #f5f5f5 100%);
}
.onboarding-container {
  max-width: 520px;
  width: 100%;
}
.steps-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.steps {
  display: flex;
  gap: 8px;
}
.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #d9d9d9;
  transition: all 0.3s;
}
.step-dot.active {
  background: #3B82F6;
  transform: scale(1.2);
}
.step-dot.done {
  background: #22c55e;
}
.step-card {
  background: #fff;
  border-radius: 12px;
  padding: 32px 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  text-align: center;
}
.step-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.step-title {
  font-size: 22px;
  font-weight: 700;
  display: block;
}
.step-desc {
  display: block;
  margin-top: 8px;
  font-size: 15px;
  line-height: 1.5;
}
.features {
  text-align: left;
  margin: 20px 0;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
}
.feature-item {
  position: relative;
  padding-left: 16px;
  font-size: 14px;
  color: #6B7280;
  line-height: 2;
}
.feature-item::before {
  content: '\2014';
  position: absolute;
  left: 0;
}
.services-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: left;
}
.service-card {
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}
.service-card.selected {
  border-color: #3B82F6;
}
.service-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.service-info {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.service-icon {
  font-size: 28px;
  flex-shrink: 0;
}
.service-badge {
  margin-top: 8px;
  font-size: 12px;
  color: #3B82F6;
  font-weight: 500;
}
.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
  gap: 12px;
}
.step-actions-right {
  display: flex;
  justify-content: flex-end;
  margin-top: 24px;
}
.step-actions-center {
  display: flex;
  justify-content: center;
}
.summary {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  background: #f9fafb;
  padding: 16px;
  border-radius: 8px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
}
.center {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 30vh;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
}
.slide-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.slide-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}
</style>
