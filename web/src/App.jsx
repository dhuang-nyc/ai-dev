import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ProjectDetail from "./components/ProjectDetail";
import NewProjectModal from "./components/NewProjectModal";
import LoginPage from "./components/LoginPage";
import { api } from "./api";
import Dashboard from "./components/Dashboard";
import { APP_NAME } from "./utils";

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [project, setProject] = useState(null);
  const [loadingProject, setLoading] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 sm:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar
        projects={projects}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onNewProject={() => setShowNewModal(true)}
        onLogout={handleLogout}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex-1 overflow-y-auto">
        {/* Mobile top bar */}
        <div className="sm:hidden sticky top-0 z-20 flex items-center gap-3 px-4 py-3 bg-white border-b border-slate-200">
          <button
            onClick={() => setSidebarOpen(true)}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 transition-colors text-lg"
          >
            ☰
          </button>
          <span className="font-bold text-sm text-slate-900">{APP_NAME}</span>
        </div>

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
