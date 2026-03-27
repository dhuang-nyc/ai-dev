import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../api'
import ChatCore from './ChatCore'

export default function PMChatModal({ onClose, onProjectCreated }) {
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [projectCreated, setProjectCreated] = useState(null)
  const pollingRef = useRef(null)

  useEffect(() => {
    return () => clearInterval(pollingRef.current)
  }, [])

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

  async function handleSend(content) {
    setSending(true)
    const tempUser = { id: -Date.now(), role: 'user', content, processing: false }
    const tempAssistant = { id: -(Date.now() + 1), role: 'assistant', content: '', processing: true }
    setMessages(prev => [...prev, tempUser, tempAssistant])

    try {
      let convId = conversationId
      if (!convId) {
        const conv = await api.createPMConversation()
        convId = conv.id
        setConversationId(convId)
      }
      const data = await api.sendPMMessage(convId, content)
      setMessages(prev => prev.map(m => {
        if (m.id === tempUser.id) return { ...m, id: data.user_message_id }
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

        <ChatCore
          messages={messages}
          sending={sending}
          onSend={handleSend}
          emptyMessage={{ title: 'What are you trying to build?', subtitle: 'Describe your idea — even rough is fine. The PM will help you sharpen it into a project worth building.' }}
          placeholder="Describe your idea…"
          inputDisabled={!!projectCreated}
          theme="violet"
        />
      </div>
    </div>,
    document.body
  )
}
