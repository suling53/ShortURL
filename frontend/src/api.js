import axios from 'axios';

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || '/api';
const API_TOKEN = import.meta.env?.VITE_API_TOKEN || 'devtoken';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    'Authorization': API_TOKEN && API_TOKEN !== 'devtoken' ? API_TOKEN : undefined,
  },
});

// Links
export const listLinks = (page = 1) => api.get(`/links/?page=${page}`);
export const createLink = (payload) => api.post('/links/', payload);
export const deleteLink = (shortCode) => api.delete(`/links/${shortCode}/`);
export const createBatchLinks = (payload) => api.post('/links/batch/', payload);

// Analytics
export const getAnalytics = (shortCode, params = {}) => api.get(`/analytics/${shortCode}/`, { params });
export const getCodeOptions = (q = '') => api.get('/links/codes/', { params: { q } });

// Auth (session-based)
export const login = (username, password) => api.post('/auth/login', { username, password });
export const logout = () => api.post('/auth/logout');
export const me = () => api.get('/auth/me');

// Password verify (redirect flow, not session)
export const verifyPassword = (shortCode, password) => {
  return api.post(`${shortCode}/`, { password });
};
