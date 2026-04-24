import axios from 'axios';

// Base API client configured for the FastAPI backend
const apiClient = axios.create({
    baseURL: 'http://127.0.0.1:8000',
    timeout: 15000, // 15 second timeout — prevents infinite hangs
    headers: {
        'Content-Type': 'application/json',
    },
});

export default apiClient;
