import { toLegacyResume } from './document'
import type { ResumeDocument } from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.status === 204 ? (undefined as T) : response.json()
}

export const createResume = (document: ResumeDocument) =>
  request<{ id: string }>('/api/resumes', { method: 'POST', body: JSON.stringify(toLegacyResume(document)) })

export const updateResume = (id: string, document: ResumeDocument) =>
  request<{ id: string }>(`/api/resumes/${id}`, { method: 'PUT', body: JSON.stringify(toLegacyResume(document)) })
