import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";

export default function AgentLogModal({ taskId, onClose }) {
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const bottomRef = useRef(null);

  const load = useCallback(() => {
    api.getTask(taskId)
      .then((t) => { setTask(t); setLoading(false); })
      .catch(() => setLoading(false));
  }, [taskId]);

  useEffect(() => { load(); }, [load]);

  // Scroll to bottom once log is loaded
  useEffect(() => {
    if (!loading && task?.agent_log) {
      bottomRef.current?.scrollIntoView({ behavior: "instant" });
    }
  }, [loading, task]);

  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-zinc-800 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            {/* Traffic lights */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="w-3 h-3 rounded-full bg-zinc-700" />
              <span className="w-3 h-3 rounded-full bg-zinc-700" />
              <span className="w-3 h-3 rounded-full bg-zinc-700" />
            </div>
            <span className="text-xs font-mono text-zinc-400 truncate">
              {task ? `agent_log — ${task.title}` : "agent_log"}
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors shrink-0 text-xs"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4">
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : !task?.agent_log?.trim() ? (
            <p className="text-zinc-500 text-sm font-mono text-center py-16">
              No log output yet.
            </p>
          ) : (
            <pre className="text-xs font-mono text-emerald-400 whitespace-pre-wrap leading-relaxed break-words">
              {task.agent_log}
              <span ref={bottomRef} />
            </pre>
          )}
        </div>

        {/* Footer */}
        {!loading && task && (
          <div className="flex items-center justify-between px-5 py-2.5 border-t border-zinc-800 shrink-0">
            <span className="text-xs font-mono text-zinc-600">
              {task.agent_log
                ? `${task.agent_log.split("\n").length} lines`
                : "0 lines"}
            </span>
            <button
              onClick={load}
              className="text-xs font-mono text-zinc-500 hover:text-zinc-200 transition-colors px-2 py-1 rounded hover:bg-zinc-800"
            >
              ↻ refresh
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
