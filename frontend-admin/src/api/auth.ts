const API_BASE = import.meta.env.VITE_API_URL || ''

export interface TelegramLoginData {
  id: number
  first_name: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user_id: string
  tenant_id: string
  is_new: boolean
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

export interface ProfileUpdateData {
  name?: string
  email?: string
}

export interface BillingPlan {
  id: string
  name: string
  price_monthly: number
  max_api_keys: number
  max_sessions: number
  max_sub_users: number
}

export interface BillingCurrentResponse {
  plan: BillingPlan
  usage: {
    api_keys_used: number
    api_keys_limit: number
    sessions_used: number
    sessions_limit: number
    sub_users_used: number
    sub_users_limit: number
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers as Record<string, string> },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const err = new Error(body.detail || `HTTP ${res.status}`) as any
    err.status = res.status
    throw err
  }
  return res.json()
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

export function loginViaTelegram(data: TelegramLoginData): Promise<LoginResponse> {
  return request('/auth/v1/telegram/web-login', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function getProfile(token: string): Promise<ProfileResponse> {
  return request('/auth/v1/profile', {
    headers: authHeaders(token),
  })
}

export function updateProfile(token: string, data: ProfileUpdateData): Promise<ProfileResponse> {
  return request('/auth/v1/profile', {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify(data),
  })
}

export function getBillingCurrent(token: string): Promise<BillingCurrentResponse> {
  return request('/auth/v1/billing/current', {
    headers: authHeaders(token),
  })
}
