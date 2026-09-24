import { useEffect, useRef, useState } from 'react'

interface Props {
  value: string
  onSave: (value: string) => void
  placeholder?: string
  multiline?: boolean
  className?: string
}

export default function InlineEdit({ value, onSave, placeholder = '点击编辑', multiline = false, className = '' }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null)

  useEffect(() => setDraft(value), [value])
  useEffect(() => {
    if (!editing) return
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [editing])

  const cancel = () => {
    setDraft(value)
    setEditing(false)
  }

  const commit = () => {
    const next = draft.trim()
    if (next !== value) onSave(next)
    setEditing(false)
  }

  if (editing) {
    const props = {
      ref: inputRef as never,
      value: draft,
      onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setDraft(event.target.value),
      onBlur: commit,
      onKeyDown: (event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        if (event.key === 'Escape') cancel()
        if (event.key === 'Enter' && (!multiline || event.metaKey || event.ctrlKey)) {
          event.preventDefault()
          commit()
        }
      },
    }
    return (
      <span className={`preview-inline-editor ${multiline ? 'is-multiline' : ''} ${className}`}>
        {multiline ? <textarea {...props} rows={Math.max(2, draft.split('\n').length)} /> : <input {...props} />}
      </span>
    )
  }

  return (
    <span
      className={`preview-editable ${value ? '' : 'is-empty'} ${className}`}
      role="button"
      tabIndex={0}
      title="点击直接编辑"
      onClick={(event) => { event.stopPropagation(); setEditing(true) }}
      onKeyDown={(event) => { if (event.key === 'Enter') setEditing(true) }}
    >
      {value || placeholder}
    </span>
  )
}
