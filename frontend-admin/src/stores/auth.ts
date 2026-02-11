import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ProfileResponse } from '../api/auth'
import { getProfile } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<ProfileResponse | null>(null)

  const isAuthenticated = computed(() => !!localStorage.getItem('access_token'))

  async function fetchProfile(): Promise<boolean> {
    const token = localStorage.getItem('access_token')
    if (!token) return false
    try {
      const profile = await getProfile()
      user.value = profile
      return true
    } catch {
      user.value = null
      return false
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
  }

  return {
    user,
    isAuthenticated,
    fetchProfile,
    logout,
  }
})
