import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { marked } from 'marked'
import { api } from '../api'

export default function PMChatModal({ onClose, onProjectCreated }) {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [projectCreated, setProjectCreated] = useState(null) // { project_id }
  const [initError, setInitError] = useState('')
  const listRef = useRef(null)
  const pollingRef = useRef(null)
  const inputRef = useRef(null)

  // Create PM conversation on mount
  useEffect(() => {
    api.createPMConversation()
      .then(data => setConversationId(data.id))
      .catch(() => setInitError('Failed to start PM session. Please try again.'))
    return () => clearInterval(pollingRef.current)
  }, [])

  // Scroll to bottom on new messages
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages])

  // Focus input when conversation ready
  useEffect(() => {
    if (conversationId) inputRef.current?.focus()
  }, [conversationId])

  // Close on Escape (unless project was just created — user needs to navigate)
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape' && !projectCreated) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, projectCreated])

  function startPolling(msgId) {
    clearInterval(pollingRef.current)
    pollingRef.current = setInterval(async () => {
      try {
        const msg = await api.getPMMessage(msgId)
        if (!msg.processing) {
          clearInterval(pollingRef.current)
          setSending(false)
          setMessages(prev => prev.map(m => m.id === msgId ? msg : m))
          if (msg.conversation_project_id) {
            setProjectCreated({ project_id: msg.conversation_project_id })
          }
        }
      } catch {
        clearInterval(pollingRef.current)
        setSending(false)
      }
    }, 2000)
  }

  async function send() {
    const content = input.trim()
    if (!content || sending || !conversationId) return
    setInput('')
    setSending(true)

    const tempUser      = { id: -Date.now(),       role: 'user',      content, processing: false }
    const tempAssistant = { id: -(Date.now() + 1), role: 'assistant', content: '', processing: true }
    setMessages(prev => [...prev, tempUser, tempAssistant])

    try {
      const data = await api.sendPMMessage(conversationId, content)
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

  function handleViewProject() {
    onProjectCreated(projectCreated.project_id)
    onClose()
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4 bg-black/50 backdrop-blur-sm animate-fadein">
      <div className="bg-white w-full h-dvh sm:h-[80vh] sm:max-w-2xl sm:rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 shrink-0">
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 bg-violet-500 rounded-full animate-pulse" />
            <span className="text-sm font-semibold text-slate-700">Product Manager</span>
            <span className="text-xs text-slate-400 hidden sm:inline">— Iterate your idea</span>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Project created banner */}
        {projectCreated && (
          <div className="shrink-0 mx-4 mt-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between gap-3 animate-fadein">
            <div className="flex items-center gap-2 text-sm text-emerald-700">
              <span className="text-base">✓</span>
              <span className="font-semibold">Project created!</span>
              <span className="text-emerald-600 text-xs">Tech Lead is planning now.</span>
            </div>
            <button
              onClick={handleViewProject}
              className="shrink-0 px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-lg transition-colors"
            >
              View Project →
            </button>
          </div>
        )}

        {/* Messages */}
        <div
          ref={listRef}
          className="flex-1 overflow-y-auto flex flex-col gap-3 p-5 custom-scroll bg-slate-50/30"
        >
          {initError ? (
            <p className="text-center text-red-400 text-sm py-10">{initError}</p>
          ) : !conversationId ? (
            <div className="flex justify-center py-10">
              <div className="w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center py-10 gap-2 text-center">
              <p className="text-slate-500 text-sm font-medium">What are you trying to build?</p>
              <p className="text-slate-400 text-xs max-w-xs">
                Describe your idea — even rough is fine. The PM will help you sharpen it into a project worth building.
              </p>
            </div>
          ) : (
            messages.map(msg => <PMBubble key={msg.id} msg={msg} />)
          )}
        </div>

        {/* Input */}
        <div className="flex gap-3 p-4 border-t border-slate-100 bg-slate-50/60 shrink-0">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send() }
            }}
            placeholder={conversationId ? 'Describe your idea…' : 'Loading…'}
            disabled={!conversationId || !!projectCreated}
            rows={3}
            className="flex-1 text-sm px-3.5 py-2.5 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-400 placeholder:text-slate-400 bg-white transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={send}
            disabled={sending || !input.trim() || !conversationId || !!projectCreated}
            className="self-end px-5 py-2.5 bg-violet-500 hover:bg-violet-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-violet-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none whitespace-nowrap"
          >
            Send →
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

function PMBubble({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end animate-msg">
        <div className="max-w-[78%] px-4 py-2.5 bg-gradient-to-br from-violet-500 to-violet-600 text-white text-sm rounded-2xl rounded-br-sm shadow-sm shadow-violet-200 whitespace-pre-wrap leading-relaxed">
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
