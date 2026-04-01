import { useState } from "react";
import { api } from "../api";
import { TASK_STATUS_COLORS, TASK_STATUS_LABELS } from "../utils";
import TaskModal from "./TaskModal";
import AgentLogModal from "./AgentLogModal";
import AgentCostSummary from "./AgentCostSummary";

const STATUS_ORDER = {
  pr_open: 0,
  in_progress: 1,
  pending: 2,
  done: 3,
  aborted: 4,
};

function sortTasks(tasks) {
  return [...tasks].sort((a, b) => {
    const diff =
      (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99);
    if (diff !== 0) return diff;
    return (
      (a.order ?? 0) - (b.order ?? 0) || (a.priority ?? 0) - (b.priority ?? 0)
    );
  });
}

const PR_ICON = (
  <svg className="w-3 h-3 shrink-0" fill="currentColor" viewBox="0 0 16 16">
    <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354Z" />
  </svg>
);

function TaskRow({
  task,
  index,
  onOpenTask,
  onOpenLog,
  onSelectProject,
  onDelete,
}) {
  const hasLog = task.has_logs || task.agent_log?.trim();
  const duration = task.completed_at - task.started_at;
  const deletable = task.status === "pending" || task.status === "aborted";

  return (
    <div
      className="flex items-start gap-4 px-5 py-3.5 hover:bg-slate-50/70 transition-colors cursor-pointer group/row"
      onClick={() => onOpenTask(task.id)}
    >
      {index != null && (
        <span className="text-xs text-slate-400 font-semibold mt-0.5 w-5 shrink-0 text-right tabular-nums">
          {index}
        </span>
      )}

      <div className="min-w-0 flex-1">
        <div className="font-medium text-sm text-slate-800 truncate">
          {task.title}
        </div>

        {task.description && (
          <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">
            {task.description}
          </div>
        )}

        <div className="flex items-center gap-2 mt-1 flex-wrap">
          {onSelectProject && task.project_name && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSelectProject(task.project_id);
              }}
              className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
            >
              {task.project_name}
            </button>
          )}

          {task.blocked_by?.length > 0 && (
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
              {PR_ICON}
              PR
            </a>
          )}

          {hasLog && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onOpenLog(task.id);
              }}
              className="bg-black p-1 rounded-md hover:bg-slate-800 transition-colors leading-none"
              title="View agent log"
            >
              💬
            </button>
          )}
          <AgentCostSummary
            cost={task.total_cost}
            timeMs={task.total_duration_ms}
          />
        </div>
      </div>

      <div className="shrink-0 flex items-center gap-2 mt-0.5">
        <span className="text-xs text-slate-400 tabular-nums">
          p{task.priority}
        </span>
        <span
          className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
            TASK_STATUS_COLORS[task.status] ?? "bg-slate-100 text-slate-600"
          }`}
        >
          {TASK_STATUS_LABELS[task.status] ?? task.status}
        </span>
        {deletable && onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm(`Delete task "${task.title}"?`))
                onDelete(task.id);
            }}
            className="w-6 h-6 flex items-center justify-center rounded-md text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover/row:opacity-100"
            title="Delete task"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Self-contained task table with header, loading/empty states, and modals.
 *
 * Props:
 *   tasks           – array of task objects
 *   tableLabel      – header label (e.g. "Dev Tasks", "Tasks"); omit to skip header
 *   loading         – show loading spinner
 *   showIndex       – show row numbers
 *   onSelectProject – (projectId) => void; project links auto-appear when tasks span multiple projects
 *   onTasksChange   – (tasks) => void; called with the updated tasks array after save/delete
 */
export default function TaskTable({
  tasks,
  tableLabel,
  loading = false,
  showIndex = false,
  onSelectProject,
  onTasksChange,
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [logTaskId, setLogTaskId] = useState(null);

  const multiProject = new Set(tasks.map((t) => t.project_id)).size > 1;

  const counts = tasks.reduce((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {});

  function handleSaved(updated) {
    setSelectedId(null);
    onTasksChange?.(
      tasks.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)),
    );
  }

  async function handleDelete(taskId) {
    try {
      await api.deleteTask(taskId);
      onTasksChange?.(tasks.filter((t) => t.id !== taskId));
    } catch (e) {
      alert(e.message);
    }
  }

  function handleModalDeleted(id) {
    setSelectedId(null);
    onTasksChange?.(tasks.filter((t) => t.id !== id));
  }

  const sorted = sortTasks(tasks);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      {tableLabel && (
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 bg-indigo-500 rounded-md flex items-center justify-center text-white text-xs font-bold shrink-0">
              T
            </div>
            <span className="text-sm font-semibold text-slate-700">
              {tableLabel}
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
      )}

      {loading ? (
        <div className="flex justify-center py-10">
          <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : tasks.length === 0 ? (
        <p className="text-center text-slate-400 text-sm py-10">No tasks.</p>
      ) : (
        <div className="divide-y divide-slate-50">
          {sorted.map((task, i) => (
            <TaskRow
              key={task.id}
              task={task}
              index={showIndex ? i + 1 : null}
              onOpenTask={setSelectedId}
              onOpenLog={setLogTaskId}
              onSelectProject={multiProject ? onSelectProject : undefined}
              onDelete={onTasksChange ? handleDelete : undefined}
            />
          ))}
        </div>
      )}

      {selectedId && (
        <TaskModal
          taskId={selectedId}
          onClose={() => setSelectedId(null)}
          onSaved={handleSaved}
          onDeleted={handleModalDeleted}
        />
      )}

      {logTaskId && (
        <AgentLogModal taskId={logTaskId} onClose={() => setLogTaskId(null)} />
      )}
    </div>
  );
}
