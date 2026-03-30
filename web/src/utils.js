export const STATUS_COLORS = {
  draft:       { dot: 'bg-slate-400',   badge: 'bg-slate-100 text-slate-600'   },
  planning:    { dot: 'bg-blue-400',    badge: 'bg-blue-50 text-blue-700'      },
  approved:    { dot: 'bg-emerald-400', badge: 'bg-emerald-50 text-emerald-700'},
  in_progress: { dot: 'bg-cyan-400',   badge: 'bg-cyan-50 text-cyan-700'      },
  completed:   { dot: 'bg-green-500',  badge: 'bg-green-50 text-green-700'    },
  aborted:     { dot: 'bg-red-400',    badge: 'bg-red-50 text-red-700'        },
}

export const STATUS_LABELS = {
  draft:       'Draft',
  planning:    'Planning',
  approved:    'Approved',
  in_progress: 'In Progress',
  completed:   'Completed',
  aborted:     'Aborted',
}

export const TASK_STATUS_COLORS = {
  pending:     'bg-slate-100 text-slate-600',
  in_progress: 'bg-blue-50 text-blue-700',
  pr_open:     'bg-violet-50 text-violet-700',
  done:        'bg-green-50 text-green-700',
  aborted:     'bg-red-50 text-red-700',
}

export const TASK_STATUS_LABELS = {
  pending:     'Pending',
  in_progress: 'In Progress',
  pr_open:     'PR Open',
  done:        'Done',
  aborted:     'Aborted',
}

export const APP_NAME = "Capy AI";