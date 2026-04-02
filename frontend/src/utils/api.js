/**
 * utils/api.js
 * ─────────────
 * Axios API client pre-configured for the UPSC backend.
 * All API calls go through this module.
 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// ── Upload ────────────────────────────────────────────────────────────────────

export const uploadPDF = (formData, onProgress) =>
  api.post('/upload/pdf', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
  })

export const uploadNewspaper = (formData, onProgress) =>
  api.post('/upload/newspaper', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
  })

export const uploadJSON = (formData) =>
  api.post('/upload/json', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

export const getDocumentStatus = (id) => api.get(`/upload/status/${id}`)
export const listDocuments      = (params) => api.get('/upload/documents', { params })

// ── Query ─────────────────────────────────────────────────────────────────────

export const startConversation   = ()       => api.post('/query/conversation/start')
export const sendQuery           = (data)   => api.post('/query/', data)
export const writeAnswer         = (data, type) => api.post(`/query/answer?answer_type=${type}`, data)
export const getProbableQs       = (data)   => api.post('/query/probable-questions', data)
export const getCurrentAffairs   = (params) => api.get('/query/current-affairs', { params })
export const getConversation     = (id)     => api.get(`/query/conversation/${id}`)

// ── Analytics ─────────────────────────────────────────────────────────────────

export const getWeakness   = ()       => api.get('/analytics/weakness')
export const getCoverage   = ()       => api.get('/analytics/coverage')
export const getPYQTrends  = (paper)  => api.get('/analytics/pyq-trends', { params: { paper } })
export const getCASummary  = (days)   => api.get('/analytics/ca-summary', { params: { days } })

// ── Revision ──────────────────────────────────────────────────────────────────

export const getWeeklyRevision  = ()      => api.get('/revision/weekly')
export const getMonthlyRevision = ()      => api.get('/revision/monthly')
export const getTopicRevision   = (data)  => api.post('/revision/topic', data)
export const getRevisionHistory = ()      => api.get('/revision/history')

// ── Visuals ───────────────────────────────────────────────────────────────────

export const getDocumentVisuals = (id)    => api.get(`/visuals/document/${id}`)
export const getTopicVisuals    = (id)    => api.get(`/visuals/topic/${id}`)
export const getVisual          = (id)    => api.get(`/visuals/${id}`)
export const processVisual      = (id)    => api.post(`/visuals/${id}/process`)
export const visualImageUrl     = (id)    => `/visuals/${id}/image`

export default api
