import { STATUS_COLORS, STATUS_LABELS, APP_NAME } from "../utils";
import Logo from "./blocks/Logo";
export default function Sidebar({
  projects,
  selectedId,
  onSelect,
  onNewProject,
  onLogout,
  isOpen,
  onClose,
  pmPage,
  onShowPMList,
  onNewIdea,
}) {
  function handleSelect(id) {
    onSelect(id);
    onClose?.();
  }

  function handleShowPMList() {
    onShowPMList?.();
    onClose?.();
  }

  return (
    <aside
      className={`w-72 bg-slate-900 flex flex-col shrink-0 border-r border-slate-800
        fixed inset-y-0 left-0 z-40 transition-transform duration-300
        sm:relative sm:translate-x-0 sm:h-full
        ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-700/60">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Logo />
            <div>
              <div className="text-white font-bold text-sm tracking-tight">
                {APP_NAME}
              </div>
              <div className="text-slate-500 text-xs">Daisy's Dev Team</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="sm:hidden w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            ✕
          </button>
        </div>
      </div>

      {/* PM Ideas nav */}
      <div className="px-2 pt-3 pb-1 border-b border-slate-700/60">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest px-3 mb-1.5">
          PM Ideas
        </p>
        <button
          onClick={handleShowPMList}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
            pmPage !== null
              ? 'bg-violet-500/20 border-violet-500/40 text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/80 border-transparent'
          }`}
        >
          <span className="flex items-center gap-2">
            <span className="text-violet-400">✦</span>
            All Conversations
          </span>
        </button>
        <button
          onClick={() => { onNewIdea?.(); onClose?.(); }}
          className="w-full text-left px-3 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/80 border border-transparent transition-colors"
        >
          <span className="flex items-center gap-2">
            <span className="text-violet-400">+</span>
            New Idea
          </span>
        </button>
      </div>

      {/* Project list */}
      <div className="flex-1 overflow-y-auto px-2 py-3 custom-scroll">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest px-3 mb-2">
          Projects
        </p>
        {projects.length === 0 ? (
          <p className="text-slate-600 text-xs px-3 py-6 text-center">
            No projects yet
          </p>
        ) : (
          projects.map((p, i) => {
            const active = selectedId === p.id;
            const colors = STATUS_COLORS[p.status] ?? STATUS_COLORS.draft;
            return (
              <button
                key={p.id}
                onClick={() => handleSelect(p.id)}
                style={{ animationDelay: `${i * 35}ms` }}
                className={`w-full text-left px-3 py-2.5 rounded-lg mb-0.5 transition-all duration-150 animate-slidein border group ${
                  active
                    ? "bg-indigo-500/20 border-indigo-500/40"
                    : "hover:bg-slate-800/80 border-transparent"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${colors.dot} ${
                      p.status === "in_progress" ? "animate-pulse" : ""
                    }`}
                  />
                  <span
                    className={`font-medium text-sm truncate transition-colors ${
                      active
                        ? "text-white"
                        : "text-slate-300 group-hover:text-white"
                    }`}
                  >
                    {p.name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 mt-0.5 pl-[18px]">
                  <span className="text-xs text-slate-500">
                    {STATUS_LABELS[p.status] ?? p.status}
                  </span>
                  {p.task_count > 0 && (
                    <>
                      <span className="text-slate-600 text-xs">·</span>
                      <span className="text-xs text-slate-500">
                        {p.task_count} task{p.task_count !== 1 ? "s" : ""}
                      </span>
                    </>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-slate-700/60 flex flex-col gap-2">
        <button
          onClick={onNewProject}
          className="w-full py-2.5 px-4 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-indigo-900/40"
        >
          + New Project
        </button>
        <button
          onClick={onLogout}
          className="w-full py-2 px-4 text-slate-500 hover:text-slate-300 text-xs font-medium rounded-xl transition-colors hover:bg-slate-800/60"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
