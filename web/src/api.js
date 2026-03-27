class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function req(method, path, body) {
  const opts = { method, headers: {}, credentials: 'include' }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method.toUpperCase())) {
    opts.headers['X-CSRFToken'] = getCsrfToken()
  }
  const res = await fetch('/api' + path, opts)
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const d = await res.json(); msg = d.detail ?? JSON.stringify(d) } catch { /* empty */ }
    throw new ApiError(res.status, msg)
  }
  return res.json()
}

export const api = {
  me:             ()             => req('GET',  '/auth/me/'),
  login:          (u, p)        => req('POST', '/auth/login/', { username: u, password: p }),
  logout:         ()             => req('POST', '/auth/logout/'),
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
  // PM
  listPMConversations:    ()             => req('GET',  '/pm/conversations/'),
  getPMConversation:      (id)           => req('GET',  `/pm/conversations/${id}/`),
  createPMConversation:   ()             => req('POST', '/pm/conversations/'),
  sendPMMessage:          (id, content)  => req('POST', `/pm/conversations/${id}/chat/`, { content }),
  getPMMessages:          (id)           => req('GET',  `/pm/conversations/${id}/messages/`),
  getPMMessage:           (id)           => req('GET',  `/pm/messages/${id}/`),
  getProjectPMConversation: (id)         => req('GET',  `/projects/${id}/pm-conversation/`),
  deletePMConversation:     (id)           => req('DELETE', `/pm/conversations/${id}/`),
}
