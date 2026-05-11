import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('froid_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
};

export const sessionAPI = {
  create: (data: any) => api.post('/sessions', data),
  start: (sessionId: string) => api.patch(`/sessions/${sessionId}/start`),
  end: (sessionId: string, notes?: string) => api.patch(`/sessions/${sessionId}/end`, { notes }),
  analyzeVoice: (sessionId: string, audioData: any) => api.post(`/sessions/${sessionId}/analyze-voice`, { audioData }),
  analyzeFace: (sessionId: string, imageData: any) => api.post(`/sessions/${sessionId}/analyze-face`, { imageData }),
  getResults: (sessionId: string) => api.get(`/sessions/${sessionId}/results`),
};

export default api;
