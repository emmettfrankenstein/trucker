import { api } from './client'

export const geocode = (q, signal) => api.get('/geocode/', { params: { q }, signal }).then((r) => r.data)
export const planTrip = (body) => api.post('/trips/', body).then((r) => r.data)
export const getTrip = (id) => api.get(`/trips/${id}/`).then((r) => r.data)
export const getHeatmap = (id) => api.get(`/trips/${id}/heatmap/`).then((r) => r.data)
export const listTrips = () => api.get('/trips/').then((r) => r.data)
export const deleteTrip = (id) => api.delete(`/trips/${id}/`)

export const login = (body) => api.post('/auth/token/', body).then((r) => r.data)
export const register = (body) => api.post('/auth/register/', body).then((r) => r.data)
export const logout = (refresh) => api.post('/auth/logout/', { refresh })
export const me = () => api.get('/auth/me/').then((r) => r.data)
