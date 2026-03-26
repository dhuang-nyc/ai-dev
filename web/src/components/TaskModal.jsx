import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { TASK_STATUS_COLORS, TASK_STATUS_LABELS } from "../utils";

export default function TaskModal({ taskId, onClose, onSaved }) {
  const [task, setTask]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState(null);
  const [dirty, setDirty]     = useState(false);

  const [title, setTitle]           = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt]         = useState("");
  const [status, setStatus]         = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api.getTask(taskId)
      .then((t) => {
        setTask(t);
        setTitle(t.title);
        setDescription(t.description);
        setPrompt(t.claude_prompt);
        setStatus(t.status);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [taskId]);

  useEffect(() => { load(); }, [load]);

  // Close on Escape
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const editable = task && task.status === "pending";

  function handleChange(setter) {
    return (e) => { setter(e.target.value); setDirty(true); };
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const payload = { status };
      if (editable) {
        payload.title = title;
        payload.description = description;
        payload.claude_prompt = prompt;
      }
      const updated = await api.updateTask(taskId, payload);
      setTask(updated);
      setDirty(false);
      onSaved?.(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4 bg-black/40 backdrop-blur-sm animate-fadein"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white sm:rounded-2xl shadow-2xl border border-slate-200 w-full h-dvh sm:h-auto sm:max-w-2xl sm:max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            {task && (
              <select
                value={status}
                onChange={(e) => { setStatus(e.target.value); setDirty(true); }}
                className={`text-xs font-semibold px-2.5 py-1 rounded-full border-0 cursor-pointer shrink-0 focus:outline-none focus:ring-2 focus:ring-indigo-400 ${
                  TASK_STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600"
                }`}
              >
                {Object.entries(TASK_STATUS_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            )}
            {task?.branch_name && (
              <span className="text-xs text-slate-400 font-mono truncate">{task.branch_name}</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors shrink-0"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-5">
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : !task ? (
            <p className="text-center text-slate-400 py-16">Task not found.</p>
          ) : (
            <>
              {/* Title */}
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  Title
                </label>
                {editable ? (
                  <input
                    className="w-full text-sm font-semibold text-slate-800 border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                    value={title}
                    onChange={handleChange(setTitle)}
                  />
                ) : (
                  <p className="text-sm font-semibold text-slate-800">{task.title}</p>
                )}
              </div>

              {/* PR link */}
              {task.pr_url && (
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Pull Request
                  </label>
                  <a
                    href={task.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 hover:underline font-medium"
                  >
                    <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 16 16">
                      <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354Z"/>
                    </svg>
                    {task.pr_url.replace("https://github.com/", "")}
                  </a>
                </div>
              )}

              {/* Description */}
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  Description
                </label>
                {editable ? (
                  <textarea
                    rows={3}
                    className="w-full text-sm text-slate-700 border border-slate-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                    value={description}
                    onChange={handleChange(setDescription)}
                  />
                ) : (
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">
                    {task.description || <span className="text-slate-400 italic">No description.</span>}
                  </p>
                )}
              </div>

              {/* Claude Prompt */}
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  Implementation Prompt
                </label>
                {editable ? (
                  <textarea
                    rows={10}
                    className="w-full text-xs font-mono text-slate-700 border border-slate-200 rounded-lg px-3 py-2 resize-y focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                    value={prompt}
                    onChange={handleChange(setPrompt)}
                  />
                ) : (
                  <pre className="text-xs font-mono text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 overflow-x-auto whitespace-pre-wrap">
                    {task.claude_prompt || <span className="text-slate-400 italic">No prompt.</span>}
                  </pre>
                )}
              </div>

            </>
          )}
        </div>

        {/* Footer */}
        {!loading && task && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 shrink-0">
            <div className="text-xs text-slate-400">
              {!editable && (
                <span className="italic">Fields locked — status only is editable</span>
              )}
              {error && <span className="text-red-500">{error}</span>}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onClose}
                className="px-4 py-1.5 text-sm text-slate-600 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Close
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !dirty}
                className="px-4 py-1.5 text-sm font-semibold bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
