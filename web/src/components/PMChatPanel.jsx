import { useState, useEffect } from 'react'
import { api } from '../api'
import ChatCore from './ChatCore'

export default function PMChatPanel({ projectId }) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    api.getProjectPMConversation(projectId)
      .then(msgs => { setMessages(msgs); setLoading(false) })
      .catch(() => setLoading(false))
  }, [projectId])

  if (loading || messages.length === 0) return null

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50/80 hover:bg-slate-100/60 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2 bg-violet-400 rounded-full" />
          <span className="text-sm font-semibold text-slate-700">PM Discovery Chat</span>
          <span className="text-xs text-slate-400">{messages.length} messages · read-only</span>
        </div>
        <span className="text-slate-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <ChatCore
          messages={messages}
          theme="violet"
          readOnly
          maxHeight="480px"
        />
      )}
    </div>
  )
}
