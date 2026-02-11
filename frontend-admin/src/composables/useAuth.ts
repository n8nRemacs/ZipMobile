import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { registerViaTelegram, logout as apiLogout, getProfile } from '../api/auth'
import type { ProfileResponse, RegisterViaTelegramRequest } from '../api/auth'

const user = ref<ProfileResponse | null>(null)
const isAuthenticated = computed(() => !!localStorage.getItem('access_token'))

export function useAuth() {
  const router = useRouter()

  async function loginWithTelegram(telegramUser: any) {
    const data: RegisterViaTelegramRequest = {
      telegram_id: telegramUser.id,
      first_name: telegramUser.first_name,
      username: telegramUser.username,
      last_name: telegramUser.last_name,
      photo_url: telegramUser.photo_url,
      auth_date: telegramUser.auth_date,
      hash: telegramUser.hash,
    }

    const res = await registerViaTelegram(data)

    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('refresh_token', res.refresh_token)

    if (res.is_new_user) {
      router.push('/onboarding')
    } else {
      router.push('/dashboard')
    }
  }

  async function devLogin() {
    const res = await registerViaTelegram({
      telegram_id: 999999999,
      username: 'dev_user',
      first_name: 'Developer',
      last_name: 'Test',
    })
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('refresh_token', res.refresh_token)
    router.push('/dashboard')
  }

  async function logout() {
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      try { await apiLogout(refreshToken) } catch { /* ignore */ }
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
    router.push('/login')
  }

  async function fetchProfile(): Promise<ProfileResponse | null> {
    try {
      const res = await getProfile()
      user.value = res
      return res
    } catch {
      user.value = null
      return null
    }
  }

  return { user, isAuthenticated, loginWithTelegram, devLogin, logout, fetchProfile }
}
