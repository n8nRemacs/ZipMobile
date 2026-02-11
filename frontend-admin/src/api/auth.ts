const API_BASE = import.meta.env.VITE_API_URL || ''

// --- Types ---

export interface RegisterViaTelegramRequest {
  telegram_id: number
  username?: string
  first_name: string
  last_name?: string
  photo_url?: string
  auth_date?: number
  hash?: string
}

export interface RegisterViaTelegramResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  is_new_user: boolean
}

export interface ProfileResponse {
  id: string
  tenant_id: string
  phone: string
  email: string | null
  email_verified: boolean
  phone_verified: boolean
  name: string | null
  avatar_url: string | null
  role: string
  settings: Record<string, any>
  created_at: string
  telegram_username?: string | null
  telegram_first_name?: string | null
  telegram_last_name?: string | null
  available_channels?: string[]
  preferred_channel?: string
}

export interface BillingV2Subscription {
  service_slug: string
  service_name: string
  plan_slug: string
  plan_name: string
  price_monthly: number
  limits: Record<string, number>
  status: string
}

export interface BillingV2Summary {
  subscriptions: BillingV2Subscription[]
  seat_package: { id: string; slug: string; name: string; max_seats: number; price_monthly: number } | null
  seats_used: number
  seats_total: number
  total_monthly: number
}

export interface PlatformServiceInfo {
  id: string
  slug: string
  name: string
  description: string | null
  icon: string | null
  plans: { id: string; slug: string; name: string; price_monthly: number; limits: Record<string, number>; features: Record<string, any> }[]
}

export interface UsageCounterInfo {
  used: number
  limit: number | string
}

export interface UsageServiceInfo {
  service_slug: string
  counters: Record<string, UsageCounterInfo>
}

// --- Request helper ---

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }

  const token = localStorage.getItem('access_token')
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(url, { ...options, headers })

  // Auto-refresh on 401
  if (res.status === 401 && token) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`
      const retry = await fetch(url, { ...options, headers })
      if (!retry.ok) {
        const body = await retry.json().catch(() => ({ detail: retry.statusText }))
        throw createApiError(body, retry.status)
      }
      return retry.json()
    } else {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
      throw new Error('Session expired')
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw createApiError(body, res.status)
  }
  return res.json()
}

function createApiError(body: any, status: number): Error & { status: number } {
  const err = new Error(body.detail || `HTTP ${status}`) as any
  err.status = status
  return err
}

let refreshPromise: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise
  refreshPromise = doRefresh()
  const result = await refreshPromise
  refreshPromise = null
  return result
}

async function doRefresh(): Promise<boolean> {
  const rt = localStorage.getItem('refresh_token')
  if (!rt) return false
  try {
    const res = await fetch(`${API_BASE}/auth/v1/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    })
    if (!res.ok) return false
    const data = await res.json()
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    return true
  } catch {
    return false
  }
}

async function publicRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers as Record<string, string> || {}) },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw createApiError(body, res.status)
  }
  return res.json()
}

// --- Auth (public) ---

export function registerViaTelegram(data: RegisterViaTelegramRequest): Promise<RegisterViaTelegramResponse> {
  return publicRequest('/auth/v1/register-via-telegram', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// --- Auth (authenticated) ---

export function logout(refreshToken: string): Promise<{ message: string }> {
  return request('/auth/v1/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
}

export function getProfile(): Promise<ProfileResponse> {
  return request('/auth/v1/profile')
}

// --- Billing V2 ---

export function getBillingV2My(): Promise<BillingV2Summary> {
  return request('/auth/v1/billing/v2/my')
}

export function getBillingV2Services(): Promise<PlatformServiceInfo[]> {
  return publicRequest('/auth/v1/billing/v2/services')
}

export function getBillingV2Usage(): Promise<UsageServiceInfo[]> {
  return request('/auth/v1/billing/v2/usage')
}
