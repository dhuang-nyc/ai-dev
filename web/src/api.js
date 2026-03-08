async function req(method, path, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch('/api' + path, opts)
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const d = await res.json(); msg = d.detail ?? JSON.stringify(d) } catch { /* empty */ }
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  getActiveTasks: ()             => req('GET',  '/tasks/'),
  getWorkspaces:  ()             => req('GET',  '/workspaces/'),
  listProjects:   ()             => req('GET',  '/projects/'),
  getProject:     (id)           => req('GET',  `/projects/${id}/`),
  getMessages:    (id)           => req('GET',  `/projects/${id}/messages/`),
  getMessage:     (id)           => req('GET',  `/messages/${id}/`),
  getTasks:       (id)           => req('GET',  `/projects/${id}/tasks/`),
  getTask:        (id)           => req('GET',  `/tasks/${id}/`),
  updateTask:     (id, data)     => req('PATCH', `/tasks/${id}/`, data),
  sendMessage:    (id, content)  => req('POST', `/projects/${id}/chat/`, { content }),
  createFromIdea: (idea)         => req('POST', '/projects/create-from-idea/', { idea }),
  approveProject: (id)           => req('POST', `/projects/${id}/approve/`),
  startProject:   (id)           => req('POST', `/projects/${id}/start/`),
  markStatus:     (id, status)   => req('POST', `/projects/${id}/mark-status/?status=${status}`),
  runDevAgents:   ()             => req('POST', '/dev-agent/run/'),
}
