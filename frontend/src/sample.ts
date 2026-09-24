import type { ResumeData } from './types'

export const sampleResume: ResumeData = {
  title: '产品设计师简历',
  template: 'classic',
  accent_color: '#176B5B',
  content: {
    personal: {
      name: '林知夏',
      title: '产品设计师 · 体验策略',
      email: 'zhixia.lin@example.com',
      phone: '138 0000 0000',
      location: '上海',
      website: 'linzhixia.design',
      summary: '6 年数字产品设计经验，关注复杂业务中的清晰体验。擅长从用户研究到设计落地的完整链路，曾主导多个千万级用户产品的体验升级。',
    },
    experiences: [
      {
        id: 'exp-1',
        company: '远山科技',
        role: '高级产品设计师',
        start_date: '2022.04',
        end_date: '',
        current: true,
        description: '负责企业协作产品的核心体验，带领 3 人设计小组完成工作台重构，关键任务完成率提升 28%。\n建立跨端设计系统与评审机制，将设计交付周期缩短 35%。',
      },
      {
        id: 'exp-2',
        company: '岛屿互动',
        role: '产品设计师',
        start_date: '2019.07',
        end_date: '2022.03',
        current: false,
        description: '参与从 0 到 1 搭建内容社区，负责创作与增长模块，推动次日留存提升 12%。',
      },
    ],
    projects: [
      {
        id: 'project-1',
        name: '企业工作台 3.0',
        role: '设计负责人',
        link: '',
        description: '通过 20+ 场用户访谈重构信息架构，以角色化首页帮助不同岗位快速抵达高频任务。',
      },
    ],
    education: [
      { id: 'edu-1', school: '江南大学', degree: '工业设计 · 本科', start_date: '2015.09', end_date: '2019.06' },
    ],
    skills: [
      { id: 'skill-1', name: '产品策略', level: '精通' },
      { id: 'skill-2', name: '交互设计', level: '精通' },
      { id: 'skill-3', name: 'Figma', level: '熟练' },
      { id: 'skill-4', name: '用户研究', level: '熟练' },
    ],
  },
}

export const createId = () => crypto.randomUUID()
