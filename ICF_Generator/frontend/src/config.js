/**
 * Application API Configuration
 * Centralized location for backend URL and endpoints.
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

export const API_ENDPOINTS = {
  HEALTH: `${API_BASE_URL}/health`,
  STUDIES: `${API_BASE_URL}/api/studies`,
  UPLOAD: `${API_BASE_URL}/api/protocol/upload`,
  PROCESS: `${API_BASE_URL}/api/protocol/process`,
  CANONICALIZE: `${API_BASE_URL}/api/protocol/canonicalize`,
  CHUNK: `${API_BASE_URL}/api/protocol/chunk`,
  EMBED: `${API_BASE_URL}/api/protocol/embed`,
  INDEX: `${API_BASE_URL}/api/protocol/index`,
  VECTOR_STORE_STATUS: `${API_BASE_URL}/api/vector-store/status`,
  SEARCH: `${API_BASE_URL}/api/search`,
  RAG_RETRIEVE: `${API_BASE_URL}/api/rag/retrieve`,
  ANALYZE_PROTOCOL: `${API_BASE_URL}/api/protocol/analyze`,
  GENERATE_ICF: `${API_BASE_URL}/api/icf/generate`,
  VALIDATE_ICF: `${API_BASE_URL}/api/icf/validate`,
  HUMAN_REVIEW: `${API_BASE_URL}/api/icf/review`,
  EXPORT_ICF: `${API_BASE_URL}/api/icf/export`,
};
