import apiClient from './client';

export const salesApi = {
    // Get all sales for a store
    getSales: async (storeId = 'store001') => {
        const { data } = await apiClient.get(`/agent/sales/list?store_id=${storeId}`);
        return data;
    },

    // Add a new sale
    addSale: async (saleData) => {
        const { data } = await apiClient.post('/agent/sales/add', saleData);
        return data;
    },

    // Update an existing sale
    updateSale: async (saleId, saleData) => {
        const { data } = await apiClient.put(`/agent/sales/${saleId}`, saleData);
        return data;
    },

    // Delete a sale
    deleteSale: async (saleId) => {
        const { data } = await apiClient.delete(`/agent/sales/${saleId}`);
        return data;
    }
};
