import apiClient from './client';

export const supplierApi = {
    // Get all known suppliers
    getSuppliers: async (storeId = 'store001') => {
        const { data } = await apiClient.get(`/agent/supplier/list?store_id=${storeId}`);
        return data;
    },

    // Get active purchase orders
    getPurchaseOrders: async (storeId = 'store001') => {
        const { data } = await apiClient.get(`/agent/supplier/orders?store_id=${storeId}`);
        return data;
    },

    addPurchaseOrder: async (orderData) => {
        const { data } = await apiClient.post('/agent/supplier/orders/add', orderData);
        return data;
    },

    deletePurchaseOrder: async (orderId) => {
        const { data } = await apiClient.delete(`/agent/supplier/orders/${orderId}`);
        return data;
    }
};
