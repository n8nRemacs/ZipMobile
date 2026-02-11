<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NInput, NText, NSpace, NSpin, NTag, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import AppHeader from '../components/AppHeader.vue'

const router = useRouter()
const authStore = useAuthStore()
const message = useMessage()

const loading = ref(true)
const saving = ref(false)
const name = ref('')
const email = ref('')

onMounted(async () => {
  if (!authStore.user) {
    await authStore.fetchProfile()
  }
  if (authStore.user) {
    name.value = authStore.user.name || ''
    email.value = authStore.user.email || ''
  }
  loading.value = false
})

async function handleSave() {
  saving.value = true
  try {
    await authStore.updateProfile({
      name: name.value.trim() || undefined,
      email: email.value.trim() || undefined,
    })
    message.success('Сохранено')
  } catch (err: any) {
    message.error(err.message || 'Ошибка сохранения')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <AppHeader />
    <div class="profile-view">
      <div class="profile-header">
        <NButton text @click="router.push('/dashboard')">&#8592; Назад</NButton>
        <NText tag="h2" style="font-size: 20px; font-weight: 700">Профиль</NText>
      </div>

      <div v-if="loading" class="center">
        <NSpin size="large" />
      </div>

      <template v-else-if="authStore.user">
        <NSpace vertical :size="20" style="margin-top: 24px">
          <div>
            <NText depth="3" class="label">Ваше имя</NText>
            <NInput v-model:value="name" placeholder="Имя" :maxlength="200" />
          </div>

          <div>
            <NText depth="3" class="label">Телефон</NText>
            <div style="display: flex; align-items: center; gap: 8px">
              <NText>{{ authStore.user.phone || 'Не указан' }}</NText>
              <NTag v-if="authStore.user.phone_verified" size="small" type="success">подтверждён</NTag>
              <NTag v-else size="small" type="warning">не подтверждён</NTag>
            </div>
          </div>

          <div>
            <NText depth="3" class="label">Telegram</NText>
            <NText>{{ authStore.user.telegram_username ? `@${authStore.user.telegram_username}` : 'Привязан' }}</NText>
          </div>

          <div>
            <NText depth="3" class="label">Email</NText>
            <NInput v-model:value="email" placeholder="email@example.com" :maxlength="200" />
          </div>

          <div>
            <NText depth="3" class="label">Роль</NText>
            <NTag size="small">{{ authStore.user.role }}</NTag>
          </div>

          <div v-if="authStore.user.available_channels?.length">
            <NText depth="3" class="label">Каналы связи</NText>
            <NSpace :size="4">
              <NTag v-for="ch in authStore.user.available_channels" :key="ch" size="small">{{ ch }}</NTag>
            </NSpace>
          </div>

          <NButton
            type="primary"
            block
            strong
            size="large"
            :loading="saving"
            @click="handleSave"
          >
            Сохранить изменения
          </NButton>
        </NSpace>
      </template>
    </div>
  </div>
</template>

<style scoped>
.profile-view {
  max-width: 600px;
  margin: 0 auto;
  padding: 24px;
}
.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
}
.label {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
}
.center {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 40vh;
}
</style>
