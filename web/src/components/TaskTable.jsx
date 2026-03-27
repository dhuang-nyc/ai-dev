import { useState } from "react";
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

function TaskRow({ task, index, onOpenTask, onOpenLog, onSelectProject }) {
  const hasLog = task.has_logs || task.agent_log?.trim();
  const duration = task.completed_at - task.started_at;

  return (
    <div
      className="flex items-start gap-4 px-5 py-3.5 hover:bg-slate-50/70 transition-colors cursor-pointer"
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
          {/* Project link — Dashboard only */}
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

          {/* Blocked-by badges — TasksPanel only */}
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

          {/* PR link */}
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

          {/* Agent log button */}
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
          <AgentCostSummary cost={task.total_cost} timeMs={duration} />
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
      </div>
    </div>
  );
}

/**
 * Shared task table used by Dashboard and TasksPanel.
 *
 * Props:
 *   tasks           – array of task objects (DashboardTaskSchema or DevTaskSchema)
 *   onSelectProject – (projectId) => void   dashboard only; when provided shows project name link
 *   onTaskSaved     – (updatedTask) => void  called after task modal saves
 *   showIndex       – bool, default false    show row numbers (TasksPanel style)
 */
export default function TaskTable({
  tasks,
  onSelectProject,
  onTaskSaved,
  showIndex = false,
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [logTaskId, setLogTaskId] = useState(null);

  const sorted = sortTasks(tasks);

  return (
    <>
      <div className="divide-y divide-slate-50">
        {sorted.map((task, i) => (
          <TaskRow
            key={task.id}
            task={task}
            index={showIndex ? i + 1 : null}
            onOpenTask={setSelectedId}
            onOpenLog={setLogTaskId}
            onSelectProject={onSelectProject}
          />
        ))}
      </div>

      {selectedId && (
        <TaskModal
          taskId={selectedId}
          onClose={() => setSelectedId(null)}
          onSaved={(updated) => {
            setSelectedId(null);
            onTaskSaved?.(updated);
          }}
        />
      )}

      {logTaskId && (
        <AgentLogModal taskId={logTaskId} onClose={() => setLogTaskId(null)} />
      )}
    </>
  );
}
