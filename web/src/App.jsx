import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ProjectDetail from "./components/ProjectDetail";
import NewProjectModal from "./components/NewProjectModal";
import { api } from "./api";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [project, setProject] = useState(null);
  const [loadingProject, setLoading] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);

  const fetchProjects = useCallback(async () => {
    try {
      setProjects(await api.listProjects());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    if (!selectedId) {
      setProject(null);
      return;
    }
    setLoading(true);
    api
      .getProject(selectedId)
      .then((p) => {
        setProject(p);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedId]);

  async function handleRefresh() {
    await fetchProjects();
    if (selectedId) {
      try {
        setProject(await api.getProject(selectedId));
      } catch {
        /* empty */
      }
    }
  }

  function handleProjectCreated(projectId) {
    setShowNewModal(false);
    fetchProjects();
    setSelectedId(projectId);
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      <Sidebar
        projects={projects}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onNewProject={() => setShowNewModal(true)}
      />

      <main className="flex-1 overflow-y-auto">
        {loadingProject ? (
          <div className="flex items-center justify-center h-full">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : project ? (
          <ProjectDetail
            key={selectedId}
            project={project}
            onRefresh={handleRefresh}
          />
        ) : (
          <Dashboard
            projects={projects}
            onNewProject={() => setShowNewModal(true)}
            onSelectProject={setSelectedId}
          />
        )}
      </main>

      {showNewModal && (
        <NewProjectModal
          onClose={() => setShowNewModal(false)}
          onCreated={handleProjectCreated}
        />
      )}
    </div>
  );
}

