import { ArrowUp, Target } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { sendAgentMessage } from '../api'
import type { ResumeDocument } from '../types'
import BreadIcon from './BreadIcon'

type Message = { id: string; role: 'assistant' | 'user'; content: string }
const initialMessages: Message[] = [{ id: 'welcome', role: 'assistant', content: '你好，我是你的简历顾问。你可以让我检查内容、优化表达，或者直接点击右侧简历中的文字修改。' }]
const prompts = ['检查这份简历', '优化个人简介', '如何突出工作成果？', '给我 3 条修改建议']

export default function ResumeChat({ document, sessionId, ensureSession }: { document: ResumeDocument; sessionId: string | null; ensureSession: () => Promise<string | null> }) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, thinking])

  const send = async (text = input) => {
    const value = text.trim()
    if (!value || thinking) return
    setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'user', content: value }])
    setInput(''); setThinking(true)
    try {
      const activeSessionId = sessionId || await ensureSession()
      if (!activeSessionId) throw new Error('无法创建 Agent 会话')
      let content = ''
      await sendAgentMessage(activeSessionId, value, (event, data) => {
        if (event === 'message_delta') content += String(data.content || '')
        if (event === 'error') throw new Error(String(data.message || 'Agent 请求失败'))
      })
      setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'assistant', content: content || '我已收到你的请求。' }])
    } catch (error) {
      setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'assistant', content: error instanceof Error ? error.message : 'Agent 请求失败，请稍后重试。' }])
    } finally { setThinking(false) }
  }

  return <section className="resume-chat">
    <header className="chat-header"><div className="chat-agent-avatar"><BreadIcon size={19} /></div><div><strong>面包简历顾问</strong><span><i /> Agent 模式</span></div></header>
    <div className="chat-context"><Target size={14} /><span>当前目标</span><strong>{document.targetRole || document.basics.headline || '待确认求职方向'}</strong></div>
    <div className="chat-messages">
      {messages.map((message) => <div className={`chat-message ${message.role}`} key={message.id}><div className="chat-avatar">{message.role === 'user' ? '我' : <BreadIcon size={16} />}</div><div className="chat-bubble-wrap"><span>{message.role === 'user' ? '你' : '面包'}</span><div className="chat-bubble">{message.content.split('\n').map((line, index) => <p key={index}>{line || <br />}</p>)}</div></div></div>)}
      {thinking && <div className="chat-message assistant"><div className="chat-avatar"><BreadIcon size={16} /></div><div className="chat-thinking"><i /><i /><i /></div></div>}<div ref={endRef} />
    </div>
    <div className="chat-composer-area"><div className="prompt-chips">{prompts.map((prompt) => <button key={prompt} onClick={() => send(prompt)}>{prompt}</button>)}</div><div className="chat-composer"><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} placeholder="告诉我你想如何修改简历…" rows={3} /><div className="composer-footer"><span>请求发送到 Resume Agent</span><button onClick={() => void send()} disabled={!input.trim() || thinking} aria-label="发送"><ArrowUp size={17} /></button></div></div></div>
  </section>
}
