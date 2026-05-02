// Thin client over /api. All errors throw; rate limits raise RateLimitedError
// with the seconds you should wait before retrying.

import type {
  BriefResult,
  DetectionResult,
  DraftResult,
  PostDetail,
  PostRecord,
  StatusInfo,
  TranslationResult,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export class RateLimitedError extends ApiError {
  retryAfter: number
  constructor(message: string, retryAfter: number) {
    super(message, 429)
    this.name = 'RateLimitedError'
    this.retryAfter = retryAfter
  }
}

async function request<T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: 'same-origin',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const payload = await res.json().catch(() => ({ detail: res.statusText }))
    const message = payload?.detail || `HTTP ${res.status}`
    if (res.status === 429) {
      const retryAfter = parseInt(res.headers.get('Retry-After') || '30', 10)
      throw new RateLimitedError(message, isNaN(retryAfter) ? 30 : retryAfter)
    }
    throw new ApiError(message, res.status)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// ---- Auth + admin types ----

export interface AuthUser {
  username: string
  role: 'admin' | 'user'
}

export interface AdminFile {
  path: string
  category: string
  label: string
  size: number
  modified_at: string
  deletable: boolean
}

export interface AdminFileContent extends AdminFile {
  content: string
}

export interface TranscriptParseResult {
  text: string
  detected_format: 'vtt' | 'srt' | 'text' | 'unknown'
  line_count: number
  word_count: number
  speakers: string[]
}

export type BotState = 'queued' | 'joining' | 'in_call' | 'done' | 'error'

export interface BotStatus {
  bot_id: string
  state: BotState
  raw_status_codes: string[]
  transcript_text: string | null
  error: string | null
}

// ---- Endpoints ----

export const api = {
  // Auth
  login: (username: string, password: string) =>
    request<AuthUser>('POST', '/auth/login', { username, password }),
  logout: () => request<{ ok: boolean }>('POST', '/auth/logout'),
  me: () => request<AuthUser>('GET', '/auth/me'),

  // Admin
  adminListFiles: () => request<AdminFile[]>('GET', '/admin/files'),
  adminReadFile: (path: string) =>
    request<AdminFileContent>('GET', `/admin/files/${path}`),
  adminWriteFile: (path: string, content: string) =>
    request<AdminFile>('PUT', `/admin/files/${path}`, { path, content }),
  adminDeleteFile: (path: string) =>
    request<{ path: string; deleted: boolean }>('DELETE', `/admin/files/${path}`),

  // Meetings
  parseTranscript: (content: string, filename?: string) =>
    request<TranscriptParseResult>('POST', '/meeting/parse', { content, filename }),

  // Real-time meeting bot (Recall.ai)
  createMeetingBot: (meeting_url: string, bot_name?: string) =>
    request<{ bot_id: string }>('POST', '/meeting/bot', { meeting_url, bot_name }),
  getMeetingBot: (botId: string) =>
    request<BotStatus>('GET', `/meeting/bot/${encodeURIComponent(botId)}`),
  leaveMeetingBot: (botId: string) =>
    request<{ bot_id: string; left: boolean }>(
      'DELETE',
      `/meeting/bot/${encodeURIComponent(botId)}`,
    ),

  // Pipeline
  status: () => request<StatusInfo>('GET', '/status'),

  translate: (text: string, target_lang = 'en') =>
    request<TranslationResult>('POST', '/translate', { text, target_lang }),

  brief: (idea: string, target_lang = 'en') =>
    request<BriefResult>('POST', '/brief', { idea, target_lang }),

  draft: (postId: string) =>
    request<DraftResult>('POST', `/draft/${encodeURIComponent(postId)}`),

  detect: (postId: string) =>
    request<DetectionResult>('POST', `/detect/${encodeURIComponent(postId)}`),

  retention: (postId: string) =>
    request<{ post_id: string; human_edit_completed: boolean }>(
      'POST',
      `/retention/${encodeURIComponent(postId)}`,
    ),

  publish: (postId: string, url: string) =>
    request<{ post_id: string; substack_url: string; published_at: string }>(
      'POST',
      `/publish/${encodeURIComponent(postId)}`,
      { url },
    ),

  posts: () => request<{ posts: PostRecord[] }>('GET', '/posts'),

  postDetail: (postId: string) =>
    request<PostDetail>('GET', `/posts/${encodeURIComponent(postId)}`),
}
