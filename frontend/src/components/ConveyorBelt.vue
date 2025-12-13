<template>
  <div class="conveyor-container">
    <!-- 传送带主体 -->
    <div class="conveyor-belt" :class="{ running: isRunning }">
      <!-- 传送带轨道 -->
      <div class="belt-track">
        <div class="belt-surface" :style="beltStyle">
          <div class="belt-pattern"></div>
        </div>
      </div>
      
      <!-- 传送带上的物品 -->
      <div class="items-layer">
        <div 
          v-for="item in items" 
          :key="item.id"
          class="conveyor-item"
          :class="item.shape"
          :style="getItemStyle(item)"
        >
          <div class="item-body" :style="{ background: item.color }">
            <span class="item-label">{{ item.id }}</span>
          </div>
        </div>
      </div>
      
      <!-- 起点标记 -->
      <div class="endpoint start">
        <div class="endpoint-icon">📥</div>
        <span>入口</span>
      </div>
      
      <!-- 终点标记 -->
      <div class="endpoint end">
        <div class="endpoint-icon">📤</div>
        <span>出口</span>
      </div>
      
      <!-- 滚轮装饰 -->
      <div class="roller roller-start" :class="{ spinning: isRunning }"></div>
      <div class="roller roller-end" :class="{ spinning: isRunning }"></div>
    </div>
    
    <!-- 状态面板 -->
    <div class="conveyor-status">
      <div class="status-item">
        <span class="status-label">状态</span>
        <span class="status-value" :class="{ active: isRunning }">
          {{ isRunning ? '运行中' : '已停止' }}
        </span>
      </div>
      <div class="status-item">
        <span class="status-label">速度</span>
        <span class="status-value">{{ speed.toFixed(1) }}x</span>
      </div>
      <div class="status-item">
        <span class="status-label">完成</span>
        <span class="status-value highlight">{{ completedCount }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">在线</span>
        <span class="status-value">{{ items.length }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  wsUrl: {
    type: String,
    default: 'ws://localhost:8001/ws/conveyor'
  }
})

const emit = defineEmits(['connected', 'disconnected', 'state-change'])

// 状态
const isRunning = ref(false)
const speed = ref(1.0)
const items = ref([])
const completedCount = ref(0)
const connected = ref(false)

// WebSocket
let ws = null
let beltOffset = ref(0)
let animationFrame = null

// 传送带动画样式
const beltStyle = computed(() => ({
  backgroundPosition: `${beltOffset.value}px 0`
}))

// 获取物品样式
const getItemStyle = (item) => ({
  left: `${item.position}%`,
  transform: `translateX(-50%)`
})

// 连接WebSocket
const connect = () => {
  try {
    ws = new WebSocket(props.wsUrl)
    
    ws.onopen = () => {
      connected.value = true
      emit('connected')
      console.log('✓ 传送带服务已连接')
    }
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      handleMessage(message)
    }
    
    ws.onclose = () => {
      connected.value = false
      emit('disconnected')
      // 尝试重连
      setTimeout(connect, 3000)
    }
    
    ws.onerror = (err) => {
      console.error('传送带连接错误:', err)
    }
  } catch (e) {
    console.error('连接失败:', e)
  }
}

// 处理消息
const handleMessage = (message) => {
  const { type, data } = message
  
  if (type === 'init' || type === 'state_update') {
    isRunning.value = data.is_running
    speed.value = data.speed
    items.value = data.items || []
    completedCount.value = data.completed_count
    emit('state-change', data)
  }
  
  if (type === 'tick') {
    items.value = data.items || []
    completedCount.value = data.completed_count
    isRunning.value = data.is_running
  }
}

// 发送命令
const sendCommand = (command, params = {}) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ command, params }))
  }
}

// 传送带动画
const animateBelt = () => {
  if (isRunning.value) {
    beltOffset.value -= speed.value * 2
    if (beltOffset.value <= -40) {
      beltOffset.value = 0
    }
  }
  animationFrame = requestAnimationFrame(animateBelt)
}

// 暴露方法给父组件
defineExpose({
  sendCommand,
  start: () => sendCommand('start'),
  stop: () => sendCommand('stop'),
  pause: () => sendCommand('pause'),
  setSpeed: (s) => sendCommand('set_speed', { speed: s }),
  setMode: (m) => sendCommand('set_mode', { mode: m }),
  addItem: () => sendCommand('add_item'),
  clearItems: () => sendCommand('clear_items'),
  toggleAuto: () => sendCommand('toggle_auto')
})

onMounted(() => {
  connect()
  animateBelt()
})

onUnmounted(() => {
  if (ws) ws.close()
  if (animationFrame) cancelAnimationFrame(animationFrame)
})
</script>


<style scoped>
.conveyor-container {
  width: 100%;
  padding: 16px;
}

/* 传送带主体 */
.conveyor-belt {
  position: relative;
  height: 120px;
  background: linear-gradient(180deg, #0d1520 0%, #111b2a 100%);
  border-radius: 8px;
  border: 1px solid rgba(58, 145, 199, 0.2);
  overflow: hidden;
}

/* 传送带轨道 */
.belt-track {
  position: absolute;
  top: 50%;
  left: 60px;
  right: 60px;
  height: 40px;
  transform: translateY(-50%);
  background: #1a2535;
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid rgba(58, 145, 199, 0.15);
}

.belt-surface {
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    90deg,
    #252f3f 0px,
    #252f3f 18px,
    #1e2836 18px,
    #1e2836 20px,
    #252f3f 20px,
    #252f3f 38px,
    #1e2836 38px,
    #1e2836 40px
  );
  transition: background-position 0.05s linear;
}

.conveyor-belt.running .belt-surface {
  animation: none; /* 使用JS控制 */
}

/* 物品层 */
.items-layer {
  position: absolute;
  top: 50%;
  left: 60px;
  right: 60px;
  height: 60px;
  transform: translateY(-50%);
  pointer-events: none;
}

/* 物品样式 */
.conveyor-item {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  transition: left 0.05s linear;
}

.item-body {
  width: 36px;
  height: 36px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 
    0 4px 12px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.conveyor-item.cylinder .item-body {
  border-radius: 50%;
}

.item-label {
  font-size: 10px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  font-family: var(--font-mono, monospace);
}

/* 端点标记 */
.endpoint {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  z-index: 10;
}

.endpoint.start {
  left: 12px;
}

.endpoint.end {
  right: 12px;
}

.endpoint-icon {
  font-size: 20px;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}

.endpoint span {
  font-size: 10px;
  color: var(--text-muted, rgba(255, 255, 255, 0.4));
  letter-spacing: 0.5px;
}

/* 滚轮 */
.roller {
  position: absolute;
  top: 50%;
  width: 24px;
  height: 50px;
  background: linear-gradient(90deg, #2a3545 0%, #3a4555 50%, #2a3545 100%);
  border-radius: 4px;
  transform: translateY(-50%);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.roller-start {
  left: 48px;
}

.roller-end {
  right: 48px;
}

.roller::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 8px;
  height: 8px;
  background: #1a2535;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  border: 2px solid #4a5565;
}

.roller.spinning::before {
  animation: spin 0.5s linear infinite;
}

@keyframes spin {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 状态面板 */
.conveyor-status {
  display: flex;
  justify-content: space-around;
  margin-top: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border: 1px solid rgba(58, 145, 199, 0.1);
}

.status-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.status-label {
  font-size: 10px;
  color: var(--text-muted, rgba(255, 255, 255, 0.4));
  text-transform: uppercase;
  letter-spacing: 1px;
}

.status-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary, rgba(255, 255, 255, 0.65));
  font-family: var(--font-mono, monospace);
}

.status-value.active {
  color: var(--success-color, #4a9d6e);
}

.status-value.highlight {
  color: var(--primary-color, #3a91c7);
}
</style>
