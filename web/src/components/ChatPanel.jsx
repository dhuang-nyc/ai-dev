import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import ChatCore from './ChatCore'

export default function ChatPanel({ projectId }) {
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const pollingRef = useRef(null)

  useEffect(() => {
    api.getMessages(projectId).then(msgs => {
      setMessages(msgs)
      const processing = [...msgs].reverse().find(m => m.processing)
      if (processing) { setSending(true); startPolling(processing.id) }
    })
    return () => clearInterval(pollingRef.current)
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

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

  async function handleSend(content) {
    setSending(true)
    const tempUser = { id: -Date.now(), role: 'user', content, processing: false }
    const tempAssistant = { id: -(Date.now() + 1), role: 'assistant', content: '', processing: true }
    setMessages(prev => [...prev, tempUser, tempAssistant])

    try {
      const data = await api.sendMessage(projectId, content)
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
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/80">
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
          <span className="text-sm font-semibold text-slate-700">Chat with Tech Lead</span>
        </div>
        <span className="text-xs text-slate-400">Ctrl+Enter to send</span>
      </div>
      <ChatCore
        messages={messages}
        sending={sending}
        onSend={handleSend}
        emptyMessage={{ title: 'Start chatting with the Tech Lead to plan your feature.' }}
        placeholder="Describe your feature idea or ask a question…"
        theme="indigo"
        maxHeight="480px"
      />
    </div>
  )
}
