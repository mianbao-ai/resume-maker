import { ArrowDown, ArrowUp, Globe2, Mail, MapPin, Phone, Trash2 } from 'lucide-react'
import InlineEdit from './InlineEdit'
import type { Education, Experience, Project, ResumeData, Skill } from '../types'

const lines = (value: string) => value.split('\n').filter(Boolean)

export default function ResumePreview({ resume, onChange }: { resume: ResumeData; onChange: (resume: ResumeData) => void }) {
  const { personal, experiences, projects, education, skills } = resume.content
  const setPersonal = (key: keyof typeof personal, value: string) => onChange({
    ...resume,
    content: { ...resume.content, personal: { ...personal, [key]: value } },
  })
  const updateItem = (key: 'experiences' | 'projects' | 'education' | 'skills', id: string, patch: Partial<Experience & Project & Education & Skill>) => onChange({
    ...resume,
    content: { ...resume.content, [key]: resume.content[key].map((item) => item.id === id ? { ...item, ...patch } : item) },
  })
  const removeItem = (key: 'experiences' | 'projects' | 'education', id: string) => onChange({
    ...resume,
    content: { ...resume.content, [key]: resume.content[key].filter((item) => item.id !== id) },
  })
  const moveItem = (key: 'experiences' | 'projects' | 'education', index: number, direction: -1 | 1) => {
    const items = [...resume.content[key]]
    const target = index + direction
    if (target < 0 || target >= items.length) return
    ;[items[index], items[target]] = [items[target], items[index]]
    onChange({ ...resume, content: { ...resume.content, [key]: items } })
  }
  const contact = [
    [Mail, 'email', personal.email], [Phone, 'phone', personal.phone], [MapPin, 'location', personal.location], [Globe2, 'website', personal.website],
  ] as const

  return (
    <article className={`resume-paper template-${resume.template}`} style={{ '--accent': resume.accent_color } as React.CSSProperties}>
      <header className="resume-header">
        <div className="name-mark">{personal.name.slice(0, 1) || '你'}</div>
        <div className="identity">
          <h1><InlineEdit value={personal.name} onSave={(value) => setPersonal('name', value)} placeholder="你的姓名" /></h1>
          <p><InlineEdit value={personal.title} onSave={(value) => setPersonal('title', value)} placeholder="求职方向" /></p>
        </div>
        <div className="contact-list">
          {contact.map(([Icon, key, value]) => <span key={key}><Icon size={11} /><InlineEdit value={value} onSave={(next) => setPersonal(key, next)} placeholder={key === 'email' ? '邮箱' : key === 'phone' ? '电话' : key === 'location' ? '所在地' : '个人主页'} /></span>)}
        </div>
      </header>

      <ResumeSection title="个人简介"><p className="summary"><InlineEdit value={personal.summary} onSave={(value) => setPersonal('summary', value)} placeholder="点击补充个人简介" multiline /></p></ResumeSection>

      {experiences.length > 0 && <ResumeSection title="工作经历">
        {experiences.map((item, index) => <div className="resume-entry" key={item.id}>
          <EntryActions index={index} count={experiences.length} onMove={(direction) => moveItem('experiences', index, direction)} onDelete={() => removeItem('experiences', item.id)} />
          <div className="entry-top"><div><strong><InlineEdit value={item.company} onSave={(value) => updateItem('experiences', item.id, { company: value })} placeholder="公司名称" /></strong><span><InlineEdit value={item.role} onSave={(value) => updateItem('experiences', item.id, { role: value })} placeholder="职位" /></span></div><time><InlineEdit value={item.start_date} onSave={(value) => updateItem('experiences', item.id, { start_date: value })} placeholder="开始时间" /> — {item.current ? '至今' : <InlineEdit value={item.end_date} onSave={(value) => updateItem('experiences', item.id, { end_date: value })} placeholder="结束时间" />}</time></div>
          <ul>{lines(item.description).map((line, i) => <li key={i}><InlineEdit value={line} onSave={(value) => updateItem('experiences', item.id, { description: lines(item.description).map((old, lineIndex) => lineIndex === i ? value : old).join('\n') })} multiline /></li>)}</ul>
        </div>)}
      </ResumeSection>}

      {projects.length > 0 && <ResumeSection title="项目经历">
        {projects.map((item, index) => <div className="resume-entry" key={item.id}>
          <EntryActions index={index} count={projects.length} onMove={(direction) => moveItem('projects', index, direction)} onDelete={() => removeItem('projects', item.id)} />
          <div className="entry-top"><div><strong><InlineEdit value={item.name} onSave={(value) => updateItem('projects', item.id, { name: value })} placeholder="项目名称" /></strong><span><InlineEdit value={item.role} onSave={(value) => updateItem('projects', item.id, { role: value })} placeholder="你的角色" /></span></div>{item.link && <small><InlineEdit value={item.link} onSave={(value) => updateItem('projects', item.id, { link: value })} /></small>}</div>
          <p><InlineEdit value={item.description} onSave={(value) => updateItem('projects', item.id, { description: value })} placeholder="项目描述" multiline /></p>
        </div>)}
      </ResumeSection>}

      {education.length > 0 && <ResumeSection title="教育背景">
        {education.map((item, index) => <div className="resume-entry education-entry" key={item.id}>
          <EntryActions index={index} count={education.length} onMove={(direction) => moveItem('education', index, direction)} onDelete={() => removeItem('education', item.id)} />
          <div><strong><InlineEdit value={item.school} onSave={(value) => updateItem('education', item.id, { school: value })} placeholder="学校名称" /></strong><span><InlineEdit value={item.degree} onSave={(value) => updateItem('education', item.id, { degree: value })} placeholder="专业与学历" /></span></div><time><InlineEdit value={item.start_date} onSave={(value) => updateItem('education', item.id, { start_date: value })} /> — <InlineEdit value={item.end_date} onSave={(value) => updateItem('education', item.id, { end_date: value })} /></time>
        </div>)}
      </ResumeSection>}

      {skills.length > 0 && <ResumeSection title="技能专长">
        <div className="resume-skills">{skills.map((skill) => <span key={skill.id}><InlineEdit value={skill.name} onSave={(value) => updateItem('skills', skill.id, { name: value })} placeholder="技能" /><small>{skill.level}</small></span>)}</div>
      </ResumeSection>}
    </article>
  )
}

function EntryActions({ index, count, onMove, onDelete }: { index: number; count: number; onMove: (direction: -1 | 1) => void; onDelete: () => void }) {
  return <div className="preview-entry-actions" role="toolbar" aria-label="条目操作">
    <button disabled={index === 0} onClick={() => onMove(-1)} title="上移"><ArrowUp size={11} /></button>
    <button disabled={index === count - 1} onClick={() => onMove(1)} title="下移"><ArrowDown size={11} /></button>
    <button className="danger" onClick={onDelete} title="删除"><Trash2 size={11} /></button>
  </div>
}

function ResumeSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="resume-section"><h2>{title}</h2><div>{children}</div></section>
}
