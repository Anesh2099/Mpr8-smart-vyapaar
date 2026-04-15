import { create } from 'zustand';
import { agentApi } from '@/api/agents';

const useChatStore = create((set, get) => ({
  // Chat state
  messages: [
    {
      id: 1,
      role: 'assistant',
      content: 'Hello! I\'m your AI assistant. How can I help you manage your shop today?',
      timestamp: new Date().toISOString(),
    }
  ],
  isTyping: false,
  sessionId: 'session_' + Math.floor(Math.random() * 100000), // Generate random session ID for this window

  // UI state
  isChatPanelOpen: true,

  // Agent activity
  activeAgents: [],
  agentLogs: [],

  // Shop info
  shopInfo: {
    name: 'Devanshu\'s Store',
    owner: 'Devanshu',
    location: 'Mumbai, India',
    id: 'store001',
  },

  // Actions
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, {
      ...message,
      id: Date.now() + Math.random(),
      timestamp: new Date().toISOString(),
    }]
  })),

  sendMessageToAgent: async (content) => {
    const { addMessage, sessionId, shopInfo } = get();

    // 1. Add User Message
    addMessage({ role: 'user', content });

    // 2. Set Typing State
    set({ isTyping: true });

    try {
      // 3. Call Backend API
      const response = await agentApi.chat(content, sessionId, shopInfo.id);

      // 4. Update active agents badge based on trace
      if (response.agent_trace && response.agent_trace.length > 0) {
        set({ activeAgents: response.agent_trace });
      }

      // 5. Add AI Response Message (includes action cards/alerts if any)
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
      // 6. Remove Typing State
      set({ isTyping: false });
    }
  },

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

