import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import ChatCore from './ChatCore'
import ConfirmModal from './ConfirmModal'

export default function PMConversationChat({ conversationId, onBack, onProjectCreated }) {
  const [messages, setMessages] = useState([])
  const [projectId, setProjectId] = useState(null)
  const [projectName, setProjectName] = useState(null)
  const [loading, setLoading] = useState(true)
  const [projectJustCreated, setProjectJustCreated] = useState(false)
  const [sending, setSending] = useState(false)
  const pollingRef = useRef(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  useEffect(() => {
    Promise.all([
      api.getPMConversation(conversationId),
      api.getPMMessages(conversationId),
    ])
      .then(([conv, msgs]) => {
        setProjectId(conv.project_id)
        setMessages(msgs)
        setLoading(false)
        const last = msgs[msgs.length - 1]
        if (last?.role === 'assistant' && last.processing) {
          setSending(true)
          startPolling(last.id)
        }
      })
      .catch(() => setLoading(false))

    return () => clearInterval(pollingRef.current)
  }, [conversationId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!projectId) return
    api.getProject(projectId).then(p => setProjectName(p.name)).catch(() => {})
  }, [projectId])

  function startPolling(msgId) {
    clearInterval(pollingRef.current)
    pollingRef.current = setInterval(async () => {
      try {
        const msg = await api.getPMMessage(msgId)
        if (!msg.processing) {
          clearInterval(pollingRef.current)
          setSending(false)
          setMessages(prev => prev.map(m => m.id === msgId ? msg : m))
          if (msg.conversation_project_id && !projectId) {
            setProjectId(msg.conversation_project_id)
            setProjectJustCreated(true)
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
      const data = await api.sendPMMessage(conversationId, content)
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

  return (
    <div className="flex flex-col h-full animate-fadein">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors text-sm"
          >
            ←
          </button>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-violet-500 rounded-full animate-pulse" />
            <span className="text-sm font-semibold text-slate-700">Product Manager</span>
            <span className="text-xs text-slate-400 hidden sm:inline">— Conversation #{conversationId}</span>
          </div>
        </div>
        {projectId && (
          <button
            onClick={() => onProjectCreated(projectId)}
            className="shrink-0 px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-lg transition-colors"
          >
            {projectName ? `View Project: ${projectName}` : 'View Project'} →
          </button>
        )}
        <button
          onClick={() => setShowDeleteModal(true)}
          className="shrink-0 px-3.5 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs font-semibold rounded-lg transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="size-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
          </svg>
        </button>
      </div>

      {/* Project created banner */}
      {projectJustCreated && (
        <div className="shrink-0 mx-4 mt-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between gap-3 animate-fadein">
          <div className="flex items-center gap-2 text-sm text-emerald-700">
            <span>✓</span>
            <span className="font-semibold">Project created!</span>
            <span className="text-emerald-600 text-xs hidden sm:inline">Tech Lead is planning now.</span>
          </div>
          <button
            onClick={() => onProjectCreated(projectId)}
            className="shrink-0 px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-lg transition-colors"
          >
            View Project →
          </button>
        </div>
      )}

      <ChatCore
        messages={messages}
        loading={loading}
        sending={sending}
        onSend={handleSend}
        emptyMessage={{ title: 'Conversation is empty', subtitle: 'Start by describing your product idea.' }}
        placeholder="Continue the conversation…"
        theme="violet"
      />

      {showDeleteModal && (
        <ConfirmModal
          message="Once deleted, this conversation can't be recovered."
          onConfirmed={() => { api.deletePMConversation(conversationId).then(() => onBack()) }}
          onClose={() => setShowDeleteModal(false)}
        />
      )}
    </div>
  )
}
