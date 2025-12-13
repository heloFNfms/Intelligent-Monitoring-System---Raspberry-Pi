<template>
  <div class="dashboard" :class="{ 'alarm-active': alarmActive }">
    <!-- 全屏报警遮罩 -->
    <div v-if="alarmActive" class="alarm-overlay" @click="dismissAlarm">
      <div class="alarm-siren">
        <div class="siren-light"></div>
        <div class="siren-body">
          <span class="siren-icon">🚨</span>
        </div>
      </div>
      <div class="alarm-text">
        <h2>⚠️ 危险区域入侵警报 ⚠️</h2>
        <p>检测到人员进入危险区域！</p>
        <small>点击任意位置关闭报警</small>
      </div>
    </div>

    <!-- 顶部标题栏 -->
    <header class="header">
      <h1>🏭 智能生产线监控系统</h1>
      <div class="header-info">
        <span class="connection-status" :class="{ connected: wsConnected }">
          {{ wsConnected ? '● 已连接' : '○ 未连接' }}
        </span>
        <span class="time">{{ currentTime }}</span>
      </div>
    </header>

    <main class="main-content">
      <!-- 左侧面板 -->
      <section class="left-panel">
        <!-- 生产状态卡片 -->
        <div class="card status-card">
          <h3>生产状态</h3>
          <div class="status-display">
            <div class="status-indicator" :class="productionStatus">
              {{ statusText }}
            </div>
            <div class="mode-display">
              模式: <strong>{{ modeText }}</strong>
            </div>
          </div>
          <div class="production-count">
            <span class="count-label">累计生产</span>
            <span class="count-value">{{ productionCount }}</span>
            <span class="count-unit">件</span>
          </div>
        </div>

        <!-- 控制面板 -->
        <div class="card control-card">
          <h3>远程控制</h3>
          <div class="control-buttons">
            <el-button type="success" @click="sendCommand('start')" :disabled="productionStatus === 'running'">
              ▶ 启动
            </el-button>
            <el-button type="danger" @click="sendCommand('stop')" :disabled="productionStatus === 'stopped'">
              ■ 停止
            </el-button>
            <el-button type="warning" @click="sendCommand('pause')" :disabled="productionStatus !== 'running'">
              ⏸ 暂停
            </el-button>
          </div>
          <div class="mode-switch">
            <span>切换模式:</span>
            <el-radio-group v-model="selectedMode" @change="switchMode">
              <el-radio label="product_a">产品A</el-radio>
              <el-radio label="product_b">产品B</el-radio>
            </el-radio-group>
          </div>
        </div>

        <!-- 报警列表 -->
        <div class="card alert-card">
          <h3>
            报警信息 
            <el-badge :value="activeAlerts" :hidden="activeAlerts === 0" type="danger" />
          </h3>
          <div class="alert-list">
            <div v-for="alert in alerts" :key="alert.id" 
                 class="alert-item" :class="alert.level">
              <span class="alert-time">{{ formatTime(alert.timestamp) }}</span>
              <span class="alert-message">{{ alert.message }}</span>
              <el-button v-if="!alert.resolved" size="small" @click="resolveAlertItem(alert.id)">
                处理
              </el-button>
            </div>
            <div v-if="alerts.length === 0" class="no-alerts">
              暂无报警
            </div>
          </div>
        </div>
      </section>

      <!-- 中间面板 - 图表 -->
      <section class="center-panel">
        <!-- 温度曲线 -->
        <div class="card chart-card">
          <h3>温度实时曲线</h3>
          <div ref="tempChartRef" class="chart-container"></div>
          <div class="current-value" :class="{ warning: currentTemp >= 80, danger: currentTemp >= 95 }">
            当前温度: <strong>{{ currentTemp?.toFixed(1) || '--' }}°C</strong>
          </div>
        </div>

        <!-- 压力曲线 -->
        <div class="card chart-card">
          <h3>压力实时曲线</h3>
          <div ref="pressureChartRef" class="chart-container"></div>
          <div class="current-value">
            当前压力: <strong>{{ currentPressure?.toFixed(1) || '--' }} kPa</strong>
          </div>
        </div>
      </section>

      <!-- 右侧面板 -->
      <section class="right-panel">
        <!-- 检测状态 + 视频流 -->
        <div class="card detection-card">
          <h3>
            区域检测
            <span class="video-status" :class="{ active: videoConnected }">
              {{ videoConnected ? '📹 直播中' : '📹 等待连接' }}
            </span>
          </h3>
          
          <!-- 视频流显示 -->
          <div class="video-container">
            <img v-if="videoFrame" :src="'data:image/jpeg;base64,' + videoFrame" 
                 class="video-frame" alt="实时监控" />
            <div v-else class="video-placeholder">
              <span>等待视频流...</span>
              <small>请运行 zone_detection.py</small>
            </div>
          </div>
          
          <div class="detection-status" :class="{ danger: inDangerZone }">
            <div class="person-count">
              检测人数: <strong>{{ personCount }}</strong>
            </div>
            <div class="zone-status">
              {{ inDangerZone ? '⚠️ 危险区域有人!' : '✓ 安全' }}
            </div>
          </div>
        </div>

        <!-- 统计信息 -->
        <div class="card stats-card">
          <h3>今日统计</h3>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value">{{ todayDetections }}</span>
              <span class="stat-label">检测次数</span>
            </div>
            <div class="stat-item">
              <span class="stat-value danger">{{ dangerEntries }}</span>
              <span class="stat-label">危险区入侵</span>
            </div>
            <div class="stat-item">
              <span class="stat-value warning">{{ todayAlerts }}</span>
              <span class="stat-label">报警次数</span>
            </div>
          </div>
        </div>

        <!-- LED状态指示 -->
        <div class="card led-card">
          <h3>指示灯状态</h3>
          <div class="led-grid">
            <div class="led-item">
              <div class="led-light" :class="{ on: ledStatus.alert, blink: ledStatus.alert }"></div>
              <span>报警灯</span>
            </div>
            <div class="led-item">
              <div class="led-light product-a" :class="{ on: productionMode === 'product_a' && productionStatus === 'running' }"></div>
              <span>产品A</span>
            </div>
            <div class="led-item">
              <div class="led-light product-b" :class="{ on: productionMode === 'product_b' && productionStatus === 'running' }"></div>
              <span>产品B</span>
            </div>
            <div class="led-item">
              <div class="led-light running" :class="{ on: productionStatus === 'running' }"></div>
              <span>运行中</span>
            </div>
          </div>
        </div>

        <!-- 设备信息 -->
        <div class="card device-card">
          <h3>设备信息</h3>
          <div class="device-info">
            <p>设备ID: {{ deviceId }}</p>
            <p>湿度: {{ currentHumidity?.toFixed(1) || '--' }}%</p>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getDashboard, sendControl, getAlerts, resolveAlert } from './api'
import { wsClient } from './utils/websocket'

const deviceId = ref('device_001')
const wsConnected = ref(false)
const currentTime = ref('')

// 生产状态
const productionStatus = ref('stopped')
const productionMode = ref('product_a')
const productionCount = ref(0)
const selectedMode = ref('product_a')

// 传感器数据
const currentTemp = ref(null)
const currentPressure = ref(null)
const currentHumidity = ref(null)
const tempData = ref([])
const pressureData = ref([])

// 检测数据
const personCount = ref(0)
const inDangerZone = ref(false)

// 视频流数据
const videoFrame = ref(null)
const videoConnected = ref(false)
let videoTimeout = null

// 报警数据
const alerts = ref([])
const activeAlerts = ref(0)
const todayAlerts = ref(0)

// 统计数据
const todayDetections = ref(0)
const dangerEntries = ref(0)

// LED状态
const ledStatus = ref({
  alert: false,      // 报警灯
  productA: false,   // 产品A指示灯
  productB: false,   // 产品B指示灯
  running: false     // 运行指示灯
})

// 报警器状态
const alarmActive = ref(false)
let alarmSound = null
let alarmTimeout = null

// 图表实例
const tempChartRef = ref(null)
const pressureChartRef = ref(null)
let tempChart = null
let pressureChart = null

// 计算属性
const statusText = computed(() => {
  const map = { running: '运行中', stopped: '已停止', paused: '已暂停' }
  return map[productionStatus.value] || '未知'
})

const modeText = computed(() => {
  const map = { product_a: '产品A', product_b: '产品B' }
  return map[productionMode.value] || '未知'
})

// 时间格式化
const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN')
}

// 更新时间
const updateTime = () => {
  currentTime.value = new Date().toLocaleString('zh-CN')
}

// 初始化图表
const initCharts = () => {
  // 温度图表
  tempChart = echarts.init(tempChartRef.value)
  tempChart.setOption({
    grid: { top: 10, right: 10, bottom: 30, left: 50 },
    xAxis: { type: 'category', data: [] },
    yAxis: { type: 'value', name: '°C', min: 0, max: 120 },
    series: [{
      type: 'line',
      smooth: true,
      data: [],
      areaStyle: { opacity: 0.3 },
      lineStyle: { color: '#f56c6c' },
      itemStyle: { color: '#f56c6c' }
    }],
    visualMap: {
      show: false,
      pieces: [
        { lte: 80, color: '#67c23a' },
        { gt: 80, lte: 95, color: '#e6a23c' },
        { gt: 95, color: '#f56c6c' }
      ]
    }
  })

  // 压力图表
  pressureChart = echarts.init(pressureChartRef.value)
  pressureChart.setOption({
    grid: { top: 10, right: 10, bottom: 30, left: 50 },
    xAxis: { type: 'category', data: [] },
    yAxis: { type: 'value', name: 'kPa', min: 80, max: 150 },
    series: [{
      type: 'line',
      smooth: true,
      data: [],
      areaStyle: { opacity: 0.3 },
      lineStyle: { color: '#409eff' },
      itemStyle: { color: '#409eff' }
    }]
  })
}

// 更新图表数据
const updateChart = (chart, dataArray, newValue, maxPoints = 30) => {
  const time = new Date().toLocaleTimeString('zh-CN')
  dataArray.push({ time, value: newValue })
  if (dataArray.length > maxPoints) dataArray.shift()
  
  chart.setOption({
    xAxis: { data: dataArray.map(d => d.time) },
    series: [{ data: dataArray.map(d => d.value) }]
  })
}


// 加载仪表盘数据
const loadDashboard = async () => {
  try {
    const { data } = await getDashboard(deviceId.value)
    productionStatus.value = data.production_status
    productionMode.value = data.production_mode
    selectedMode.value = data.production_mode
    productionCount.value = data.total_production
    currentTemp.value = data.current_temperature
    currentPressure.value = data.current_pressure
    activeAlerts.value = data.active_alerts
    todayAlerts.value = data.today_alerts
    todayDetections.value = data.today_detections
    dangerEntries.value = data.danger_zone_entries
  } catch (e) {
    console.error('加载仪表盘失败:', e)
  }
}

// 加载报警列表
const loadAlerts = async () => {
  try {
    const { data } = await getAlerts(false, 10)
    alerts.value = data
  } catch (e) {
    console.error('加载报警失败:', e)
  }
}

// 发送控制指令
const sendCommand = async (command) => {
  try {
    const { data } = await sendControl(deviceId.value, command)
    ElMessage.success(data.message)
    await loadDashboard()
  } catch (e) {
    ElMessage.error('指令发送失败')
  }
}

// 切换模式
const switchMode = async (mode) => {
  try {
    const { data } = await sendControl(deviceId.value, 'switch_mode', { mode })
    ElMessage.success(data.message)
    await loadDashboard()
  } catch (e) {
    ElMessage.error('切换模式失败')
  }
}

// 处理报警
const resolveAlertItem = async (alertId) => {
  try {
    await resolveAlert(alertId)
    ElMessage.success('报警已处理')
    await loadAlerts()
    await loadDashboard()
  } catch (e) {
    ElMessage.error('处理失败')
  }
}

// 触发报警器
const triggerAlarm = () => {
  alarmActive.value = true
  ledStatus.value.alert = true
  
  // 播放报警声音
  playAlarmSound()
  
  // 10秒后自动关闭
  if (alarmTimeout) clearTimeout(alarmTimeout)
  alarmTimeout = setTimeout(() => {
    dismissAlarm()
  }, 10000)
}

// 关闭报警器
const dismissAlarm = () => {
  alarmActive.value = false
  ledStatus.value.alert = false
  stopAlarmSound()
  if (alarmTimeout) {
    clearTimeout(alarmTimeout)
    alarmTimeout = null
  }
}

// 播放报警声音（使用Web Audio API生成）
const playAlarmSound = () => {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)()
    
    const playBeep = () => {
      if (!alarmActive.value) return
      
      const oscillator = audioContext.createOscillator()
      const gainNode = audioContext.createGain()
      
      oscillator.connect(gainNode)
      gainNode.connect(audioContext.destination)
      
      oscillator.frequency.value = 800  // 频率
      oscillator.type = 'square'
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3)
      
      oscillator.start(audioContext.currentTime)
      oscillator.stop(audioContext.currentTime + 0.3)
      
      // 循环播放
      setTimeout(() => {
        if (alarmActive.value) playBeep()
      }, 500)
    }
    
    playBeep()
    alarmSound = audioContext
  } catch (e) {
    console.log('无法播放报警声音:', e)
  }
}

// 停止报警声音
const stopAlarmSound = () => {
  if (alarmSound) {
    try {
      alarmSound.close()
    } catch (e) {}
    alarmSound = null
  }
}

// 设置WebSocket处理器
const setupWebSocket = async () => {
  try {
    await wsClient.connect()
    wsConnected.value = true
    
    // 传感器数据更新
    wsClient.on('sensor_update', (data) => {
      if (data.sensor_type === 'temperature') {
        currentTemp.value = data.value
        updateChart(tempChart, tempData.value, data.value)
      } else if (data.sensor_type === 'pressure') {
        currentPressure.value = data.value
        updateChart(pressureChart, pressureData.value, data.value)
      } else if (data.sensor_type === 'humidity') {
        currentHumidity.value = data.value
      }
    })
    
    // 检测数据更新
    wsClient.on('detection', (data) => {
      personCount.value = data.person_count
      const wasInDanger = inDangerZone.value
      inDangerZone.value = data.in_danger_zone
      
      // 如果刚进入危险区域，触发报警
      if (data.in_danger_zone && !wasInDanger && data.alert_triggered) {
        triggerAlarm()
        todayDetections.value++
        dangerEntries.value++
      }
    })
    
    // 报警更新
    wsClient.on('alert', (data) => {
      ElMessage({
        message: data.message,
        type: data.level === 'danger' ? 'error' : 'warning',
        duration: 5000
      })
      loadAlerts()
      activeAlerts.value++
      todayAlerts.value++
      
      // 如果是入侵报警，触发全屏报警器
      if (data.alert_type === 'intrusion') {
        triggerAlarm()
      } else {
        // 其他报警只闪烁LED
        ledStatus.value.alert = true
        setTimeout(() => {
          ledStatus.value.alert = false
        }, 5000)
      }
    })
    
    // 状态变化
    wsClient.on('status_change', (data) => {
      productionStatus.value = data.status
      productionMode.value = data.mode
      selectedMode.value = data.mode
      productionCount.value = data.production_count
      
      // 更新LED状态
      ledStatus.value.running = data.status === 'running'
      ledStatus.value.productA = data.mode === 'product_a' && data.status === 'running'
      ledStatus.value.productB = data.mode === 'product_b' && data.status === 'running'
    })
    
    // LED状态更新（来自开发板）
    wsClient.on('led_status', (data) => {
      if (data.led_type === 'alert') {
        ledStatus.value.alert = data.state
      } else if (data.led_type === 'product_a') {
        ledStatus.value.productA = data.state
      } else if (data.led_type === 'product_b') {
        ledStatus.value.productB = data.state
      } else if (data.led_type === 'running') {
        ledStatus.value.running = data.state
      }
    })
    
    // 视频帧更新
    wsClient.on('video_frame', (data) => {
      videoFrame.value = data.frame
      videoConnected.value = true
      
      // 更新检测数据
      if (data.detection) {
        personCount.value = data.detection.person_count || 0
        inDangerZone.value = data.detection.in_danger_zone || false
      }
      
      // 设置超时检测（5秒无数据则显示断开）
      if (videoTimeout) clearTimeout(videoTimeout)
      videoTimeout = setTimeout(() => {
        videoConnected.value = false
      }, 5000)
    })
    
  } catch (e) {
    console.error('WebSocket连接失败:', e)
    wsConnected.value = false
  }
}

// 生命周期
let timeInterval = null

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  
  initCharts()
  await loadDashboard()
  await loadAlerts()
  await setupWebSocket()
  
  // 窗口大小变化时重绘图表
  window.addEventListener('resize', () => {
    tempChart?.resize()
    pressureChart?.resize()
  })
})

onUnmounted(() => {
  clearInterval(timeInterval)
  if (videoTimeout) clearTimeout(videoTimeout)
  if (alarmTimeout) clearTimeout(alarmTimeout)
  stopAlarmSound()
  wsClient.close()
  tempChart?.dispose()
  pressureChart?.dispose()
})
</script>


<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.dashboard {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: #fff;
  font-family: 'Microsoft YaHei', sans-serif;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 30px;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header h1 {
  font-size: 24px;
  font-weight: 500;
}

.header-info {
  display: flex;
  gap: 20px;
  align-items: center;
}

.connection-status {
  color: #f56c6c;
  font-size: 14px;
}

.connection-status.connected {
  color: #67c23a;
}

.time {
  color: #909399;
  font-size: 14px;
}

.main-content {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  gap: 20px;
  padding: 20px;
  height: calc(100vh - 70px);
}

.card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.card h3 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 15px;
  color: #e0e0e0;
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 左侧面板 */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.status-card .status-display {
  text-align: center;
  margin-bottom: 20px;
}

.status-indicator {
  display: inline-block;
  padding: 10px 30px;
  border-radius: 20px;
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 10px;
}

.status-indicator.running {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
  border: 1px solid #67c23a;
}

.status-indicator.stopped {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
  border: 1px solid #f56c6c;
}

.status-indicator.paused {
  background: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
  border: 1px solid #e6a23c;
}

.mode-display {
  color: #909399;
}

.production-count {
  text-align: center;
  padding: 15px;
  background: rgba(64, 158, 255, 0.1);
  border-radius: 8px;
}

.count-value {
  font-size: 36px;
  font-weight: bold;
  color: #409eff;
  margin: 0 5px;
}

.count-label, .count-unit {
  color: #909399;
}

.control-buttons {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.control-buttons .el-button {
  flex: 1;
}

.mode-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #909399;
}

.alert-card {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.alert-list {
  flex: 1;
  overflow-y: auto;
  max-height: 200px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  margin-bottom: 8px;
  border-radius: 6px;
  font-size: 13px;
}

.alert-item.warning {
  background: rgba(230, 162, 60, 0.2);
  border-left: 3px solid #e6a23c;
}

.alert-item.danger {
  background: rgba(245, 108, 108, 0.2);
  border-left: 3px solid #f56c6c;
}

.alert-time {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}

.alert-message {
  flex: 1;
}

.no-alerts {
  text-align: center;
  color: #909399;
  padding: 20px;
}

/* 中间面板 */
.center-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chart-container {
  flex: 1;
  min-height: 200px;
}

.current-value {
  text-align: center;
  padding: 10px;
  font-size: 16px;
  color: #67c23a;
}

.current-value.warning {
  color: #e6a23c;
}

.current-value.danger {
  color: #f56c6c;
  animation: blink 1s infinite;
}

@keyframes blink {
  50% { opacity: 0.5; }
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 视频流样式 */
.video-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(144, 147, 153, 0.3);
  color: #909399;
}

.video-status.active {
  background: rgba(103, 194, 58, 0.3);
  color: #67c23a;
}

.video-container {
  width: 100%;
  aspect-ratio: 4/3;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-frame {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-placeholder {
  text-align: center;
  color: #606266;
}

.video-placeholder span {
  display: block;
  font-size: 14px;
  margin-bottom: 5px;
}

.video-placeholder small {
  font-size: 12px;
  color: #909399;
}

.detection-status {
  text-align: center;
  padding: 15px;
  border-radius: 8px;
  background: rgba(103, 194, 58, 0.1);
}

.detection-status.danger {
  background: rgba(245, 108, 108, 0.2);
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}

.person-count {
  font-size: 18px;
  margin-bottom: 10px;
}

.person-count strong {
  font-size: 28px;
  color: #409eff;
}

.zone-status {
  font-size: 16px;
}

.detection-status.danger .zone-status {
  color: #f56c6c;
  font-weight: bold;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.stat-item {
  text-align: center;
  padding: 15px 5px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-value.danger {
  color: #f56c6c;
}

.stat-value.warning {
  color: #e6a23c;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

/* LED指示灯样式 */
.led-card {
  flex-shrink: 0;
}

.led-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.led-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.led-item span {
  font-size: 12px;
  color: #909399;
}

.led-light {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3a3a3a;
  border: 2px solid #555;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
  transition: all 0.3s ease;
}

/* 报警灯 - 红色 */
.led-light.on {
  background: #f56c6c;
  box-shadow: 0 0 15px #f56c6c, 0 0 30px rgba(245, 108, 108, 0.5);
  border-color: #f89898;
}

/* 产品A灯 - 绿色 */
.led-light.product-a.on {
  background: #67c23a;
  box-shadow: 0 0 15px #67c23a, 0 0 30px rgba(103, 194, 58, 0.5);
  border-color: #95d475;
}

/* 产品B灯 - 蓝色 */
.led-light.product-b.on {
  background: #409eff;
  box-shadow: 0 0 15px #409eff, 0 0 30px rgba(64, 158, 255, 0.5);
  border-color: #79bbff;
}

/* 运行灯 - 黄色 */
.led-light.running.on {
  background: #e6a23c;
  box-shadow: 0 0 15px #e6a23c, 0 0 30px rgba(230, 162, 60, 0.5);
  border-color: #eebe77;
}

/* 闪烁动画 */
.led-light.blink {
  animation: led-blink 0.5s infinite;
}

@keyframes led-blink {
  0%, 100% { 
    opacity: 1;
    box-shadow: 0 0 15px #f56c6c, 0 0 30px rgba(245, 108, 108, 0.5);
  }
  50% { 
    opacity: 0.3;
    box-shadow: none;
  }
}

.device-info p {
  color: #909399;
  margin-bottom: 8px;
}

/* ==================== 报警器样式 ==================== */
.dashboard.alarm-active {
  animation: screen-flash 0.5s infinite;
}

@keyframes screen-flash {
  0%, 100% { }
  50% { box-shadow: inset 0 0 100px rgba(245, 108, 108, 0.3); }
}

.alarm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  animation: alarm-fade-in 0.3s ease;
}

@keyframes alarm-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.alarm-siren {
  position: relative;
  margin-bottom: 40px;
}

.siren-light {
  position: absolute;
  top: -20px;
  left: 50%;
  transform: translateX(-50%);
  width: 60px;
  height: 60px;
  background: #f56c6c;
  border-radius: 50%;
  animation: siren-rotate 0.5s linear infinite;
  box-shadow: 
    0 0 30px #f56c6c,
    0 0 60px #f56c6c,
    0 0 90px rgba(245, 108, 108, 0.5);
}

@keyframes siren-rotate {
  0% { 
    box-shadow: 
      -100px 0 60px rgba(245, 108, 108, 0.8),
      0 0 30px #f56c6c;
  }
  25% { 
    box-shadow: 
      0 -100px 60px rgba(245, 108, 108, 0.8),
      0 0 30px #f56c6c;
  }
  50% { 
    box-shadow: 
      100px 0 60px rgba(245, 108, 108, 0.8),
      0 0 30px #f56c6c;
  }
  75% { 
    box-shadow: 
      0 100px 60px rgba(245, 108, 108, 0.8),
      0 0 30px #f56c6c;
  }
  100% { 
    box-shadow: 
      -100px 0 60px rgba(245, 108, 108, 0.8),
      0 0 30px #f56c6c;
  }
}

.siren-body {
  width: 120px;
  height: 80px;
  background: linear-gradient(180deg, #333 0%, #1a1a1a 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 50px;
  border: 3px solid #444;
}

.siren-icon {
  font-size: 48px;
  animation: siren-shake 0.1s infinite;
}

@keyframes siren-shake {
  0%, 100% { transform: rotate(-5deg); }
  50% { transform: rotate(5deg); }
}

.alarm-text {
  text-align: center;
  animation: alarm-pulse 0.5s infinite;
}

@keyframes alarm-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.alarm-text h2 {
  font-size: 36px;
  color: #f56c6c;
  margin-bottom: 15px;
  text-shadow: 0 0 20px rgba(245, 108, 108, 0.8);
}

.alarm-text p {
  font-size: 24px;
  color: #fff;
  margin-bottom: 20px;
}

.alarm-text small {
  font-size: 14px;
  color: #909399;
}
</style>
