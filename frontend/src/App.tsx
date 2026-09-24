import { Check, Cloud, Download, Github, LayoutTemplate, Loader2, Palette, RotateCcw, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { createResume, updateResume } from './api'
import ResumeChat from './components/ResumeChat'
import ResumePreview from './components/ResumePreview'
import { sampleResume } from './sample'
import type { ResumeData, Template } from './types'

const STORAGE_KEY = 'resume-maker-draft-v1'
const colors = ['#176B5B', '#214C75', '#714955', '#8A4B26', '#51468C', '#252525']

function loadDraft(): ResumeData {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : sampleResume
  } catch { return sampleResume }
}

export default function App() {
  const [resume, setResume] = useState<ResumeData>(loadDraft)
  const [savedId, setSavedId] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<'local' | 'saving' | 'cloud' | 'error'>('local')
  const firstRender = useRef(true)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(resume))
    if (firstRender.current) { firstRender.current = false; return }
    setSaveState('local')
  }, [resume])

  const completeness = useMemo(() => {
    const p = resume.content.personal
    const checks = [p.name, p.title, p.email, p.summary, resume.content.experiences.length, resume.content.education.length, resume.content.skills.length]
    return Math.round((checks.filter(Boolean).length / checks.length) * 100)
  }, [resume])

  const saveToCloud = async () => {
    setSaveState('saving')
    try {
      const saved = savedId ? await updateResume(savedId, resume) : await createResume(resume)
      setSavedId(saved.id)
      setSaveState('cloud')
    } catch { setSaveState('error') }
  }

  const reset = () => {
    if (window.confirm('确定恢复示例内容吗？当前编辑将被覆盖。')) {
      setResume(sampleResume); setSavedId(null)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#"><span className="brand-mark">简</span><span>简历工坊<small>RESUME MAKER</small></span></a>
        <div className="document-title">
          <input value={resume.title} onChange={(e) => setResume({ ...resume, title: e.target.value })} aria-label="简历标题" />
          <span className={`save-state ${saveState}`}>
            {saveState === 'saving' ? <Loader2 size={12} className="spin" /> : saveState === 'cloud' ? <Cloud size={12} /> : <Check size={12} />}
            {saveState === 'saving' ? '正在保存' : saveState === 'cloud' ? '已同步' : saveState === 'error' ? '同步失败' : '已保存到本地'}
          </span>
        </div>
        <nav className="top-actions">
          <a className="ghost-button github" href="https://github.com/mianbao-ai/resume-maker" target="_blank" rel="noreferrer"><Github size={17} /> GitHub</a>
          <button className="ghost-button" onClick={saveToCloud}><Cloud size={17} /> 同步</button>
          <button className="primary-button" onClick={() => window.print()}><Download size={17} /> 导出 PDF</button>
        </nav>
      </header>

      <main className="workspace">
        <aside className="chat-column"><ResumeChat resume={resume} onChange={setResume} /></aside>
        <section className="preview-area">
          <div className="preview-toolbar">
            <div className="completion">
              <div className="progress-ring" style={{ '--progress': `${completeness * 3.6}deg` } as React.CSSProperties}><span>{completeness}</span></div>
              <div><strong>简历完成度</strong><small>{completeness === 100 ? '内容很完整，可以投递了' : '再补充一些内容会更出彩'}</small></div>
            </div>
            <div className="toolbar-groups">
              <div className="tool-group"><LayoutTemplate size={15} /><span>版式</span>{(['classic', 'minimal'] as Template[]).map((t) => <button key={t} className={resume.template === t ? 'active' : ''} onClick={() => setResume({ ...resume, template: t })}>{t === 'classic' ? '专业' : '极简'}</button>)}</div>
              <div className="tool-group colors"><Palette size={15} /><span>主题</span>{colors.map((color) => <button key={color} className={resume.accent_color === color ? 'active' : ''} style={{ background: color }} onClick={() => setResume({ ...resume, accent_color: color })} aria-label={`主题色 ${color}`} />)}</div>
              <button className="reset-button" onClick={reset}><RotateCcw size={15} /> 重置</button>
            </div>
          </div>
          <div className="paper-stage"><div className="paper-wrap"><ResumePreview resume={resume} onChange={setResume} /></div></div>
          <div className="privacy-note"><Sparkles size={14} /> 默认仅存储在你的浏览器中，你的数据由你掌控</div>
        </section>
      </main>
    </div>
  )
}
