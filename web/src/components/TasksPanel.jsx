import { useState, useEffect } from "react";
import { api } from "../api";
import { TASK_STATUS_COLORS, TASK_STATUS_LABELS } from "../utils";
import TaskTable from "./TaskTable";

export default function TasksPanel({ projectId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTasks(projectId)
      .then((t) => { setTasks(t); setLoading(false); })
      .catch(() => setLoading(false));
  }, [projectId]);

  if (loading || tasks.length === 0) return null;

  const counts = tasks.reduce((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/80">
        <div className="flex items-center gap-2.5">
          <div className="w-5 h-5 bg-indigo-500 rounded-md flex items-center justify-center text-white text-xs font-bold shrink-0">
            T
          </div>
          <span className="text-sm font-semibold text-slate-700">Dev Tasks</span>
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

      <TaskTable
        tasks={tasks}
        showIndex
        onTaskSaved={(updated) =>
          setTasks((prev) => prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)))
        }
      />
    </div>
  );
}
