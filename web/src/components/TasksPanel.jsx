import { useState, useEffect } from "react";
import { api } from "../api";
import { TASK_STATUS_COLORS, TASK_STATUS_LABELS } from "../utils";
import TaskModal from "./TaskModal";

export default function TasksPanel({ projectId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);

  function load() {
    api
      .getTasks(projectId)
      .then((t) => {
        setTasks(t);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading || tasks.length === 0) return null;

  const counts = tasks.reduce((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <>
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 bg-indigo-500 rounded-md flex items-center justify-center text-white text-xs font-bold shrink-0">
              T
            </div>
            <span className="text-sm font-semibold text-slate-700">
              Dev Tasks
            </span>
          </div>
          <div className="flex items-center gap-2">
            {Object.entries(counts).map(([status, n]) => (
              <span
                key={status}
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${TASK_STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600"}`}
              >
                {n} {TASK_STATUS_LABELS[status] ?? status}
              </span>
            ))}
          </div>
        </div>

        <div className="divide-y divide-slate-50">
          {tasks.map((task, i) => (
            <button
              key={task.id}
              onClick={() => setSelectedId(task.id)}
              className="w-full flex items-start gap-4 px-5 py-3.5 hover:bg-slate-50/60 transition-colors text-left"
            >
              <span className="text-xs text-slate-400 font-semibold mt-0.5 w-5 shrink-0 text-right tabular-nums">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-sm text-slate-800">
                  {task.title}
                </div>
                {task.description && (
                  <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">
                    {task.description}
                  </div>
                )}
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  {task.blocked_by.length > 0 && (
                    <>
                      <span className="text-xs text-slate-400">blocked by</span>
                      {task.blocked_by.map((id) => (
                        <span
                          key={id}
                          className="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded-md"
                        >
                          #{id}
                        </span>
                      ))}
                    </>
                  )}
                  {task.pr_url && (
                    <a
                      href={task.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 hover:underline"
                    >
                      <svg
                        className="w-3 h-3"
                        fill="currentColor"
                        viewBox="0 0 16 16"
                      >
                        <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354Z" />
                      </svg>
                      PR
                    </a>
                  )}
                  {task.agent_log?.trim() && (
                    <span className="text-xs text-slate-400">💬</span>
                  )}
                </div>
              </div>
              <div className="shrink-0 flex items-center gap-2">
                <span className="text-xs text-slate-400 tabular-nums">
                  p{task.priority}
                </span>
                <span
                  className={`text-xs font-semibold px-2.5 py-1 rounded-full ${TASK_STATUS_COLORS[task.status] ?? "bg-slate-100 text-slate-600"}`}
                >
                  {TASK_STATUS_LABELS[task.status] ?? task.status}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {selectedId && (
        <TaskModal
          taskId={selectedId}
          onClose={() => setSelectedId(null)}
          onSaved={(updated) => {
            setTasks((prev) =>
              prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)),
            );
          }}
        />
      )}
    </>
  );
}
