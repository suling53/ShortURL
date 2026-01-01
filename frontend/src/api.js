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

// Links（后端已限制只允许登录用户删除/管理，本次任务后续可在视图层继续按 user 过滤）
export const listLinks = (page = 1) => api.get(`/links/?page=${page}`);
export const createLink = (payload) => api.post('/links/', payload);
export const deleteLink = (shortCode) => api.delete(`/links/${shortCode}/`);
export const createBatchLinks = (payload) => api.post('/links/batch/', payload);

// Analytics
export const getAnalytics = (shortCode, params = {}) => api.get(`/analytics/${shortCode}/`, { params });
export const getCodeOptions = (q = '') => api.get('/links/codes/', { params: { q } });

// Auth (session-based)，统一放在一个地方
export const register = (username, email, password, captcha_id, captcha) =>
  api.post('/auth/register', { username, email, password, captcha_id, captcha });

export const login = (username, password, captcha_id, captcha) =>
  api.post('/auth/login', { username, password, captcha_id, captcha });

export const logout = () => api.post('/auth/logout');
export const me = () => api.get('/auth/me');
export const getCaptcha = () => api.get('/auth/captcha');

// Password verify 
export const verifyPassword = (shortCode, password) => {
  return api.post(`${shortCode}/`, { password });
};
