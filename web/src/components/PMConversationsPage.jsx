import { useState, useEffect } from 'react'
import { api } from '../api'

export default function PMConversationsPage({ onSelectConv, onNewConv, onSelectProject }) {
  const [convs, setConvs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listPMConversations()
      .then(setConvs)
      .catch(() => setError('Failed to load conversations.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="w-full animate-fadein px-4 py-8 sm:px-12 sm:py-12 flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">PM Conversations</h1>
          <p className="text-sm text-slate-500 mt-0.5">Ideas you've been developing with the Product Manager</p>
        </div>
        <button
          onClick={onNewConv}
          className="px-4 py-2.5 bg-violet-500 hover:bg-violet-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-violet-200"
        >
          ✦ New Idea
        </button>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-6 h-6 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <p className="text-center text-red-400 text-sm py-12">{error}</p>
      ) : convs.length === 0 ? (
        <div className="flex flex-col items-center py-16 gap-3 text-center">
          <div className="w-12 h-12 bg-violet-100 rounded-2xl flex items-center justify-center text-2xl select-none">✦</div>
          <p className="text-slate-500 text-sm font-medium">No conversations yet</p>
          <p className="text-slate-400 text-xs max-w-xs">Start by describing a product idea to the PM.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {convs.map(conv => (
            <ConvCard
              key={conv.id}
              conv={conv}
              onOpen={() => onSelectConv(conv.id)}
              onGoProject={() => onSelectProject(conv.project_id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ConvCard({ conv, onOpen, onGoProject }) {
  const hasProject = !!conv.project_id
  const date = new Date(conv.created_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 hover:border-violet-200 hover:shadow-sm transition-all duration-150 flex items-start gap-4">
      {/* Status dot */}
      <div className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${hasProject ? 'bg-emerald-400' : 'bg-violet-400 animate-pulse'}`} />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {hasProject ? (
            <span className="text-xs font-semibold px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full">
              Project Created
            </span>
          ) : (
            <span className="text-xs font-semibold px-2 py-0.5 bg-violet-50 text-violet-700 border border-violet-200 rounded-full">
              In Progress
            </span>
          )}
          <span className="text-xs text-slate-400">{date}</span>
          {conv.message_count > 0 && (
            <span className="text-xs text-slate-400">· {conv.message_count} messages</span>
          )}
        </div>
        {conv.preview ? (
          <p className="mt-1.5 text-sm text-slate-700 line-clamp-2 leading-relaxed">{conv.preview}</p>
        ) : (
          <p className="mt-1.5 text-sm text-slate-400 italic">No messages yet</p>
        )}
        {hasProject && conv.project_name && (
          <p className="mt-1 text-xs text-slate-500">
            Project: <span className="font-medium text-slate-700">{conv.project_name}</span>
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 shrink-0">
        {hasProject && (
          <button
            onClick={onGoProject}
            className="px-3 py-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors"
          >
            View Project →
          </button>
        )}
        <button
          onClick={onOpen}
          className="px-3 py-1.5 text-xs font-semibold text-violet-700 bg-violet-50 border border-violet-200 rounded-lg hover:bg-violet-100 transition-colors"
        >
          Continue →
        </button>
      </div>
    </div>
  )
}
