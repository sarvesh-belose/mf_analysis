import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
});

// ── Ingestion ────────────────────────────────────────────────────────────
export const loadMaster = () => api.post('/ingest/load-master');
export const loadTri = () => api.post('/ingest/load-tri');
export const fetchNavs = (force = false) => api.post(`/ingest/fetch-navs?force=${force}`);
export const computeMetrics = (force = false) => api.post(`/ingest/compute-metrics?force=${force}`);
export const getIngestionStatus = () => api.get('/ingest/status');
export const getTaskStatus = (task) => api.get(`/ingest/status/${task}`);
export const stopTask = (task) => api.post(`/ingest/stop/${task}`);

// ── Funds ────────────────────────────────────────────────────────────────
export const listFunds = (params) => api.get('/funds', { params });
export const getFundFilters = () => api.get('/funds/filters');
export const getFundDetail = (id) => api.get(`/funds/${id}`);
export const getNavHistory = (id) => api.get(`/funds/${id}/nav-history`);
export const getRollingReturns = (id, params) => api.get(`/funds/${id}/rolling-returns`, { params });

// ── Metrics ──────────────────────────────────────────────────────────────
export const listMetrics = (params) => api.get('/metrics', { params });
export const getTopFunds = (params) => api.get('/metrics/top', { params });
export const compareFunds = (params) => api.get('/metrics/compare', { params });

// ── Benchmarks ───────────────────────────────────────────────────────────
export const listBenchmarks = () => api.get('/benchmarks');
export const updateBenchmark = (id, data) => api.put(`/benchmarks/${id}`, data);
export const getTriData = (id) => api.get(`/benchmarks/${id}/tri-data`);
export const getTriFiles = () => api.get('/benchmarks/tri/available-files');
export const getTriCoverage = () => api.get('/benchmarks/tri/coverage');
export const getRefreshPrompt = (exchange) => api.get('/benchmarks/tri/refresh-prompt', { params: { exchange } });
export const uploadTriCsv = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/benchmarks/tri/upload', form);
};
export const getTriFetchLog = () => api.get('/benchmarks/tri/fetch-log');

// ── Dashboard ────────────────────────────────────────────────────────────
export const getDashboardSummary = (params) => api.get('/dashboard/summary', { params });

// ── Config ───────────────────────────────────────────────────────────────
export const getConfig = () => api.get('/config');
export const updateConfig = (key, value) => api.put(`/config/${key}`, { value });

// ── Health ───────────────────────────────────────────────────────────────
export const healthCheck = () => api.get('/health');

export default api;
