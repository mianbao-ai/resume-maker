import type { ResumeDocument, Template } from './types'

export const templateToId = (template: Template): ResumeDocument['templateId'] => template === 'classic' ? 'ats-classic-v1' : 'tech-elegant-v1'
export const idToTemplate = (templateId: ResumeDocument['templateId']): Template => templateId === 'ats-classic-v1' ? 'classic' : 'minimal'

type LegacyResume = {
  title?: string; template?: Template; accent_color?: string
  content?: {
    personal?: { name?: string; title?: string; email?: string; phone?: string; location?: string; website?: string; summary?: string }
    experiences?: Array<{ id?: string; company?: string; role?: string; start_date?: string; end_date?: string; current?: boolean; description?: string }>
    projects?: Array<{ id?: string; name?: string; role?: string; link?: string; description?: string }>
    education?: Array<{ id?: string; school?: string; degree?: string; start_date?: string; end_date?: string }>
    skills?: Array<{ name?: string }>
  }
}

export function fromLegacyResume(value: unknown, fallback: ResumeDocument): ResumeDocument {
  const input = value as LegacyResume
  if (!input?.content?.personal) return value as ResumeDocument
  const personal = input.content.personal
  const id = (prefix: string, index: number) => `${prefix}-${index + 1}`
  return {
    ...fallback,
    title: input.title || fallback.title,
    targetRole: personal.title || fallback.targetRole,
    templateId: templateToId(input.template || 'classic'),
    formatting: { ...fallback.formatting, accentColor: input.accent_color || fallback.formatting.accentColor },
    basics: {
      ...fallback.basics, name: personal.name || '', headline: personal.title || '', email: personal.email || '',
      phone: personal.phone || '', location: personal.location || '',
      links: personal.website ? [{ id: 'link-1', label: '主页', url: personal.website }] : [],
    },
    selfEvaluation: personal.summary || '',
    experiences: (input.content.experiences || []).map((item, index) => ({
      id: item.id || id('experience', index), company: item.company || '', role: item.role || '', startDate: item.start_date || '',
      endDate: item.current ? '至今' : item.end_date || '', bullets: (item.description || '').split('\n').filter(Boolean),
    })),
    projects: (input.content.projects || []).map((item, index) => ({
      id: item.id || id('project', index), name: item.name || '', role: item.role || '', link: item.link || '', bullets: (item.description || '').split('\n').filter(Boolean),
    })),
    education: (input.content.education || []).map((item, index) => ({
      id: item.id || id('education', index), school: item.school || '', degree: item.degree || '', startDate: item.start_date || '', endDate: item.end_date || '', highlights: [],
    })),
    skills: [{ id: 'skills-1', label: '技能', skills: (input.content.skills || []).map((item) => item.name || '').filter(Boolean) }],
  }
}
