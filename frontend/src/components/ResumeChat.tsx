import { ArrowUp, Check, MessageSquareText, Target } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ResumeData } from '../types'
import BreadIcon from './BreadIcon'

type Proposal = { kind: 'summary'; before: string; after: string; applied?: boolean }
type Message = { id: string; role: 'assistant' | 'user'; content: string; proposal?: Proposal }

const initialMessages: Message[] = [{
  id: 'welcome',
  role: 'assistant',
  content: '你好，我是你的简历顾问。你可以让我检查内容、优化表达，或者直接点击右侧简历中的文字修改。',
}]

const prompts = ['检查这份简历', '优化个人简介', '如何突出工作成果？', '给我 3 条修改建议']

function createReply(input: string, resume: ResumeData): Omit<Message, 'id' | 'role'> {
  const { personal, experiences, projects, education, skills } = resume.content
  if (/简介|自我介绍|个人介绍/.test(input)) {
    const role = personal.title || '目标岗位'
    const years = Math.max(1, experiences.length * 2 + 2)
    const after = `${years} 年${role}相关经验，擅长将复杂问题转化为清晰、可落地的解决方案。具备从分析到交付的完整项目经验，重视结果，并善于通过协作推动业务持续增长。`
    return {
      content: '我根据你的求职方向重写了一版简介。建议保留具体年限，并在最后一句补充最有说服力的业务成果。',
      proposal: { kind: 'summary', before: personal.summary, after },
    }
  }
  if (/检查|诊断|体检/.test(input)) {
    const missing = [!personal.email && '联系方式', !personal.summary && '个人简介', !experiences.length && '工作经历', !education.length && '教育背景', !skills.length && '技能'].filter(Boolean)
    return { content: missing.length
      ? `我完成了快速检查。目前最需要补充：${missing.join('、')}。补齐后再重点优化经历中的量化结果。`
      : `整体结构完整，完成度很好。当前有 ${experiences.length} 段工作经历、${projects.length} 个项目和 ${skills.length} 项技能。下一步建议把每段经历改成“行动 + 方法 + 结果”，并尽量加入数字。` }
  }
  if (/成果|工作|经历|量化/.test(input)) {
    return { content: '建议每条经历按“做了什么 → 如何做 → 产生什么结果”组织。比如把“负责工作台改版”改为“主导工作台信息架构重构，通过 20 场访谈定位关键路径，使任务完成率提升 28%”。右侧经历文字可以直接点击修改。' }
  }
  if (/建议|优化/.test(input)) {
    return { content: `我建议先做三件事：\n1. 标题明确目标岗位，而不是宽泛职能；\n2. 每段经历保留 2–4 条高价值成果；\n3. 项目描述加入规模、难度和最终指标。\n\n你也可以告诉我具体目标岗位，我会给出更针对性的建议。` }
  }
  return { content: `我理解你希望优化“${input.slice(0, 40)}${input.length > 40 ? '…' : ''}”。当前本地版不会把简历发送到第三方。你可以继续说明目标岗位或希望重点修改的模块，我会结合右侧内容给出建议。` }
}

export default function ResumeChat({ resume, onChange }: { resume: ResumeData; onChange: (resume: ResumeData) => void }) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  const send = (text = input) => {
    const value = text.trim()
    if (!value || thinking) return
    setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'user', content: value }])
    setInput('')
    setThinking(true)
    window.setTimeout(() => {
      const reply = createReply(value, resume)
      setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'assistant', ...reply }])
      setThinking(false)
    }, 420)
  }

  const applyProposal = (messageId: string, proposal: Proposal) => {
    onChange({ ...resume, content: { ...resume.content, personal: { ...resume.content.personal, summary: proposal.after } } })
    setMessages((items) => items.map((item) => item.id === messageId ? { ...item, proposal: { ...proposal, applied: true } } : item))
  }

  return (
    <section className="resume-chat">
      <header className="chat-header">
        <div className="chat-agent-avatar"><BreadIcon size={19} /></div>
        <div><strong>面包简历顾问</strong><span><i /> 本地模式</span></div>
      </header>

      <div className="chat-context"><Target size={14} /><span>当前目标</span><strong>{resume.content.personal.title || '待确认求职方向'}</strong></div>

      <div className="chat-messages">
        {messages.map((message) => <div className={`chat-message ${message.role}`} key={message.id}>
          <div className="chat-avatar">{message.role === 'user' ? '我' : <BreadIcon size={16} />}</div>
          <div className="chat-bubble-wrap">
            <span>{message.role === 'user' ? '你' : '面包'}</span>
            <div className="chat-bubble">{message.content.split('\n').map((line, index) => <p key={index}>{line || <br />}</p>)}</div>
            {message.proposal && <div className={`change-proposal ${message.proposal.applied ? 'is-applied' : ''}`}>
              <div className="proposal-title"><MessageSquareText size={14} /><strong>个人简介修改建议</strong></div>
              <div className="proposal-diff"><span>修改后</span><p>{message.proposal.after}</p></div>
              <button disabled={message.proposal.applied} onClick={() => applyProposal(message.id, message.proposal!)}>
                <Check size={14} />{message.proposal.applied ? '已应用到简历' : '应用这项修改'}
              </button>
            </div>}
          </div>
        </div>)}
        {thinking && <div className="chat-message assistant"><div className="chat-avatar"><BreadIcon size={16} /></div><div className="chat-thinking"><i /><i /><i /></div></div>}
        <div ref={endRef} />
      </div>

      <div className="chat-composer-area">
        <div className="prompt-chips">{prompts.map((prompt) => <button key={prompt} onClick={() => send(prompt)}>{prompt}</button>)}</div>
        <div className="chat-composer">
          <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send() } }} placeholder="告诉我你想如何修改简历…" rows={3} />
          <div className="composer-footer"><span>内容仅在本地处理</span><button onClick={() => send()} disabled={!input.trim() || thinking} aria-label="发送"><ArrowUp size={17} /></button></div>
        </div>
      </div>
    </section>
  )
}
