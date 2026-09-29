import type { AgentMessage, ResumeDocument } from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.status === 204 ? (undefined as T) : response.json()
}

export interface AgentSessionResponse {
  session_id: string
  resume_document: ResumeDocument
  messages: AgentMessage[]
}

export function createAgentSession(options: { audience?: ResumeDocument['audience']; target_role?: string; source_resume_id?: string; force_new?: boolean } = {}) {
  return request<AgentSessionResponse>('/api/resume-agent/sessions', {
    method: 'POST',
    body: JSON.stringify({ audience: 'general', force_new: true, ...options }),
  })
}

export function loadAgentSession(sessionId: string) {
  return request<AgentSessionResponse>(`/api/resume-agent/sessions/${sessionId}`)
}

export function updateAgentDocument(sessionId: string, baseVersion: number, document: ResumeDocument) {
  const roots: Array<keyof ResumeDocument> = [
    'title', 'targetRole', 'audience', 'templateId', 'basics', 'education', 'experiences', 'projects',
    'research', 'awards', 'skills', 'languages', 'selfEvaluation', 'sectionOrder', 'formatting',
  ]
  return request<{ resume_document: ResumeDocument }>(`/api/resume-agent/sessions/${sessionId}/document`, {
    method: 'PATCH',
    body: JSON.stringify({
      base_version: baseVersion,
      patches: roots.filter((root) => root !== 'title' && root !== 'targetRole' && root !== 'audience').map((root) => ({
        id: `sync-${String(root)}`,
        op: 'replace',
        path: `/${String(root)}`,
        after: document[root],
      })),
    }),
  })
}

export function updateAgentGoal(sessionId: string, goal: Record<string, unknown>) {
  return request<{ resume_document: ResumeDocument; messages: AgentMessage[] }>(`/api/resume-agent/sessions/${sessionId}/goal`, {
    method: 'PUT', body: JSON.stringify(goal),
  })
}

export async function sendAgentMessage(sessionId: string, message: string, onEvent: (event: string, data: Record<string, unknown>) => void) {
  const response = await fetch(`${API_BASE}/api/resume-agent/sessions/${sessionId}/chat/stream`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }),
  })
  if (!response.ok || !response.body) throw new Error(`Request failed: ${response.status}`)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() || ''
    for (const chunk of chunks) {
      const event = chunk.match(/^event: (.+)$/m)?.[1]
      const data = chunk.match(/^data: (.+)$/m)?.[1]
      if (event && data) onEvent(event, JSON.parse(data))
    }
    if (done) break
  }
}

export async function exportAgent(sessionId: string, format: 'pdf' | 'docx') {
  const response = await fetch(`${API_BASE}/api/resume-agent/sessions/${sessionId}/export/${format}`, { method: 'POST', headers: { 'Content-Type': 'application/json' } })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.blob()
}
