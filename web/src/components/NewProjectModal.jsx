import { useState } from 'react'
import { api } from '../api'

export default function NewProjectModal({ onClose, onCreated }) {
  const [idea, setIdea]       = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!idea.trim()) return
    setLoading(true)
    setError('')
    try {
      const data = await api.createFromIdea(idea.trim())
      onCreated(data.project_id)
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg animate-fadein overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-indigo-500 to-violet-500" />
        <div className="px-6 py-5">
          <h2 className="text-lg font-bold text-slate-900 mb-1">New Project</h2>
          <p className="text-sm text-slate-500 mb-4">
            Describe your idea — the Tech Lead will ask questions and build a plan.
          </p>

          <form onSubmit={handleSubmit}>
            <textarea
              value={idea}
              onChange={e => setIdea(e.target.value)}
              placeholder="e.g. Build a user auth system with email/password login, OAuth, and password reset flow…"
              rows={5}
              autoFocus
              className="w-full text-sm px-4 py-3 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 placeholder:text-slate-400 bg-slate-50 transition-shadow"
            />
            {error && (
              <p className="text-red-500 text-xs mt-2 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
            )}
            <div className="flex justify-end gap-3 mt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !idea.trim()}
                className="px-5 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              >
                {loading ? 'Creating…' : 'Create Project →'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
