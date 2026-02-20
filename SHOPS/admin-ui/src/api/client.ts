import axios from 'axios'
import type {
  ModerationItem,
  ResolveRequest,
  Brand,
  Model,
  PartType,
  Color,
  ShopNormStatus,
  ModerationStats,
  TaskInfo,
} from '../types'

const api = axios.create({
  baseURL: '/api',
})

// --- Нормализация ---

export async function normalizeShop(shopCode: string): Promise<{ task_id: string; total: number }> {
  const { data } = await api.post(`/normalize/shop/${shopCode}`)
  return data
}

export async function getNormalizeStatus(): Promise<ShopNormStatus[]> {
  const { data } = await api.get('/normalize/status')
  return data
}

export async function getTask(taskId: string): Promise<TaskInfo> {
  const { data } = await api.get(`/task/${taskId}`)
  return data
}

// --- Модерация ---

export async function getModerationList(params: {
  entity_type?: string
  shop_code?: string
  limit?: number
  offset?: number
}): Promise<ModerationItem[]> {
  const { data } = await api.get('/moderate', { params })
  return data
}

export async function getModerationItem(id: number): Promise<ModerationItem> {
  const { data } = await api.get(`/moderate/${id}`)
  return data
}

export async function resolveModeration(id: number, req: ResolveRequest): Promise<{ resolved_entity_id: number }> {
  const { data } = await api.post(`/moderate/${id}/resolve`, req)
  return data
}

export async function getModerationStats(): Promise<ModerationStats> {
  const { data } = await api.get('/moderate/stats')
  return data
}

// --- Справочники ---

export async function getBrands(q?: string): Promise<Brand[]> {
  const { data } = await api.get('/dict/brands', { params: q ? { q } : undefined })
  return data
}

export async function getModels(brandId?: number, q?: string): Promise<Model[]> {
  const params: Record<string, unknown> = {}
  if (brandId) params.brand_id = brandId
  if (q) params.q = q
  const { data } = await api.get('/dict/models', { params })
  return data
}

export async function getPartTypes(): Promise<PartType[]> {
  const { data } = await api.get('/dict/part_types')
  return data
}

export async function getColors(): Promise<Color[]> {
  const { data } = await api.get('/dict/colors')
  return data
}
