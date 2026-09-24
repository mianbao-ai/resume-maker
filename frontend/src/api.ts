import type { ResumeData, SavedResume } from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.status === 204 ? (undefined as T) : response.json()
}

export const createResume = (data: ResumeData) =>
  request<SavedResume>('/api/resumes', { method: 'POST', body: JSON.stringify(data) })

export const updateResume = (id: string, data: ResumeData) =>
  request<SavedResume>(`/api/resumes/${id}`, { method: 'PUT', body: JSON.stringify(data) })
