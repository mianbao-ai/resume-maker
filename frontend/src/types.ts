export type Template = 'classic' | 'minimal'
export type SkillLevel = '了解' | '熟悉' | '熟练' | '精通'

export interface PersonalInfo {
  name: string
  title: string
  email: string
  phone: string
  location: string
  website: string
  summary: string
}

export interface Experience {
  id: string
  company: string
  role: string
  start_date: string
  end_date: string
  current: boolean
  description: string
}

export interface Project {
  id: string
  name: string
  role: string
  link: string
  description: string
}

export interface Education {
  id: string
  school: string
  degree: string
  start_date: string
  end_date: string
}

export interface Skill {
  id: string
  name: string
  level: SkillLevel
}

export interface ResumeContent {
  personal: PersonalInfo
  experiences: Experience[]
  projects: Project[]
  education: Education[]
  skills: Skill[]
}

export interface ResumeData {
  title: string
  template: Template
  accent_color: string
  content: ResumeContent
}

export interface SavedResume extends ResumeData {
  id: string
  created_at: string
  updated_at: string
}
