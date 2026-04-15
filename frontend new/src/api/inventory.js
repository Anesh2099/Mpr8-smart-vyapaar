import apiClient from './client';

export const inventoryApi = {
    // Get all inventory status (with AI calculated fields like stock_status)
    getStatus: async (storeId = 'store001') => {
        const { data } = await apiClient.get(`/agent/inventory/status?store_id=${storeId}`);
        return data;
    },
    // Low stock items only
    getLowStock: async (storeId = 'store001') => {
        const { data } = await apiClient.get(`/agent/inventory/low-stock?store_id=${storeId}`);
        return data;
    },
    // Near-expiry items
    getExpiry: async (storeId = 'store001') => {
        const { data } = await apiClient.get(`/agent/inventory/expiry?store_id=${storeId}`);
        return data;
    },
    // Reorder quantity suggestion for a product
    getReorderQty: async (productId) => {
        const { data } = await apiClient.get(`/agent/inventory/reorder/${productId}`);
        return data;
    },
    // AI Pricing recommendation for a product
    getPricing: async (productId, storeId = 'store001') => {
        const { data } = await apiClient.get(`/agent/pricing/${productId}?store_id=${storeId}`);
        return data;
    },
    // Demand forecast for a product
    getForecast: async (productId) => {
        const { data } = await apiClient.get(`/agent/forecast/${productId}`);
        return data;
    },
    // Trigger full forecast pipeline (background task)
    runForecast: async () => {
        const { data } = await apiClient.post('/agent/forecast/run');
        return data;
    },
    // Festival stocking advice
    getFestivals: async () => {
        const { data } = await apiClient.get('/agent/festivals');
        return data;
    },
    addProduct: async (productData) => {
        const { data } = await apiClient.post('/agent/inventory/add', productData);
        return data;
    },
    updateProduct: async (productId, productData) => {
        const { data } = await apiClient.put(`/agent/inventory/edit/${productId}`, productData);
        return data;
    },
    deleteProduct: async (productId) => {
        const { data } = await apiClient.delete(`/agent/inventory/delete/${productId}`);
        return data;
    }
};