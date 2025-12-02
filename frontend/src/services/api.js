import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const statisticsAPI = {
  getAvailableGrids: async () => {
    const response = await api.get('/api/v1/statistics/grids');
    return response.data;
  },

  getGridStatistics: async (gridId) => {
    const response = await api.get(`/api/v1/statistics/grid/${gridId}`);
    return response.data;
  },

  getLeaderboard: async (gridId, limit = 100) => {
    const response = await api.get(`/api/v1/statistics/grid/${gridId}/leaderboard`, {
      params: { limit },
    });
    return response.data;
  },

  getScoreDistribution: async (gridId) => {
    const response = await api.get(`/api/v1/statistics/grid/${gridId}/distribution`);
    return response.data;
  },

  getCompletionTimeDistribution: async (gridId) => {
    const response = await api.get(`/api/v1/statistics/grid/${gridId}/completion-time-distribution`);
    return response.data;
  },

  getTemporalStatistics: async (gridId) => {
    const response = await api.get(`/api/v1/statistics/grid/${gridId}/temporal`);
    return response.data;
  },

  getGlobalStatistics: async () => {
    const response = await api.get('/api/v1/statistics/global');
    return response.data;
  },
};

export default api;
