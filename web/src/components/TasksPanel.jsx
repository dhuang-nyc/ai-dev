import { useState, useEffect } from "react";
import { api } from "../api";
import TaskTable from "./TaskTable";

export default function TasksPanel({ projectId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTasks(projectId)
      .then((t) => { setTasks(t); setLoading(false); })
      .catch(() => setLoading(false));
  }, [projectId]);

  if (!loading && tasks.length === 0) return null;

  return (
    <TaskTable
      tasks={tasks}
      tableLabel="Dev Tasks"
      loading={loading}
      showIndex
      onTasksChange={setTasks}
    />
  );
}
