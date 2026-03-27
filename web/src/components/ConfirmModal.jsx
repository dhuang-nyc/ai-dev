export default function ConfirmModal({
  onClose,
  onConfirmed,
  message = null,
  safe = false,
}) {
  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-end sm:items-center justify-center z-50 sm:p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white w-full h-dvh sm:h-auto sm:rounded-2xl sm:max-w-lg animate-fadein overflow-hidden flex flex-col">
        <div className="h-1 bg-gradient-to-r from-indigo-500 to-violet-500 shrink-0" />
        <div className="px-6 py-5 flex flex-col flex-1">
          <div className="flex items-start justify-between mb-1">
            <h2 className="text-lg font-bold text-slate-900">Are you sure?</h2>
            <button
              type="button"
              onClick={onClose}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors shrink-0 -mt-0.5"
            >
              ✕
            </button>
          </div>
          {message && <p className="text-sm text-slate-500 mb-4">{message}</p>}

          <div
            className={`flex justify-between ${safe ? "flex-row-reverse" : ""}`}
          >
            <button
              onClick={onConfirmed}
              className={`px-4 py-2 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md ${safe ? "bg-slate-500" : "bg-red-500"}`}
            >
              Yes
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-400 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-slate-200"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
