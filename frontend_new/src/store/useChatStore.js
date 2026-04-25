import { create } from 'zustand';
import { agentApi } from '@/api/agents';

const STORAGE_KEY = 'kiranaiq_chat_sessions';
const MAX_SESSIONS = 10;

// ── Helpers ──────────────────────────────────────────────────────────────────
const loadSessions = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
};

const saveSessions = (sessions, currentSessionId) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessions, currentSessionId }));
  } catch { /* ignore */ }
};

const WELCOME_MSG = {
  id: 1,
  role: 'assistant',
  content: "Hello! I'm **Agent Saarthi**, your AI business assistant. How can I help you manage your shop today?",
  timestamp: new Date().toISOString(),
};

const createNewSession = (label) => ({
  id: `session_${Date.now()}`,
  label: label || `Chat ${new Date().toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })}`,
  createdAt: new Date().toISOString(),
  messages: [{ ...WELCOME_MSG, id: Date.now() }],
});

// ── Load persisted state ──────────────────────────────────────────────────────
const persisted = loadSessions();
const initialSessions = persisted?.sessions?.length > 0 ? persisted.sessions : [createNewSession('Default')];
const initialSessionId = persisted?.currentSessionId || initialSessions[0].id;
const initialMessages = initialSessions.find(s => s.id === initialSessionId)?.messages || [{ ...WELCOME_MSG }];

// ─────────────────────────────────────────────────────────────────────────────

const useChatStore = create((set, get) => ({
  // Chat state
  messages: initialMessages,
  isTyping: false,
  sessionId: initialSessionId,

  // Chat history
  sessions: initialSessions,
  showHistory: false,

  // UI state
  isChatPanelOpen: true,

  // Agent activity
  activeAgents: [],
  agentLogs: [],

  // Shop info
  shopInfo: {
    name: "Devanshu's Store",
    owner: 'Devanshu',
    location: 'Mumbai, India',
    id: 'store001',
  },

  // Actions
  addMessage: (message) => set((state) => {
    const newMsg = {
      ...message,
      id: Date.now() + Math.random(),
      timestamp: new Date().toISOString(),
    };
    const updatedMessages = [...state.messages, newMsg];
    // Persist to sessions
    const updatedSessions = state.sessions.map(s =>
      s.id === state.sessionId ? { ...s, messages: updatedMessages } : s
    );
    saveSessions(updatedSessions, state.sessionId);
    return { messages: updatedMessages, sessions: updatedSessions };
  }),

  sendMessageToAgent: async (content) => {
    const { addMessage, sessionId, shopInfo } = get();

    addMessage({ role: 'user', content });
    set({ isTyping: true });

    try {
      const response = await agentApi.chat(content, sessionId, shopInfo.id);

      if (response.agent_trace?.length > 0) {
        set({ activeAgents: response.agent_trace });
      }

      addMessage({
        role: 'assistant',
        content: response.message || "I processed your request, but received an empty response.",
        actionCards: response.action_cards || [],
        alerts: response.alerts || [],
      });

    } catch (error) {
      console.error("Chat API Error:", error);
      addMessage({
        role: 'assistant',
        content: "Sorry, I encountered an error communicating with the backend agents.",
        isError: true,
      });
    } finally {
      set({ isTyping: false });
    }
  },

  // Start a fresh chat session
  startNewSession: () => {
    const { sessions } = get();
    const newSession = createNewSession();
    const trimmedSessions = [newSession, ...sessions].slice(0, MAX_SESSIONS);
    saveSessions(trimmedSessions, newSession.id);
    set({
      sessions: trimmedSessions,
      sessionId: newSession.id,
      messages: newSession.messages,
      showHistory: false,
    });
  },

  // Switch to an existing session
  switchSession: (sessionId) => {
    const { sessions } = get();
    const session = sessions.find(s => s.id === sessionId);
    if (!session) return;
    saveSessions(sessions, sessionId);
    set({
      sessionId,
      messages: session.messages,
      showHistory: false,
    });
  },

  // Delete a session
  deleteSession: (sessionId) => {
    const { sessions, sessionId: currentId, startNewSession } = get();
    const remaining = sessions.filter(s => s.id !== sessionId);
    if (remaining.length === 0) {
      startNewSession();
      return;
    }
    const newActive = currentId === sessionId ? remaining[0] : sessions.find(s => s.id === currentId);
    saveSessions(remaining, newActive.id);
    set({
      sessions: remaining,
      sessionId: newActive.id,
      messages: newActive.messages,
      showHistory: false,
    });
  },

  toggleHistory: () => set((state) => ({ showHistory: !state.showHistory })),

  toggleChatPanel: () => set((state) => ({
    isChatPanelOpen: !state.isChatPanelOpen
  })),

  setChatPanelOpen: (isOpen) => set({ isChatPanelOpen: isOpen }),

  addAgentLog: (log) => set((state) => ({
    agentLogs: [...state.agentLogs, {
      ...log,
      id: Date.now(),
      timestamp: new Date().toISOString(),
    }]
  })),

  setActiveAgents: (agents) => set({ activeAgents: agents }),

  updateShopInfo: (info) => set((state) => ({
    shopInfo: { ...state.shopInfo, ...info }
  })),

  clearMessages: () => set({ messages: [] }),
}));

export default useChatStore;
