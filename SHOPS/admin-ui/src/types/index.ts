export interface ModerationItem {
  id: number
  entity_type: 'brand' | 'model' | 'part_type' | 'color'
  proposed_name: string
  proposed_data: Record<string, unknown> | null
  source_article: string | null
  source_name: string | null
  source_shop: string | null
  ai_confidence: number | null
  ai_reasoning: string | null
  status: 'pending' | 'resolved'
  resolution: Record<string, unknown> | null
  resolved_entity_id: number | null
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

export interface ResolveRequest {
  existing_id?: number | null
  create_new?: boolean
  new_name?: string | null
  new_data?: Record<string, unknown> | null
  reviewed_by?: string
}

export interface Brand {
  id: number
  name: string
}

export interface Model {
  id: number
  name: string
  brand_id: number
}

export interface PartType {
  id: number
  name: string
}

export interface Color {
  id: number
  name: string
}

export interface ShopNormStatus {
  shop_code: string
  shop_name: string
  total: number
  normalized: number
  pending: number
}

export interface ModerationStats {
  [entityType: string]: {
    [status: string]: number
  }
}

export interface TaskInfo {
  task_id: string
  task_type: string
  status: string
  progress: Record<string, unknown> | null
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}
