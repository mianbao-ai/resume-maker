import type { ResumeDocument } from './types'

export const sampleResume: ResumeDocument = {
  title: '产品设计师简历', targetRole: '产品设计师 · 体验策略', audience: 'general', templateId: 'ats-classic-v1',
  basics: {
    name: '林知夏', headline: '产品设计师 · 体验策略', email: 'zhixia.lin@example.com', phone: '138 0000 0000', location: '上海',
    links: [{ id: 'link-1', label: '主页', url: 'linzhixia.design' }], extras: [],
  },
  experiences: [
    { id: 'exp-1', company: '远山科技', role: '高级产品设计师', startDate: '2022.04', endDate: '至今', bullets: ['负责企业协作产品的核心体验，带领 3 人设计小组完成工作台重构，关键任务完成率提升 28%。', '建立跨端设计系统与评审机制，将设计交付周期缩短 35%。'] },
    { id: 'exp-2', company: '岛屿互动', role: '产品设计师', startDate: '2019.07', endDate: '2022.03', bullets: ['参与从 0 到 1 搭建内容社区，负责创作与增长模块，推动次日留存提升 12%。'] },
  ],
  projects: [{ id: 'project-1', name: '企业工作台 3.0', role: '设计负责人', link: '', bullets: ['通过 20+ 场用户访谈重构信息架构，以角色化首页帮助不同岗位快速抵达高频任务。'] }],
  education: [{ id: 'edu-1', school: '江南大学', degree: '工业设计 · 本科', startDate: '2015.09', endDate: '2019.06', highlights: [] }],
  research: [], awards: [], skills: [{ id: 'skills-1', label: '技能', skills: ['产品策略', '交互设计', 'Figma', '用户研究'] }], languages: [],
  selfEvaluation: '6 年数字产品设计经验，关注复杂业务中的清晰体验。擅长从用户研究到设计落地的完整链路，曾主导多个千万级用户产品的体验升级。',
  sectionOrder: ['education', 'experiences', 'projects', 'research', 'skills', 'awards', 'selfEvaluation'],
  formatting: { accentColor: '#176B5B', entries: {}, inline: {} },
}

export const createId = () => crypto.randomUUID()
