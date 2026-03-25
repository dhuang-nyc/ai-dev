import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ProjectDetail from "./components/ProjectDetail";
import NewProjectModal from "./components/NewProjectModal";
import LoginPage from "./components/LoginPage";
import { api } from "./api";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [project, setProject] = useState(null);
  const [loadingProject, setLoading] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);

  useEffect(() => {
    api
      .me()
      .then((data) => {
        if (data.authenticated) setUser(data);
      })
      .catch(() => {})
      .finally(() => setAuthChecked(true));
  }, []);

  const fetchProjects = useCallback(async () => {
    try {
      setProjects(await api.listProjects());
    } catch (e) {
      if (e.status === 401) setUser(null);
      else console.error(e);
    }
  }, []);

  useEffect(() => {
    if (user) fetchProjects();
  }, [user, fetchProjects]);

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
      .catch((e) => {
        if (e.status === 401) setUser(null);
        setLoading(false);
      });
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

  async function handleLogout() {
    try {
      await api.logout();
    } catch {
      /* empty */
    }
    setUser(null);
    setProjects([]);
    setSelectedId(null);
    setProject(null);
  }

  if (!authChecked) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <LoginPage onLogin={setUser} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      <Sidebar
        projects={projects}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onNewProject={() => setShowNewModal(true)}
        onLogout={handleLogout}
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
