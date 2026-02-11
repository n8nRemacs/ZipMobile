import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const userId = ref<string | null>(localStorage.getItem('user_id'))
  const tenantId = ref<string | null>(localStorage.getItem('tenant_id'))
  const expiresAt = ref<number>(Number(localStorage.getItem('expires_at') || '0'))
  const phoneVerified = ref<boolean>(localStorage.getItem('phone_verified') === 'true')

  const isAuthenticated = computed(() => {
    return !!accessToken.value && expiresAt.value > Date.now() / 1000
  })

  function setTokens(data: { access_token: string; refresh_token: string; expires_in: number; user_id: string; tenant_id: string }) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    userId.value = data.user_id
    tenantId.value = data.tenant_id
    expiresAt.value = Math.floor(Date.now() / 1000) + data.expires_in

    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('user_id', data.user_id)
    localStorage.setItem('tenant_id', data.tenant_id)
    localStorage.setItem('expires_at', String(expiresAt.value))
  }

  function clearTokens() {
    accessToken.value = null
    refreshToken.value = null
    userId.value = null
    tenantId.value = null
    expiresAt.value = 0

    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('tenant_id')
    localStorage.removeItem('expires_at')
    localStorage.removeItem('phone_verified')
  }

  async function autoLogin(initData: string): Promise<boolean> {
    try {
      console.log('[AuthStore] autoLogin calling API...')
      const res = await authApi.autoLogin(initData)
      console.log('[AuthStore] autoLogin response:', { authenticated: res.authenticated })
      if (res.authenticated && res.access_token) {
        setTokens({
          access_token: res.access_token,
          refresh_token: res.refresh_token!,
          expires_in: res.expires_in!,
          user_id: res.user_id!,
          tenant_id: res.tenant_id!,
        })
        phoneVerified.value = res.phone_verified ?? false
        localStorage.setItem('phone_verified', String(phoneVerified.value))
        return true
      }
      clearTokens()
      return false
    } catch (err) {
      console.error('[AuthStore] autoLogin error:', err)
      clearTokens()
      return false
    }
  }

  async function registerUser(data: authApi.RegisterData): Promise<void> {
    console.log('[AuthStore] registerUser calling API...', { phone: data.phone, name: data.name })
    const res = await authApi.register(data)
    console.log('[AuthStore] registerUser success:', { user_id: res.user_id, tenant_id: res.tenant_id })
    setTokens({
      access_token: res.access_token,
      refresh_token: res.refresh_token,
      expires_in: res.expires_in,
      user_id: res.user_id,
      tenant_id: res.tenant_id,
    })
  }

  async function updateAndLogin(data: authApi.UpdateAndLoginData): Promise<void> {
    console.log('[AuthStore] updateAndLogin calling API...')
    const res = await authApi.updateAndLogin(data)
    console.log('[AuthStore] updateAndLogin success:', { user_id: res.user_id })
    setTokens({
      access_token: res.access_token,
      refresh_token: res.refresh_token,
      expires_in: res.expires_in,
      user_id: res.user_id,
      tenant_id: res.tenant_id,
    })
  }

  return {
    accessToken,
    refreshToken,
    userId,
    tenantId,
    phoneVerified,
    isAuthenticated,
    setTokens,
    clearTokens,
    autoLogin,
    registerUser,
    updateAndLogin,
  }
})
