import { useState, useEffect, useRef } from "react";
import { marked } from "marked";
import { api } from "../api";
import ConfirmModal from "./ConfirmModal";

export default function PMConversationChat({
  conversationId,
  onBack,
  onProjectCreated,
}) {
  const [messages, setMessages] = useState([]);
  const [projectId, setProjectId] = useState(null);
  const [projectName, setProjectName] = useState(null);
  const [loading, setLoading] = useState(true);
  const [projectJustCreated, setProjectJustCreated] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef(null);
  const pollingRef = useRef(null);
  const inputRef = useRef(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Load conversation + messages
  useEffect(() => {
    Promise.all([
      api.getPMConversation(conversationId),
      api.getPMMessages(conversationId),
    ])
      .then(([conv, msgs]) => {
        setProjectId(conv.project_id);
        setMessages(msgs);
        setLoading(false);
        // Resume polling if last assistant message is still processing
        const last = msgs[msgs.length - 1];
        if (last?.role === "assistant" && last.processing) {
          setSending(true);
          startPolling(last.id);
        }
      })
      .catch(() => setLoading(false));

    return () => clearInterval(pollingRef.current);
  }, [conversationId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch project name when projectId is set
  useEffect(() => {
    if (!projectId) return;
    api
      .getProject(projectId)
      .then((p) => setProjectName(p.name))
      .catch(() => {});
  }, [projectId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (listRef.current)
      listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  // Focus input on load
  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

  function startPolling(msgId) {
    clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const msg = await api.getPMMessage(msgId);
        if (!msg.processing) {
          clearInterval(pollingRef.current);
          setSending(false);
          setMessages((prev) => prev.map((m) => (m.id === msgId ? msg : m)));
          if (msg.conversation_project_id && !projectId) {
            setProjectId(msg.conversation_project_id);
            setProjectJustCreated(true);
          }
        }
      } catch {
        clearInterval(pollingRef.current);
        setSending(false);
      }
    }, 2000);
  }

  async function send() {
    const content = input.trim();
    if (!content || sending) return;
    setInput("");
    setSending(true);

    const tempUser = {
      id: -Date.now(),
      role: "user",
      content,
      processing: false,
    };
    const tempAssistant = {
      id: -(Date.now() + 1),
      role: "assistant",
      content: "",
      processing: true,
    };
    setMessages((prev) => [...prev, tempUser, tempAssistant]);

    try {
      const data = await api.sendPMMessage(conversationId, content);
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id === tempUser.id) return { ...m, id: data.user_message_id };
          if (m.id === tempAssistant.id)
            return { ...m, id: data.assistant_message_id };
          return m;
        }),
      );
      startPolling(data.assistant_message_id);
    } catch {
      setMessages((prev) =>
        prev.filter((m) => m.id !== tempUser.id && m.id !== tempAssistant.id),
      );
      setSending(false);
    }
  }

  function handleViewProject() {
    onProjectCreated(projectId);
  }

  return (
    <div className="flex flex-col h-full animate-fadein">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors text-sm"
          >
            ←
          </button>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-violet-500 rounded-full animate-pulse" />
            <span className="text-sm font-semibold text-slate-700">
              Product Manager
            </span>
            <span className="text-xs text-slate-400 hidden sm:inline">
              — Conversation #{conversationId}
            </span>
          </div>
        </div>
        {projectId && (
          <button
            onClick={handleViewProject}
            className="shrink-0 px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-lg transition-colors"
          >
            {projectName ? `View Project: ${projectName}` : "View Project"} →
          </button>
        )}
        <button
          onClick={() => setShowDeleteModal(true)}
          className="shrink-0 px-3.5 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs font-semibold rounded-lg transition-colors"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
            className="size-4"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
            />
          </svg>
        </button>
      </div>

      {/* Project created banner (shown only when project was created in this session) */}
      {projectJustCreated && (
        <div className="shrink-0 mx-4 mt-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between gap-3 animate-fadein">
          <div className="flex items-center gap-2 text-sm text-emerald-700">
            <span>✓</span>
            <span className="font-semibold">Project created!</span>
            <span className="text-emerald-600 text-xs hidden sm:inline">
              Tech Lead is planning now.
            </span>
          </div>
          <button
            onClick={handleViewProject}
            className="shrink-0 px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-semibold rounded-lg transition-colors"
          >
            View Project →
          </button>
        </div>
      )}

      {/* Messages */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto flex flex-col gap-3 p-5 custom-scroll bg-slate-50/30"
      >
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center py-16 gap-2 text-center">
            <p className="text-slate-500 text-sm font-medium">
              Conversation is empty
            </p>
            <p className="text-slate-400 text-xs max-w-xs">
              Start by describing your product idea.
            </p>
          </div>
        ) : (
          messages.map((msg) => <PMBubble key={msg.id} msg={msg} />)
        )}
      </div>

      {/* Input */}
      <div className="shrink-0 flex gap-3 p-4 border-t border-slate-200 bg-white">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Continue the conversation…"
          rows={3}
          className="flex-1 text-sm px-3.5 py-2.5 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-400 placeholder:text-slate-400 bg-white transition-shadow"
        />
        <button
          onClick={send}
          disabled={sending || !input.trim() || loading}
          className="self-end px-5 py-2.5 bg-violet-500 hover:bg-violet-600 text-white text-sm font-semibold rounded-xl transition-all hover:-translate-y-0.5 shadow-md shadow-violet-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none whitespace-nowrap"
        >
          Send →
        </button>
      </div>
      {showDeleteModal && (
        <ConfirmModal
          message="Once deleted, this conversation can't be recovered."
          onConfirmed={() => {
            api.deletePMConversation(conversationId).then(() => {
              onBack();
            });
          }}
          onClose={() => setShowDeleteModal(false)}
        />
      )}
    </div>
  );
}

function PMBubble({ msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end animate-msg">
        <div className="max-w-[78%] px-4 py-2.5 bg-gradient-to-br from-violet-500 to-violet-600 text-white text-sm rounded-2xl rounded-br-sm shadow-sm shadow-violet-200 whitespace-pre-wrap leading-relaxed">
          {msg.content}
        </div>
      </div>
    );
  }
  if (msg.processing) {
    return (
      <div className="flex justify-start animate-msg">
        <div className="px-4 py-3 bg-white border border-slate-200 rounded-2xl rounded-bl-sm shadow-sm">
          <div className="typing-dots">
            <span />
            <span />
            <span />
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start animate-msg">
      <div
        className="max-w-[82%] px-4 py-3 bg-white border border-slate-200 text-slate-800 text-sm rounded-2xl rounded-bl-sm shadow-sm md-prose leading-relaxed"
        dangerouslySetInnerHTML={{
          __html: marked.parse(msg.content, { breaks: true, gfm: true }),
        }}
      />
    </div>
  );
}
