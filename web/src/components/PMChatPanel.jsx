import { useState, useEffect } from 'react'
import { marked } from 'marked'
import { api } from '../api'

/**
 * Read-only view of the PM discovery conversation for a project page.
 * Only rendered when the project has a PM conversation.
 */
export default function PMChatPanel({ projectId }) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    api.getProjectPMConversation(projectId)
      .then(msgs => {
        setMessages(msgs)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [projectId])

  if (loading || messages.length === 0) return null

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Collapsible header */}
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
        <div className="flex flex-col gap-3 p-5 max-h-[480px] overflow-y-auto custom-scroll bg-slate-50/30">
          {messages.map(msg => (
            <PMBubble key={msg.id} msg={msg} />
          ))}
        </div>
      )}
    </div>
  )
}

function PMBubble({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] px-4 py-2.5 bg-gradient-to-br from-violet-500 to-violet-600 text-white text-sm rounded-2xl rounded-br-sm shadow-sm shadow-violet-200 whitespace-pre-wrap leading-relaxed">
          {msg.content}
        </div>
      </div>
    )
  }
  return (
    <div className="flex justify-start">
      <div
        className="max-w-[82%] px-4 py-3 bg-white border border-slate-200 text-slate-800 text-sm rounded-2xl rounded-bl-sm shadow-sm md-prose leading-relaxed"
        dangerouslySetInnerHTML={{ __html: marked.parse(msg.content, { breaks: true, gfm: true }) }}
      />
    </div>
  )
}
