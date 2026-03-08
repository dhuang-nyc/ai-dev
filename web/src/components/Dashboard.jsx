import { useState, useEffect } from "react";
import { api } from "../api";
import {
  STATUS_COLORS,
  STATUS_LABELS,
  TASK_STATUS_COLORS,
  TASK_STATUS_LABELS,
} from "../utils";
import TaskModal from "./TaskModal";

export default function Dashboard({ projects, onNewProject, onSelectProject }) {
  const [tasks, setTasks] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [selectedTaskId, setSelectedTaskId] = useState(null);

  function fetchTasks() {
    return Promise.all([api.getActiveTasks(), api.getWorkspaces()])
      .then(([t, w]) => {
        setTasks(t);
        setWorkspaces(w);
        setLoadingTasks(false);
      })
      .catch(() => setLoadingTasks(false));
  }

  useEffect(() => {
    fetchTasks();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pendingTasks = tasks.filter((t) => t.status === "pending");
  const activeTasks = tasks.filter((t) => t.status !== "pending");
  const availableWs = workspaces.filter((w) => w.is_available).length;

  async function handleRunDevAgents() {
    setRunning(true);
    setRunResult(null);
    try {
      const result = await api.runDevAgents();
      setRunResult(result);
      await fetchTasks();
    } catch (e) {
      setRunResult({ message: e.message });
    } finally {
      setRunning(false);
    }
  }

  const stats = [
    {
      label: "Total Projects",
      value: projects.length,
      color: "indigo",
    },
    {
      label: "In Progress",
      value: projects.filter((p) => p.status === "in_progress").length,
      color: "cyan",
    },
    {
      label: "Planning",
      value: projects.filter(
        (p) => p.status === "planning" || p.status === "approved",
      ).length,
      color: "blue",
    },
    {
      label: "Completed",
      value: projects.filter((p) => p.status === "completed").length,
      color: "emerald",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 animate-fadein space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{greeting()} ✦</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {projects.length === 0
              ? "No projects yet — start your first one."
              : `${projects.length} project${projects.length !== 1 ? "s" : ""} in your workspace`}
          </p>
        </div>
        <button
          onClick={onNewProject}
          className="px-5 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-indigo-200"
        >
          + New Project
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* Recent projects */}
      {projects.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">
            Recent Projects
          </h2>
          <div className="grid grid-cols-3 gap-3">
            {projects.slice(0, 6).map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                onClick={() => onSelectProject(p.id)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Workspaces */}
      {workspaces.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">
            Workspaces
            <span className="ml-2 text-xs font-normal text-slate-400 normal-case tracking-normal">
              {availableWs}/{workspaces.length} available
            </span>
          </h2>
          <div className="flex flex-wrap gap-2">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium ${
                  ws.is_available
                    ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                    : "bg-slate-50 border-slate-200 text-slate-600"
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    ws.is_available
                      ? "bg-emerald-400"
                      : "bg-cyan-400 animate-pulse"
                  }`}
                />
                <span>{ws.name}</span>
                {!ws.is_available && ws.current_task_title && (
                  <span className="text-slate-400 truncate max-w-[140px]">
                    — {ws.current_task_title}
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Active & pending tasks */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">
            Tasks
          </h2>
          <div className="flex items-center gap-3">
            {runResult && (
              <span className="text-xs text-slate-500 animate-fadein">
                {runResult.message}
              </span>
            )}
            <button
              onClick={handleRunDevAgents}
              disabled={running}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-semibold rounded-lg transition-all hover:-translate-y-0.5 shadow-sm shadow-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
            >
              {running ? (
                <span className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                "▶"
              )}
              Run Dev Agents
            </button>
          </div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          {loadingTasks ? (
            <div className="flex justify-center py-10">
              <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : activeTasks.length === 0 && pendingTasks.length === 0 ? (
            <p className="text-center text-slate-400 text-sm py-10">
              No tasks currently in progress.
            </p>
          ) : (
            <div className="divide-y divide-slate-100">
              {activeTasks.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onSelectProject={onSelectProject}
                  onOpenTask={setSelectedTaskId}
                />
              ))}
              {pendingTasks.length > 0 && (
                <>
                  {activeTasks.length > 0 && (
                    <div className="px-5 py-2 bg-slate-50 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Pending
                    </div>
                  )}
                  {pendingTasks.map((task) => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      onSelectProject={onSelectProject}
                      onOpenTask={setSelectedTaskId}
                    />
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Empty state */}
      {projects.length === 0 && (
        <div className="flex flex-col items-center py-12 text-center">
          <div className="w-14 h-14 bg-gradient-to-br from-indigo-100 to-violet-100 rounded-2xl flex items-center justify-center mb-3 text-2xl select-none">
            ✦
          </div>
          <p className="text-slate-400 text-sm max-w-xs">
            Start your first project by describing an idea to the AI Tech Lead.
          </p>
        </div>
      )}

      {selectedTaskId && (
        <TaskModal
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
          onSaved={(updated) =>
            setTasks((prev) =>
              prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)),
            )
          }
        />
      )}
    </div>
  );
}

const STAT_COLORS = {
  indigo:
    "bg-gradient-to-br from-indigo-50  to-indigo-100/60  border-indigo-200/70  text-indigo-700",
  cyan: "bg-gradient-to-br from-cyan-50    to-cyan-100/60    border-cyan-200/70    text-cyan-700",
  blue: "bg-gradient-to-br from-blue-50    to-blue-100/60    border-blue-200/70    text-blue-700",
  emerald:
    "bg-gradient-to-br from-emerald-50 to-emerald-100/60 border-emerald-200/70 text-emerald-700",
};

function StatCard({ label, value, color }) {
  return (
    <div className={`${STAT_COLORS[color]} border rounded-2xl px-5 py-4`}>
      <div className="text-3xl font-bold tabular-nums">{value}</div>
      <div className="text-xs font-medium mt-1 opacity-60">{label}</div>
    </div>
  );
}

function ProjectCard({ project, onClick }) {
  const c = STATUS_COLORS[project.status] ?? STATUS_COLORS.draft;
  return (
    <button
      onClick={onClick}
      className="text-left bg-white border border-slate-200 rounded-2xl p-4 hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5 transition-all duration-150 shadow-sm group"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="font-semibold text-sm text-slate-800 group-hover:text-indigo-600 transition-colors line-clamp-2 leading-snug">
          {project.name}
        </div>
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${c.badge}`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${c.dot} ${
              project.status === "in_progress" ? "animate-pulse" : ""
            }`}
          />
          {STATUS_LABELS[project.status] ?? project.status}
        </span>
      </div>

      {project.description && (
        <p className="text-xs text-slate-500 line-clamp-2 mb-2.5 leading-relaxed">
          {project.description}
        </p>
      )}

      <div className="flex items-center gap-2 text-xs text-slate-400">
        {project.task_count > 0 && (
          <span>
            {project.task_count} task{project.task_count !== 1 ? "s" : ""}
          </span>
        )}
        {project.task_count > 0 && project.has_tech_spec && <span>·</span>}
        {project.has_tech_spec && <span className="text-violet-400">spec</span>}
      </div>
    </button>
  );
}

function TaskRow({ task, onSelectProject, onOpenTask }) {
  return (
    <div
      className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50/70 transition-colors cursor-pointer"
      onClick={() => onOpenTask(task.id)}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-slate-800 truncate">
          {task.title}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelectProject(task.project_id);
            }}
            className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
          >
            {task.project_name}
          </button>
          {task.pr_url && (
            <a
              href={task.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 hover:underline"
            >
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354Z" />
              </svg>
              PR
            </a>
          )}
          {task.has_logs && <span className="text-xs text-slate-400">💬</span>}
        </div>
      </div>
      <span className="text-xs text-slate-400 tabular-nums shrink-0">
        p{task.priority}
      </span>
      <span
        className={`text-xs font-semibold px-2.5 py-1 rounded-full shrink-0 ${
          TASK_STATUS_COLORS[task.status] ?? "bg-slate-100 text-slate-600"
        }`}
      >
        {TASK_STATUS_LABELS[task.status] ?? task.status}
      </span>
    </div>
  );
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
