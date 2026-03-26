import { useState } from "react";
import ChatPanel from "./ChatPanel";
import TechSpecPanel from "./TechSpecPanel";
import TasksPanel from "./TasksPanel";
import { STATUS_COLORS, STATUS_LABELS } from "../utils";
import { api } from "../api";

export default function ProjectDetail({ project, onRefresh }) {
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState("");

  const isTerminal =
    project.status === "completed" || project.status === "aborted";

  async function doAction(fn) {
    setActionLoading(true);
    setActionError("");
    try {
      await fn();
      onRefresh();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div className="w-full animate-fadein px-4 py-8 sm:px-12 sm:py-24 flex flex-col gap-8">
      {/* Project header */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="h-1 bg-gradient-to-r from-indigo-500 to-violet-500" />
        <div className="px-6 py-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-slate-900 truncate">
                {project.name}
              </h1>
              {project.description && (
                <p className="text-sm text-slate-500 mt-1 line-clamp-2">
                  {project.description}
                </p>
              )}
              {project.github_repo_url && (
                <a
                  href={project.github_repo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-indigo-500 hover:text-indigo-700 mt-2 transition-colors"
                >
                  🔗{" "}
                  {project.github_repo_url.replace("https://github.com/", "")}
                </a>
              )}
            </div>

            <div className="flex flex-col items-end gap-2 shrink-0">
              <StatusBadge status={project.status} />
              {!isTerminal && (
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  {project.status === "planning" && (
                    <Btn
                      onClick={() =>
                        doAction(() => api.approveProject(project.id))
                      }
                      loading={actionLoading}
                      color="emerald"
                    >
                      ✓ Approve &amp; Generate Tasks
                    </Btn>
                  )}
                  {project.status === "approved" && (
                    <Btn
                      onClick={() =>
                        doAction(() => api.startProject(project.id))
                      }
                      loading={actionLoading}
                      color="indigo"
                    >
                      ▶ Start Project
                    </Btn>
                  )}
                  {project.status === "in_progress" && (
                    <Btn
                      onClick={() => {
                        if (confirm("Mark project as completed?"))
                          doAction(() =>
                            api.markStatus(project.id, "completed"),
                          );
                      }}
                      loading={actionLoading}
                      color="emerald"
                    >
                      ✓ Complete
                    </Btn>
                  )}
                  <Btn
                    onClick={() => {
                      if (confirm("Abort this project?"))
                        doAction(() => api.markStatus(project.id, "aborted"));
                    }}
                    loading={actionLoading}
                    color="red"
                  >
                    ✕ Abort
                  </Btn>
                </div>
              )}
            </div>
          </div>

          {actionError && (
            <p className="text-red-500 text-xs mt-3 bg-red-50 px-3 py-2 rounded-lg">
              {actionError}
            </p>
          )}
        </div>
      </div>

      <ChatPanel projectId={project.id} />
      {project.tech_spec && <TechSpecPanel techSpec={project.tech_spec} />}
      <TasksPanel projectId={project.id} />
    </div>
  );
}

function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] ?? {
    dot: "bg-slate-400",
    badge: "bg-slate-100 text-slate-600",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${c.badge}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${c.dot} ${status === "in_progress" ? "animate-pulse" : ""}`}
      />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

const COLOR_MAP = {
  indigo: "bg-indigo-500 hover:bg-indigo-600 shadow-indigo-200",
  emerald: "bg-emerald-500 hover:bg-emerald-600 shadow-emerald-200",
  red: "bg-red-500 hover:bg-red-600 shadow-red-200",
};

function Btn({ children, onClick, loading, color }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`px-3.5 py-1.5 text-white text-xs font-semibold rounded-lg transition-all hover:-translate-y-0.5 shadow-md disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none ${COLOR_MAP[color]}`}
    >
      {children}
    </button>
  );
}
