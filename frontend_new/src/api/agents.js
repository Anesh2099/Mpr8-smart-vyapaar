import apiClient from './client';

export const agentApi = {
    // Master Chat — longer timeout because it chains multiple LLM calls
    chat: async (query, sessionId = 'default_session', storeId = 'store001') => {
        const { data } = await apiClient.post('/agent/master/chat', {
            query,
            session_id: sessionId,
            store_id: storeId,
        }, { timeout: 60000 });
        return data;
    },

    getChatHistory: async (sessionId) => {
        const { data } = await apiClient.get(`/agent/chat/${sessionId}`);
        return data;
    },

    clearChatHistory: async (sessionId) => {
        const { data } = await apiClient.delete(`/agent/chat/${sessionId}`);
        return data;
    },

    // Proactive Alerts
    getAlerts: async (storeId = 'store001', limit = 20) => {
        const { data } = await apiClient.get(`/agent/alerts?store_id=${storeId}&limit=${limit}`);
        return data;
    },

    dismissAlert: async (alertId) => {
        const { data } = await apiClient.delete(`/agent/alerts/${alertId}`);
        return data;
    },
};
