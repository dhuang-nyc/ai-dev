import { useState, useEffect } from "react";
import { api } from "../api";
import { STATUS_COLORS, STATUS_LABELS } from "../utils";
import TaskTable from "./TaskTable";
import ProjectAgentSummary from "./ProjectAgentSummary";


export default function Dashboard({ projects, onNewProject, onIterateIdea, onSelectProject }) {
  const [tasks, setTasks] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
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
    {
      label: "Available Agents",
      value: workspaces.filter((w) => w.is_available).length,
      color: "emerald",
    },
    {
      label: "Working DevAgents",
      value: tasks.filter(
        (t) => (t.status === "in_progress") | (t.status === "pr_open"),
      ).length,
      color: "cyan",
    },
    {
      label: "Open PRs",
      value: tasks.filter((t) => t.status === "pr_open").length,
      color: "indigo",
    },
    {
      label: "Completed Tasks",
      value: tasks.filter((t) => t.status === "done").length,
      color: "emerald",
    },
  ];

  return (
    <div className="w-full animate-fadein px-4 py-8 sm:px-12 sm:py-24 flex flex-col gap-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{greeting()} ✦</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {projects.length === 0
              ? "No projects yet — start your first one."
              : `${projects.length} project${projects.length !== 1 ? "s" : ""} in your workspace`}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={onIterateIdea}
            className="px-4 py-2.5 bg-violet-500 hover:bg-violet-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-violet-200"
          >
            ✦ Iterate a New Idea
          </button>
          <button
            onClick={onNewProject}
            className="px-4 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-indigo-200"
          >
            + New Project
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
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
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">
            Tasks
          </h2>
          <div className="flex items-center gap-3 flex-wrap">
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
        <TaskTable
          tasks={tasks}
          loading={loadingTasks}
          onSelectProject={onSelectProject}
          onTasksChange={setTasks}
        />
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

      <ProjectAgentSummary
        totalCost={project.total_cost}
        totalAgentTimeMs={project.total_agent_time_ms}
        className="mt-2 pt-2 border-t border-slate-100"
      />
    </button>
  );
}


function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
