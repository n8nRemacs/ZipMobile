const API_BASE = import.meta.env.VITE_API_URL || ''

interface AutoLoginResponse {
  authenticated: boolean
  access_token?: string
  refresh_token?: string
  token_type?: string
  expires_in?: number
  user_id?: string
  tenant_id?: string
  phone_verified?: boolean
}

interface RegisterResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user_id: string
  tenant_id: string
  is_new: boolean
}

interface RegisterData {
  init_data: string
  phone: string
  telegram_phone?: string
  name: string
  company_name: string
  city: string
  address?: string
  available_channels: string[]
  preferred_channel: string
}

interface ExistingUserData {
  user_id: string
  tenant_id: string
  name: string | null
  phone: string | null
  company_name: string | null
  city: string | null
  address: string | null
  available_channels: string[]
  preferred_channel: string
}

interface ExistingUserResponse {
  detail: string
  existing_user: ExistingUserData
}

interface UpdateAndLoginData {
  init_data: string
  phone?: string
  telegram_phone?: string
  name?: string
  company_name?: string
  city?: string
  address?: string
  available_channels?: string[]
  preferred_channel?: string
}

interface ProfileResponse {
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
}

interface BillingCurrentResponse {
  plan: {
    id: string
    name: string
    price_monthly: number
    max_api_keys: number
    max_sessions: number
    max_sub_users: number
  }
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
  console.log(`[API] ${options.method || 'GET'} ${url}`)
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers as Record<string, string> },
    ...options,
  })
  console.log(`[API] ${path} → ${res.status}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    console.error(`[API] ${path} error:`, body)
    // For 409 with existing_user, throw the full body
    if (res.status === 409 && body.existing_user) {
      const err = new Error(body.detail || 'already_registered') as any
      err.status = 409
      err.existingUser = body.existing_user as ExistingUserData
      throw err
    }
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export function autoLogin(initData: string): Promise<AutoLoginResponse> {
  return request('/auth/v1/telegram/auto-login', {
    method: 'POST',
    body: JSON.stringify({ init_data: initData }),
  })
}

export function register(data: RegisterData): Promise<RegisterResponse> {
  return request('/auth/v1/telegram/register', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateAndLogin(data: UpdateAndLoginData): Promise<RegisterResponse> {
  return request('/auth/v1/telegram/update-and-login', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getSharedPhone(initData: string): Promise<string | null> {
  const res = await request<{ phone: string | null }>('/auth/v1/telegram/get-shared-phone', {
    method: 'POST',
    body: JSON.stringify({ init_data: initData }),
  })
  return res.phone
}

export function getProfile(accessToken: string): Promise<ProfileResponse> {
  return request('/auth/v1/profile', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
}

export function getBillingCurrent(accessToken: string): Promise<BillingCurrentResponse> {
  return request('/auth/v1/billing/current', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
}

// Billing V2

export interface BillingV2Subscription {
  service_slug: string
  service_name: string
  plan_slug: string
  plan_name: string
  price_monthly: number
  limits: Record<string, number>
  status: string
}

export interface BillingV2SeatPackage {
  id: string
  slug: string
  name: string
  max_seats: number
  price_monthly: number
  price_per_seat: number | null
}

export interface BillingV2Summary {
  subscriptions: BillingV2Subscription[]
  seat_package: BillingV2SeatPackage | null
  seats_used: number
  seats_total: number
  total_monthly: number
}

export function getBillingV2My(accessToken: string): Promise<BillingV2Summary> {
  return request('/auth/v1/billing/v2/my', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
}

export type {
  AutoLoginResponse, RegisterResponse, RegisterData,
  ExistingUserData, ExistingUserResponse, UpdateAndLoginData,
  ProfileResponse, BillingCurrentResponse,
}
