import { useState, useEffect, useRef } from 'react'
import { marked } from 'marked'
import { api } from '../api'

export default function ChatPanel({ projectId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [sending, setSending]   = useState(false)
  const listRef    = useRef(null)
  const pollingRef = useRef(null)

  useEffect(() => {
    api.getMessages(projectId).then(msgs => {
      setMessages(msgs)
      const processing = [...msgs].reverse().find(m => m.processing)
      if (processing) { setSending(true); startPolling(processing.id) }
    })
    return () => clearInterval(pollingRef.current)
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages])

  function startPolling(msgId) {
    clearInterval(pollingRef.current)
    pollingRef.current = setInterval(async () => {
      try {
        const msg = await api.getMessage(msgId)
        if (!msg.processing) {
          clearInterval(pollingRef.current)
          setSending(false)
          setMessages(prev => prev.map(m => m.id === msgId ? msg : m))
        }
      } catch {
        clearInterval(pollingRef.current)
        setSending(false)
      }
    }, 2000)
  }

  async function send() {
    const content = input.trim()
    if (!content || sending) return
    setInput('')
    setSending(true)

    const tempUser      = { id: -Date.now(),       role: 'user',      content, processing: false }
    const tempAssistant = { id: -(Date.now() + 1), role: 'assistant', content: '', processing: true }
    setMessages(prev => [...prev, tempUser, tempAssistant])

    try {
      const data = await api.sendMessage(projectId, content)
      setMessages(prev => prev.map(m => {
        if (m.id === tempUser.id)      return { ...m, id: data.user_message_id }
        if (m.id === tempAssistant.id) return { ...m, id: data.assistant_message_id }
        return m
      }))
      startPolling(data.assistant_message_id)
    } catch {
      setMessages(prev => prev.filter(m => m.id !== tempUser.id && m.id !== tempAssistant.id))
      setSending(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/80">
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
          <span className="text-sm font-semibold text-slate-700">Chat with Tech Lead</span>
        </div>
        <span className="text-xs text-slate-400">Ctrl+Enter to send</span>
      </div>

      {/* Messages */}
      <div
        ref={listRef}
        className="flex flex-col gap-3 p-5 min-h-[200px] max-h-[480px] overflow-y-auto custom-scroll bg-slate-50/30"
      >
        {messages.length === 0 ? (
          <p className="text-center text-slate-400 text-sm py-10">
            Start chatting with the Tech Lead to plan your feature.
          </p>
        ) : (
          messages.map(msg => <Bubble key={msg.id} msg={msg} />)
        )}
      </div>

      {/* Input */}
      <div className="flex gap-3 p-4 border-t border-slate-100 bg-slate-50/60">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send() } }}
          placeholder="Describe your feature idea or ask a question…"
          rows={3}
          className="flex-1 text-sm px-3.5 py-2.5 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 placeholder:text-slate-400 bg-white transition-shadow"
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          className="self-end px-5 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none whitespace-nowrap"
        >
          Send →
        </button>
      </div>
    </div>
  )
}

function Bubble({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end animate-msg">
        <div className="max-w-[78%] px-4 py-2.5 bg-gradient-to-br from-indigo-500 to-indigo-600 text-white text-sm rounded-2xl rounded-br-sm shadow-sm shadow-indigo-200 whitespace-pre-wrap leading-relaxed">
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
        className="max-w-[82%] px-4 py-3 bg-white border border-slate-200 text-slate-800 text-sm rounded-2xl rounded-bl-sm shadow-sm md-prose leading-relaxed"
        dangerouslySetInnerHTML={{ __html: marked.parse(msg.content, { breaks: true, gfm: true }) }}
      />
    </div>
  )
}
