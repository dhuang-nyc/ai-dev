import { useState } from 'react'
import { marked } from 'marked'

export default function TechSpecPanel({ techSpec }) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <button
        onClick={() => setCollapsed(c => !c)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/80 hover:bg-slate-100/60 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-5 h-5 bg-violet-500 rounded-md flex items-center justify-center text-white text-xs font-bold shrink-0">S</div>
          <span className="text-sm font-semibold text-slate-700">Tech Spec</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">v{techSpec.version}</span>
          <span className="text-slate-400 text-xs">{collapsed ? '▶' : '▼'}</span>
        </div>
      </button>

      {!collapsed && (
        <div
          className="px-6 py-5 md-prose text-sm"
          dangerouslySetInnerHTML={{ __html: marked.parse(techSpec.content, { breaks: true, gfm: true }) }}
        />
      )}
    </div>
  )
}
