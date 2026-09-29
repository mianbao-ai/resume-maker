export type TemplateId =
  | 'ats-classic-v1'
  | 'tech-elegant-v1'
  | 'modern-sidebar-v1'
  | 'campus-recruiting-v1'

export type Template = 'classic' | 'minimal'
export type SkillLevel = '了解' | '熟悉' | '熟练' | '精通'

export interface ResumeLink { id: string; label: string; url: string }

export interface ResumeBasics {
  name: string
  headline: string
  gender?: string
  email: string
  phone: string
  location: string
  photo?: string
  links: ResumeLink[]
  extras: Array<{ id: string; label: string; value: string }>
}

export interface ResumeExperience {
  id: string
  company: string
  role: string
  startDate: string
  endDate: string
  bullets: string[]
}

export interface ResumeProject { id: string; name: string; role: string; link?: string; bullets: string[] }

export interface ResumeEducation {
  id: string
  school: string
  degree: string
  startDate: string
  endDate: string
  highlights: string[]
}

export interface ResumeSkillGroup { id: string; label: string; skills: string[] }

export interface ResumeDocument {
  id?: string
  title: string
  targetRole: string
  audience: 'hr' | 'graduate_examiner' | 'internship_recruiter' | 'general'
  templateId: TemplateId
  basics: ResumeBasics
  education: ResumeEducation[]
  experiences: ResumeExperience[]
  projects: ResumeProject[]
  research: Array<Record<string, unknown>>
  awards: Array<Record<string, unknown>>
  skills: ResumeSkillGroup[]
  languages: Array<Record<string, unknown>>
  selfEvaluation: string
  sectionOrder: string[]
  formatting: { accentColor: string; entries: Record<string, unknown>; inline: Record<string, unknown> }
}

export interface AgentMessage {
  id: string
  role: 'assistant' | 'user' | 'system'
  content: string
  createdAt?: string
}
