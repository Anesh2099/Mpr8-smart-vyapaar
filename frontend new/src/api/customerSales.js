import axios from 'axios';

const API_URL = 'http://localhost:5001/api/customer_sales';

export const getCustomerSales = async () => {
    const response = await axios.get(API_URL);
    return response.data;
};

export const addCustomerSale = async (saleData) => {
    const response = await axios.post(API_URL, saleData);
    return response.data;
};

export const updateCustomerSale = async (id, updateData) => {
    const response = await axios.put(`${API_URL}/${id}`, updateData);
    return response.data;
};

export const deleteCustomerSale = async (id) => {
    const response = await axios.delete(`${API_URL}/${id}`);
    return response.data;
};