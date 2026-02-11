<script setup lang="ts">
import { ref, h } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NInput, NText, NSpace, useMessage, useDialog } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useTelegram } from '../composables/useTelegram'
import type { RegisterData, ExistingUserData } from '../api/auth'
import { getSharedPhone } from '../api/auth'
import ChannelSelector from '../components/ChannelSelector.vue'

const router = useRouter()
const authStore = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const { getInitData, requestContact, hapticFeedback } = useTelegram()

const name = ref('')
const companyName = ref('')
const city = ref('')
const address = ref('')
const channels = ref<string[]>(['telegram'])
const loading = ref(false)
// Flag: true when updating existing profile instead of registering new
const isUpdateMode = ref(false)

/**
 * Strip to canonical digits: remove non-digits, convert leading 8 → 7 for Russian numbers.
 */
function canonicalDigits(raw: string): string {
  let digits = raw.replace(/\D/g, '')
  if (digits.length === 11 && digits.startsWith('8')) {
    digits = '7' + digits.slice(1)
  }
  return digits
}

function formatPhone(raw: string): string {
  const digits = canonicalDigits(raw)
  return `+${digits}`
}

// --- Get phone from Telegram ---

async function getTelegramPhone(): Promise<string | null> {
  // Step 1a: Try requestContact callback
  try {
    console.log('[Register] Step 1a: calling requestContact()...')
    const contact = await requestContact()
    console.log('[Register] Step 1a OK: raw contact =', JSON.stringify(contact))
    const phone = formatPhone(contact.phone_number)
    console.log('[Register] Step 1a OK: phone =', phone)
    return phone
  } catch (contactErr: any) {
    console.warn('[Register] Step 1a FAILED:', contactErr.message)
    if (contactErr.message?.includes('cancelled') || contactErr.message?.includes('denied')) {
      return null // user refused to share
    }
  }

  // Step 1b: Fallback — fetch from bot updates
  console.log('[Register] Step 1b: fetching phone from bot updates...')
  try {
    const initData = getInitData()
    await new Promise(r => setTimeout(r, 1500))
    const botPhone = await getSharedPhone(initData)
    console.log('[Register] Step 1b: botPhone =', botPhone)
    if (botPhone) {
      const phone = formatPhone(botPhone)
      console.log('[Register] Step 1b OK: phone =', phone)
      return phone
    }
  } catch (botErr: any) {
    console.error('[Register] Step 1b error:', botErr.message)
  }

  return null
}

// --- Existing user dialog ---

function showExistingUserDialog(existingUser: ExistingUserData) {
  console.log('[Register] existing user:', existingUser)
  const lines: string[] = []
  if (existingUser.company_name) lines.push(`СЦ: ${existingUser.company_name}`)
  if (existingUser.city) lines.push(`Город: ${existingUser.city}`)
  if (existingUser.address) lines.push(`Адрес: ${existingUser.address}`)
  if (existingUser.phone) lines.push(`Телефон: ${existingUser.phone}`)

  dialog.create({
    title: 'Вы уже зарегистрированы',
    content: () => h('div', [
      ...lines.map(l => h('p', { style: 'margin: 4px 0' }, l)),
      h('p', { style: 'margin-top: 12px' }, 'Ваши данные актуальны?'),
    ]),
    positiveText: 'Да, войти',
    negativeText: 'Обновить данные',
    onPositiveClick: async () => {
      loading.value = true
      try {
        const initData = getInitData()
        const success = await authStore.autoLogin(initData)
        if (success) {
          hapticFeedback('success')
          router.replace('/dashboard')
        } else {
          message.error('Не удалось войти')
        }
      } catch (err: any) {
        message.error(err.message || 'Ошибка входа')
      } finally {
        loading.value = false
      }
    },
    onNegativeClick: () => {
      isUpdateMode.value = true
      name.value = existingUser.name || name.value
      companyName.value = existingUser.company_name || companyName.value
      city.value = existingUser.city || city.value
      address.value = existingUser.address || address.value
      if (existingUser.available_channels?.length) {
        channels.value = existingUser.available_channels
      }
      message.info('Обновите данные и нажмите «Сохранить»')
    },
  })
}

// --- Register / Update ---

async function doRegister(phone: string) {
  const initData = getInitData()
  console.log('[Register] calling API, phone:', phone, 'updateMode:', isUpdateMode.value)

  if (isUpdateMode.value) {
    await authStore.updateAndLogin({
      init_data: initData,
      phone,
      name: name.value.trim(),
      company_name: companyName.value.trim(),
      city: city.value.trim(),
      address: address.value.trim() || undefined,
      available_channels: channels.value,
      preferred_channel: 'telegram',
    })
  } else {
    const data: RegisterData = {
      init_data: initData,
      phone,
      name: name.value.trim(),
      company_name: companyName.value.trim(),
      city: city.value.trim(),
      address: address.value.trim() || undefined,
      available_channels: channels.value,
      preferred_channel: 'telegram',
    }
    await authStore.registerUser(data)
  }

  console.log('[Register] success!')
  hapticFeedback('success')
  router.replace('/dashboard')
}

function handleError(err: any) {
  console.error('[Register] error:', err)
  hapticFeedback('error')

  if (err.status === 409 && err.existingUser) {
    showExistingUserDialog(err.existingUser)
    return
  }

  const detail = err.message || 'Ошибка'
  message.error(detail)
}

async function handleRegister() {
  console.log('[Register] === START ===')
  console.log('[Register] updateMode:', isUpdateMode.value)
  console.log('[Register] fields:', {
    name: name.value,
    companyName: companyName.value, city: city.value, channels: channels.value,
  })

  // Validate form
  if (!name.value.trim()) { message.warning('Введите ваше имя'); return }
  if (!companyName.value.trim()) { message.warning('Введите название сервисного центра'); return }
  if (!city.value.trim()) { message.warning('Введите город'); return }
  if (channels.value.length === 0) { message.warning('Выберите хотя бы один канал'); return }

  loading.value = true

  // Get phone from Telegram
  const tgPhone = await getTelegramPhone()
  console.log('[Register] tgPhone =', tgPhone)

  if (!tgPhone) {
    loading.value = false
    message.warning('Необходимо поделиться номером телефона для регистрации')
    return
  }

  // Register or update
  try {
    await doRegister(tgPhone)
  } catch (err: any) {
    handleError(err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-view">
    <div class="header">
      <NText tag="h1" style="font-size: 24px; font-weight: 700">ZipMobile</NText>
      <NText depth="3" style="display: block; margin-top: 4px">Платформа для мастеров</NText>
    </div>

    <NSpace vertical :size="16" style="margin-top: 24px">
      <div>
        <NText depth="3" style="display: block; margin-bottom: 4px; font-size: 13px">Ваше имя</NText>
        <NInput v-model:value="name" placeholder="Иван Петров" :maxlength="200" />
      </div>

      <div>
        <NText depth="3" style="display: block; margin-bottom: 4px; font-size: 13px">Название сервисного центра</NText>
        <NInput v-model:value="companyName" placeholder="iFixit Москва" :maxlength="200" />
      </div>

      <div>
        <NText depth="3" style="display: block; margin-bottom: 4px; font-size: 13px">Город</NText>
        <NInput v-model:value="city" placeholder="Москва" :maxlength="100" />
      </div>

      <div>
        <NText depth="3" style="display: block; margin-bottom: 4px; font-size: 13px">Адрес (необязательно)</NText>
        <NInput v-model:value="address" placeholder="ул. Ленина, 42" :maxlength="300" />
      </div>

      <div>
        <NText depth="3" style="display: block; margin-bottom: 8px; font-size: 13px">Ваши мессенджеры</NText>
        <ChannelSelector v-model="channels" />
      </div>

      <NButton
        type="primary"
        block
        strong
        size="large"
        :loading="loading"
        @click="handleRegister"
      >
        {{ isUpdateMode ? 'Сохранить и войти' : 'Зарегистрироваться' }}
      </NButton>

      <NText depth="3" style="display: block; text-align: center; font-size: 12px; line-height: 1.4">
        Нажимая кнопку, Telegram запросит подтверждение номера телефона
      </NText>
    </NSpace>
  </div>
</template>

<style scoped>
.register-view {
  padding-top: 8px;
}
.header {
  text-align: center;
  padding: 16px 0;
}
</style>
