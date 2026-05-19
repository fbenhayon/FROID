import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para adicionar token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth API
export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  
  register: (data: { email: string; password: string; name: string; crp: string; specialty: string }) =>
    api.post('/auth/register', data),
};

// Patients API
export const patientsAPI = {
  list: (professionalId: string) =>
    api.get(`/patients/professional/${professionalId}`),
  
  create: (data: { name: string; cpf: string; birthDate: string; professionalId: string }) =>
    api.post('/patients', data),
};

// Sessions API
export const sessionsAPI = {
  create: (data: { patientId: string; professionalId: string; scheduledFor: string }) =>
    api.post('/sessions', data),
  
  list: (patientId: string) =>
    api.get(`/sessions/patient/${patientId}`),
};
