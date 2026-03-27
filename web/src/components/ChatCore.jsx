import { useState, useEffect, useRef, useMemo } from 'react'
import { marked } from 'marked'
import AgentCostSummary from './AgentCostSummary'

const THEMES = {
  indigo: {
    userBubble: 'bg-gradient-to-br from-indigo-500 to-indigo-600 shadow-indigo-200',
    focusRing: 'focus:ring-indigo-300 focus:border-indigo-400',
    sendBtn: 'bg-indigo-500 hover:bg-indigo-600 shadow-indigo-200',
    spinner: 'border-indigo-400',
  },
  violet: {
    userBubble: 'bg-gradient-to-br from-violet-500 to-violet-600 shadow-violet-200',
    focusRing: 'focus:ring-violet-300 focus:border-violet-400',
    sendBtn: 'bg-violet-500 hover:bg-violet-600 shadow-violet-200',
    spinner: 'border-violet-400',
  },
}

export default function ChatCore({
  messages,
  loading = false,
  sending = false,
  error = null,
  onSend,
  emptyMessage = null,
  placeholder = 'Type a message…',
  inputDisabled = false,
  theme = 'violet',
  maxHeight = null,
  readOnly = false,
}) {
  const [input, setInput] = useState('')
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const t = THEMES[theme] || THEMES.violet

  const stats = useMemo(() => {
    let totalCost = 0
    let totalTime = 0
    let count = 0
    for (const m of messages) {
      if (m.role !== 'assistant') continue
      if (m.token_cost != null) totalCost += Number(m.token_cost)
      if (m.response_time_ms != null) totalTime += m.response_time_ms
      if (m.token_cost != null || m.response_time_ms != null) count++
    }
    return count > 0 ? { totalCost, totalTime } : null
  }, [messages])

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    if (!loading && !readOnly) inputRef.current?.focus()
  }, [loading, readOnly])

  function send() {
    const content = input.trim()
    if (!content || sending || !onSend) return
    setInput('')
    onSend(content)
  }

  return (
    <>
      <div
        ref={listRef}
        className={`overflow-y-auto flex flex-col gap-3 p-5 custom-scroll bg-slate-50/30 ${maxHeight ? '' : 'flex-1'}`}
        style={maxHeight ? { maxHeight, minHeight: '200px' } : undefined}
      >
        {error ? (
          <p className="text-center text-red-400 text-sm py-10">{error}</p>
        ) : loading ? (
          <div className="flex justify-center py-16">
            <div className={`w-5 h-5 border-2 ${t.spinner} border-t-transparent rounded-full animate-spin`} />
          </div>
        ) : messages.length === 0 && emptyMessage ? (
          <div className="flex flex-col items-center py-16 gap-2 text-center">
            <p className="text-slate-500 text-sm font-medium">{emptyMessage.title}</p>
            {emptyMessage.subtitle && (
              <p className="text-slate-400 text-xs max-w-xs">{emptyMessage.subtitle}</p>
            )}
          </div>
        ) : (
          messages.map(msg => <Bubble key={msg.id} msg={msg} theme={t} />)
        )}
      </div>

      {!readOnly && (
        <div className="shrink-0 border-t border-slate-100 bg-slate-50/60">
          <div className="flex gap-3 p-4">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send() }
              }}
              placeholder={placeholder}
              disabled={inputDisabled}
              rows={3}
              className={`flex-1 text-sm px-3.5 py-2.5 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 ${t.focusRing} placeholder:text-slate-400 bg-white transition-shadow disabled:opacity-50 disabled:cursor-not-allowed`}
            />
            <button
              onClick={send}
              disabled={sending || !input.trim() || inputDisabled}
              className={`self-end px-5 py-2.5 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none whitespace-nowrap ${t.sendBtn}`}
            >
              Send →
            </button>
          </div>
          {stats && (
            <AgentCostSummary cost={stats.totalCost} timeMs={stats.totalTime} className="px-4 pb-3 -mt-1" />
          )}
        </div>
      )}

      {readOnly && stats && (
        <AgentCostSummary cost={stats.totalCost} timeMs={stats.totalTime} className="px-5 py-2.5 border-t border-slate-100" />
      )}
    </>
  )
}

function Bubble({ msg, theme }) {
  const [showStats, setShowStats] = useState(false)
  const bubbleRef = useRef(null)
  const hasCost = msg.role === 'assistant' && !msg.processing && (msg.token_cost != null || msg.response_time_ms != null)

  useEffect(() => {
    if (!showStats) return
    function onClickOutside(e) {
      if (bubbleRef.current && !bubbleRef.current.contains(e.target)) setShowStats(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [showStats])

  if (msg.role === 'user') {
    return (
      <div className="flex justify-end animate-msg">
        <div className={`max-w-[78%] px-4 py-2.5 text-white text-sm rounded-2xl rounded-br-sm shadow-sm whitespace-pre-wrap leading-relaxed ${theme.userBubble}`}>
          {msg.content}
        </div>
      </div>
    )
  }
  if (msg.processing) {
    return (
      <div className="flex justify-start animate-msg">
        <div className="px-4 py-3 bg-white border border-slate-200 rounded-2xl rounded-bl-sm shadow-sm">
          <div className="typing-dots"><span /><span /><span /></div>
        </div>
      </div>
    )
  }
  return (
    <div className="flex justify-start animate-msg">
      <div
        ref={bubbleRef}
        className={`max-w-[82%] bg-white border border-slate-200 text-slate-800 text-sm rounded-2xl rounded-bl-sm shadow-sm md-prose leading-relaxed ${hasCost ? 'cursor-pointer' : ''}`}
        onClick={() => hasCost && setShowStats(v => !v)}
      >
        <div
          className="px-4 py-3"
          dangerouslySetInnerHTML={{ __html: marked.parse(msg.content, { breaks: true, gfm: true }) }}
        />
        {showStats && (
          <AgentCostSummary cost={msg.token_cost} timeMs={msg.response_time_ms} className="px-4 py-2 border-t border-slate-100 text-[11px]" />
        )}
      </div>
    </div>
  )
}
