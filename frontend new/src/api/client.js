import axios from 'axios';

// Base API client configured for the FastAPI backend
const apiClient = axios.create({
    baseURL: 'http://127.0.0.1:8000',
    headers: {
        'Content-Type': 'application/json',
    },
});

export default apiClient;
