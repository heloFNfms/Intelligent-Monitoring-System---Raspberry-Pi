/**
 * API接口封装
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// 仪表盘数据
export const getDashboard = (deviceId = 'device_001') => 
  api.get('/dashboard', { params: { device_id: deviceId } })

// 生产状态
export const getStatus = (deviceId) => 
  api.get(`/status/${deviceId}`)

export const updateStatus = (deviceId, data) => 
  api.put(`/status/${deviceId}`, data)

// 控制指令
export const sendControl = (deviceId, command, params = {}) => 
  api.post('/control', { device_id: deviceId, command, params })

// 传感器数据
export const getLatestSensor = (deviceId) => 
  api.get('/sensor/latest', { params: { device_id: deviceId } })

export const getSensorHistory = (deviceId, sensorType, hours = 24) => 
  api.get('/sensor/history', { params: { device_id: deviceId, sensor_type: sensorType, hours } })

// 报警
export const getAlerts = (resolved = null, limit = 50) => 
  api.get('/alerts', { params: { resolved, limit } })

export const resolveAlert = (alertId) => 
  api.put(`/alerts/${alertId}/resolve`)

// 检测记录
export const getDetectionHistory = (deviceId, limit = 100) => 
  api.get('/detection/history', { params: { device_id: deviceId, limit } })

export default api
