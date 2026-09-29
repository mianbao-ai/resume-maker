import { ArrowDown, ArrowUp, Globe2, Mail, MapPin, Phone, Trash2 } from 'lucide-react'
import InlineEdit from './InlineEdit'
import type { ResumeDocument, ResumeEducation, ResumeExperience, ResumeProject } from '../types'

export default function ResumePreview({ document, onChange }: { document: ResumeDocument; onChange: (document: ResumeDocument) => void }) {
  const { basics, experiences, projects, education, skills } = document
  const setBasics = (key: keyof typeof basics, value: string) => onChange({ ...document, basics: { ...basics, [key]: value } })
  const updateItem = <T extends { id: string }>(key: 'experiences' | 'projects' | 'education', id: string, patch: Partial<T>) => onChange({ ...document, [key]: document[key].map((item) => item.id === id ? { ...item, ...patch } : item) } as ResumeDocument)
  const removeItem = (key: 'experiences' | 'projects' | 'education', id: string) => onChange({ ...document, [key]: document[key].filter((item) => item.id !== id) } as ResumeDocument)
  const moveItem = (key: 'experiences' | 'projects' | 'education', index: number, direction: -1 | 1) => {
    const items = [...document[key]]; const target = index + direction
    if (target < 0 || target >= items.length) return
    ;[items[index], items[target]] = [items[target], items[index]]
    onChange({ ...document, [key]: items } as ResumeDocument)
  }
  const contact = [[Mail, 'email', basics.email], [Phone, 'phone', basics.phone], [MapPin, 'location', basics.location], [Globe2, 'website', basics.links.find((link) => link.url)?.url || '']] as const

  const templateClass = document.templateId === 'ats-classic-v1' ? 'classic' : 'minimal'
  return <article className={`resume-paper template-${templateClass}`} style={{ '--accent': document.formatting.accentColor } as React.CSSProperties}>
    <header className="resume-header"><div className="name-mark">{basics.name.slice(0, 1) || '你'}</div><div className="identity"><h1><InlineEdit value={basics.name} onSave={(value) => setBasics('name', value)} placeholder="你的姓名" /></h1><p><InlineEdit value={basics.headline || document.targetRole} onSave={(value) => onChange({ ...document, targetRole: value, basics: { ...basics, headline: value } })} placeholder="求职方向" /></p></div><div className="contact-list">{contact.map(([Icon, key, value]) => <span key={key}><Icon size={11} /><InlineEdit value={value} onSave={(next) => { if (key === 'website') onChange({ ...document, basics: { ...basics, links: basics.links.length ? basics.links.map((link, index) => index === 0 ? { ...link, url: next } : link) : [{ id: 'link-1', label: '主页', url: next }] } }); else setBasics(key, next) }} placeholder={key === 'email' ? '邮箱' : key === 'phone' ? '电话' : key === 'location' ? '所在地' : '个人主页'} /></span>)}</div></header>
    <ResumeSection title="个人简介"><p className="summary"><InlineEdit value={document.selfEvaluation} onSave={(value) => onChange({ ...document, selfEvaluation: value })} placeholder="点击补充个人简介" multiline /></p></ResumeSection>
    {experiences.length > 0 && <ResumeSection title="工作经历">{experiences.map((item, index) => <ExperienceEntry key={item.id} item={item} index={index} count={experiences.length} onMove={(direction) => moveItem('experiences', index, direction)} onDelete={() => removeItem('experiences', item.id)} onChange={(patch) => updateItem<ResumeExperience>('experiences', item.id, patch)} />)}</ResumeSection>}
    {projects.length > 0 && <ResumeSection title="项目经历">{projects.map((item, index) => <ProjectEntry key={item.id} item={item} index={index} count={projects.length} onMove={(direction) => moveItem('projects', index, direction)} onDelete={() => removeItem('projects', item.id)} onChange={(patch) => updateItem<ResumeProject>('projects', item.id, patch)} />)}</ResumeSection>}
    {education.length > 0 && <ResumeSection title="教育背景">{education.map((item, index) => <div className="resume-entry education-entry" key={item.id}><EntryActions index={index} count={education.length} onMove={(direction) => moveItem('education', index, direction)} onDelete={() => removeItem('education', item.id)} /><div><strong><InlineEdit value={item.school} onSave={(value) => updateItem<ResumeEducation>('education', item.id, { school: value })} placeholder="学校名称" /></strong><span><InlineEdit value={item.degree} onSave={(value) => updateItem<ResumeEducation>('education', item.id, { degree: value })} placeholder="专业与学历" /></span></div><time><InlineEdit value={item.startDate} onSave={(value) => updateItem<ResumeEducation>('education', item.id, { startDate: value })} /> — <InlineEdit value={item.endDate} onSave={(value) => updateItem<ResumeEducation>('education', item.id, { endDate: value })} /></time></div>)}</ResumeSection>}
    {skills.length > 0 && <ResumeSection title="技能专长"><div className="resume-skills">{skills.flatMap((group, groupIndex) => group.skills.map((skill, skillIndex) => <span key={`${group.id}-${skillIndex}`}><InlineEdit value={skill} onSave={(value) => onChange({ ...document, skills: document.skills.map((current, index) => index === groupIndex ? { ...current, skills: current.skills.map((name, itemIndex) => itemIndex === skillIndex ? value : name) } : current) })} placeholder="技能" /><small>{group.label}</small></span>))}</div></ResumeSection>}
  </article>
}

function ExperienceEntry({ item, index, count, onMove, onDelete, onChange }: { item: ResumeExperience; index: number; count: number; onMove: (direction: -1 | 1) => void; onDelete: () => void; onChange: (patch: Partial<ResumeExperience>) => void }) {
  const updateBullet = (bulletIndex: number, value: string) => onChange({ bullets: item.bullets.map((bullet, index) => index === bulletIndex ? value : bullet) })
  return <div className="resume-entry"><EntryActions index={index} count={count} onMove={onMove} onDelete={onDelete} /><div className="entry-top"><div><strong><InlineEdit value={item.company} onSave={(value) => onChange({ company: value })} placeholder="公司名称" /></strong><span><InlineEdit value={item.role} onSave={(value) => onChange({ role: value })} placeholder="职位" /></span></div><time><InlineEdit value={item.startDate} onSave={(value) => onChange({ startDate: value })} placeholder="开始时间" /> — <InlineEdit value={item.endDate} onSave={(value) => onChange({ endDate: value })} placeholder="结束时间" /></time></div><ul>{item.bullets.map((bullet, bulletIndex) => <li key={bulletIndex}><InlineEdit value={bullet} onSave={(value) => updateBullet(bulletIndex, value)} multiline /></li>)}</ul></div>
}

function ProjectEntry({ item, index, count, onMove, onDelete, onChange }: { item: ResumeProject; index: number; count: number; onMove: (direction: -1 | 1) => void; onDelete: () => void; onChange: (patch: Partial<ResumeProject>) => void }) {
  const updateBullet = (bulletIndex: number, value: string) => onChange({ bullets: item.bullets.map((bullet, index) => index === bulletIndex ? value : bullet) })
  return <div className="resume-entry"><EntryActions index={index} count={count} onMove={onMove} onDelete={onDelete} /><div className="entry-top"><div><strong><InlineEdit value={item.name} onSave={(value) => onChange({ name: value })} placeholder="项目名称" /></strong><span><InlineEdit value={item.role} onSave={(value) => onChange({ role: value })} placeholder="你的角色" /></span></div>{item.link && <small><InlineEdit value={item.link} onSave={(value) => onChange({ link: value })} /></small>}</div><ul>{item.bullets.map((bullet, bulletIndex) => <li key={bulletIndex}><InlineEdit value={bullet} onSave={(value) => updateBullet(bulletIndex, value)} multiline /></li>)}</ul></div>
}

function EntryActions({ index, count, onMove, onDelete }: { index: number; count: number; onMove: (direction: -1 | 1) => void; onDelete: () => void }) {
  return <div className="preview-entry-actions" role="toolbar" aria-label="条目操作"><button disabled={index === 0} onClick={() => onMove(-1)} title="上移"><ArrowUp size={11} /></button><button disabled={index === count - 1} onClick={() => onMove(1)} title="下移"><ArrowDown size={11} /></button><button className="danger" onClick={onDelete} title="删除"><Trash2 size={11} /></button></div>
}

function ResumeSection({ title, children }: { title: string; children: React.ReactNode }) { return <section className="resume-section"><h2>{title}</h2><div>{children}</div></section> }
