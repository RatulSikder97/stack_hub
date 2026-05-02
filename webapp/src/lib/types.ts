// Mirror of the FastAPI response shapes. Keep in sync with scripts/pipeline/web/api.py.

export type PostStatus =
  | 'idea'
  | 'brief'
  | 'drafting'
  | 'ai_tells_pass'
  | 'editing'
  | 'retention_check'
  | 'scheduled'
  | 'published'

export interface PostRecord {
  post_id: string
  working_title: string
  niche: string
  hook_pattern_used: string
  structural_framework_used: string
  status: PostStatus
  publish_date: string | null
  open_loop_resolved: boolean
  ai_tells_check_passed: boolean
  human_edit_completed: boolean
  share_count: number
  open_rate: number
  substack_url: string
  created_at: string
  published_at: string | null
  retention_check_answers: Array<{ question: string; passed: boolean }>
}

export interface StatusInfo {
  provider: string
  model: string
  has_active_provider_key: boolean
  brand_name: string
  cadence_days: number
}

export interface TranslationResult {
  original_text: string
  translated_text: string
  source_language: string
  target_language: string
  needed_translation: boolean
}

export interface BriefResult extends TranslationResult {
  post_id: string
  brief_path: string
  working_title: string
  one_big_idea: string
  why_now: string
  target_hook: string
  target_framework: string
  reader_transformation: string
  forbidden_moves: string[]
  rendered_markdown: string
}

export interface DraftResult {
  post_id: string
  draft_path: string
  text: string
  word_count: number
}

export interface DetectionFlag {
  pattern: string
  snippet: string
  line_approx: number
}
export interface DetectionResult {
  post_id: string
  passed: boolean
  flags: DetectionFlag[]
  detector: string
}

export interface PostDetail {
  post: PostRecord
  brief_text: string | null
  draft_text: string | null
  published_text: string | null
}
