import axios from 'axios';

const API_URL = 'http://localhost:5001/api/orders';

export const getOrders = async () => {
    const response = await axios.get(API_URL);
    return response.data;
};

export const addOrder = async (orderData) => {
    const response = await axios.post(API_URL, orderData);
    return response.data;
};

export const updateOrder = async (id, updateData) => {
    const response = await axios.put(`${API_URL}/${id}`, updateData);
    return response.data;
};

export const deleteOrder = async (id) => {
    const response = await axios.delete(`${API_URL}/${id}`);
    return response.data;
};