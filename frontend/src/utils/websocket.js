/**
 * WebSocket连接管理
 */
export class WebSocketClient {
  constructor(url) {
    this.url = url
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 10
    this.reconnectDelay = 3000
    this.handlers = {}
  }

  connect() {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url)
        
        this.ws.onopen = () => {
          console.log('✓ WebSocket已连接')
          this.reconnectAttempts = 0
          resolve()
        }
        
        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            this.handleMessage(message)
          } catch (e) {
            console.error('消息解析失败:', e)
          }
        }
        
        this.ws.onclose = () => {
          console.log('WebSocket已断开')
          this.tryReconnect()
        }
        
        this.ws.onerror = (error) => {
          console.error('WebSocket错误:', error)
          reject(error)
        }
      } catch (e) {
        reject(e)
      }
    })
  }

  tryReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
      setTimeout(() => this.connect(), this.reconnectDelay)
    }
  }

  handleMessage(message) {
    const { type, data, timestamp } = message
    if (this.handlers[type]) {
      this.handlers[type].forEach(handler => handler(data, timestamp))
    }
    // 触发通用处理器
    if (this.handlers['*']) {
      this.handlers['*'].forEach(handler => handler(message))
    }
  }

  on(type, handler) {
    if (!this.handlers[type]) {
      this.handlers[type] = []
    }
    this.handlers[type].push(handler)
  }

  off(type, handler) {
    if (this.handlers[type]) {
      this.handlers[type] = this.handlers[type].filter(h => h !== handler)
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  sendControl(deviceId, command, params = {}) {
    this.send({
      type: 'control',
      data: { device_id: deviceId, command, params }
    })
  }

  close() {
    if (this.ws) {
      this.ws.close()
    }
  }
}

// 创建全局WebSocket实例
const wsUrl = `ws://${window.location.hostname}:8000/ws/dashboard`
export const wsClient = new WebSocketClient(wsUrl)
