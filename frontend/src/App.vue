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

      <!-- 中间面板 - 传送带 + 图表 -->
      <section class="center-panel">
        <!-- 传送带可视化 -->
        <div class="card conveyor-card">
          <h3>
            生产线传送带
            <span class="conveyor-status-badge" :class="{ active: conveyorConnected }">
              {{ conveyorConnected ? '● 在线' : '○ 离线' }}
            </span>
          </h3>
          <ConveyorBelt 
            ref="conveyorRef"
            @connected="conveyorConnected = true"
            @disconnected="conveyorConnected = false"
            @state-change="onConveyorStateChange"
          />
        </div>

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
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getDashboard, sendControl, getAlerts, resolveAlert } from './api'
import { wsClient } from './utils/websocket'
import ConveyorBelt from './components/ConveyorBelt.vue'

const deviceId = ref('device_001')

// 传送带相关
const conveyorRef = ref(null)
const conveyorConnected = ref(false)

// 传送带状态变化处理
const onConveyorStateChange = (state) => {
  // 同步传送带完成数量到生产计数
  if (state.completed_count !== undefined) {
    // 可以选择是否同步到主系统
  }
}
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

// 科技风图表主题配置
const chartTheme = {
  backgroundColor: 'transparent',
  textStyle: { color: 'rgba(255, 255, 255, 0.65)' },
  axisLine: { lineStyle: { color: 'rgba(58, 145, 199, 0.3)' } },
  splitLine: { lineStyle: { color: 'rgba(58, 145, 199, 0.15)', type: 'dashed' } },
  axisTick: { lineStyle: { color: 'rgba(58, 145, 199, 0.3)' } }
}

// 初始化图表
const initCharts = () => {
  // 温度图表
  tempChart = echarts.init(tempChartRef.value)
  tempChart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 20, right: 15, bottom: 30, left: 55 },
    xAxis: { 
      type: 'category', 
      data: [],
      axisLine: chartTheme.axisLine,
      axisTick: chartTheme.axisTick,
      axisLabel: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 10 }
    },
    yAxis: { 
      type: 'value', 
      name: '°C', 
      min: 0, 
      max: 120,
      nameTextStyle: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 11 },
      axisLine: chartTheme.axisLine,
      splitLine: chartTheme.splitLine,
      axisLabel: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 10 }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      data: [],
      areaStyle: { 
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.35)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      },
      lineStyle: { color: '#409eff', width: 2 },
      itemStyle: { color: '#409eff', borderColor: '#0d2b45', borderWidth: 2 }
    }],
    visualMap: {
      show: false,
      pieces: [
        { lte: 80, color: '#3a91c7' },
        { gt: 80, lte: 95, color: '#d4915e' },
        { gt: 95, color: '#c75050' }
      ]
    },
    animation: true,
    animationDuration: 180,
    animationEasing: 'linear'
  })

  // 压力图表
  pressureChart = echarts.init(pressureChartRef.value)
  pressureChart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 20, right: 15, bottom: 30, left: 55 },
    xAxis: { 
      type: 'category', 
      data: [],
      axisLine: chartTheme.axisLine,
      axisTick: chartTheme.axisTick,
      axisLabel: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 10 }
    },
    yAxis: { 
      type: 'value', 
      name: 'kPa', 
      min: 80, 
      max: 150,
      nameTextStyle: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 11 },
      axisLine: chartTheme.axisLine,
      splitLine: chartTheme.splitLine,
      axisLabel: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 10 }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      data: [],
      areaStyle: { 
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(45, 183, 181, 0.35)' },
          { offset: 1, color: 'rgba(45, 183, 181, 0.05)' }
        ])
      },
      lineStyle: { color: '#2db7b5', width: 2 },
      itemStyle: { color: '#2db7b5', borderColor: '#0d2b45', borderWidth: 2 }
    }],
    animation: true,
    animationDuration: 180,
    animationEasing: 'linear'
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

// 监听生产状态变化，同步到传送带
watch(productionStatus, (newStatus) => {
  if (conveyorRef.value) {
    if (newStatus === 'running') {
      conveyorRef.value.start()
    } else if (newStatus === 'stopped') {
      conveyorRef.value.stop()
    } else if (newStatus === 'paused') {
      conveyorRef.value.pause()
    }
  }
})

// 监听模式变化，同步到传送带
watch(selectedMode, (newMode) => {
  if (conveyorRef.value) {
    conveyorRef.value.setMode(newMode)
  }
})

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
/* ========================================
   科技风工业监控系统 - 视觉规范
   风格: 深色科技 / 工业感 / 官方权威 / 克制高级
   ======================================== */

/* CSS 变量定义 */
:root {
  /* 主色系 - 科技蓝 */
  --primary-color: #3a91c7;
  --primary-light: #5ba8d9;
  --primary-dark: #2a7ab0;
  
  /* 辅色 - 青色 */
  --accent-color: #2db7b5;
  --accent-light: #4dcfcd;
  
  /* 警示色 */
  --warning-color: #d4915e;
  --danger-color: #c75050;
  --success-color: #4a9d6e;
  
  /* 背景色系 - 深色层次 */
  --bg-primary: #0a0f1a;
  --bg-secondary: #0d1520;
  --bg-tertiary: #111b2a;
  --bg-card: rgba(15, 25, 40, 0.75);
  
  /* 边框与分割线 */
  --border-color: rgba(58, 145, 199, 0.2);
  --border-glow: rgba(58, 145, 199, 0.4);
  
  /* 文字色 */
  --text-primary: rgba(255, 255, 255, 0.92);
  --text-secondary: rgba(255, 255, 255, 0.65);
  --text-muted: rgba(255, 255, 255, 0.4);
  
  /* 毛玻璃效果 */
  --glass-blur: 12px;
  --glass-bg: rgba(12, 20, 35, 0.7);
  
  /* 等宽字体 - 仪表盘数字 */
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Consolas', 'Monaco', monospace;
  
  /* 动效时长 */
  --transition-fast: 150ms;
  --transition-normal: 200ms;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* 全局字体引入 */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* ========================================
   主容器
   ======================================== */
.dashboard {
  min-height: 100vh;
  background: 
    radial-gradient(ellipse at 20% 0%, rgba(58, 145, 199, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 100%, rgba(45, 183, 181, 0.06) 0%, transparent 50%),
    linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 50%, var(--bg-tertiary) 100%);
  color: var(--text-primary);
  font-family: 'Microsoft YaHei', 'PingFang SC', -apple-system, sans-serif;
  position: relative;
}

/* 微妙的网格背景 */
.dashboard::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(rgba(58, 145, 199, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(58, 145, 199, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
  pointer-events: none;
  z-index: 0;
}

/* ========================================
   顶部标题栏
   ======================================== */
.header {
  position: relative;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border-bottom: 1px solid var(--border-color);
}

.header h1 {
  font-size: 22px;
  font-weight: 500;
  letter-spacing: 1px;
  color: var(--text-primary);
}

.header-info {
  display: flex;
  gap: 24px;
  align-items: center;
}

.connection-status {
  font-size: 13px;
  color: var(--danger-color);
  font-family: var(--font-mono);
  letter-spacing: 0.5px;
}

.connection-status.connected {
  color: var(--success-color);
}

.time {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  letter-spacing: 0.5px;
}

/* ========================================
   主内容区域
   ======================================== */
.main-content {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  gap: 20px;
  padding: 20px;
  height: calc(100vh - 70px);
}

/* ========================================
   卡片组件 - 毛玻璃效果
   ======================================== */
.card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border-radius: 8px;
  padding: 20px;
  border: 1px solid var(--border-color);
  box-shadow: 
    0 4px 24px rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transition: border-color var(--transition-normal) ease;
}

.card:hover {
  border-color: var(--border-glow);
}

.card h3 {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 16px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1.5px;
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ========================================
   左侧面板
   ======================================== */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 生产状态卡片 */
.status-card .status-display {
  text-align: center;
  margin-bottom: 20px;
}

.status-indicator {
  display: inline-block;
  padding: 10px 28px;
  border-radius: 4px;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  letter-spacing: 2px;
  font-family: var(--font-mono);
}

.status-indicator.running {
  background: rgba(74, 157, 110, 0.15);
  color: var(--success-color);
  border: 1px solid rgba(74, 157, 110, 0.4);
  box-shadow: 0 0 20px rgba(74, 157, 110, 0.1);
}

.status-indicator.stopped {
  background: rgba(199, 80, 80, 0.15);
  color: var(--danger-color);
  border: 1px solid rgba(199, 80, 80, 0.4);
}

.status-indicator.paused {
  background: rgba(212, 145, 94, 0.15);
  color: var(--warning-color);
  border: 1px solid rgba(212, 145, 94, 0.4);
}

.mode-display {
  color: var(--text-secondary);
  font-size: 13px;
}

.mode-display strong {
  color: var(--accent-color);
}

.production-count {
  text-align: center;
  padding: 18px;
  background: rgba(58, 145, 199, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(58, 145, 199, 0.15);
}

.count-value {
  font-size: 42px;
  font-weight: 600;
  color: var(--primary-color);
  margin: 0 6px;
  font-family: var(--font-mono);
  letter-spacing: -1px;
}

.count-label, .count-unit {
  color: var(--text-muted);
  font-size: 13px;
}

/* 控制面板 */
.control-buttons {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.control-buttons .el-button {
  flex: 1;
  font-weight: 500;
  letter-spacing: 1px;
}

.mode-switch {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* 报警列表 */
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

.alert-list::-webkit-scrollbar {
  width: 4px;
}

.alert-list::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
}

.alert-list::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 2px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  font-size: 12px;
  transition: background var(--transition-fast) ease;
}

.alert-item.warning {
  background: rgba(212, 145, 94, 0.1);
  border-left: 2px solid var(--warning-color);
}

.alert-item.danger {
  background: rgba(199, 80, 80, 0.1);
  border-left: 2px solid var(--danger-color);
}

.alert-time {
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-mono);
  white-space: nowrap;
}

.alert-message {
  flex: 1;
  color: var(--text-secondary);
}

.no-alerts {
  text-align: center;
  color: var(--text-muted);
  padding: 24px;
  font-size: 13px;
}

/* ========================================
   中间面板 - 传送带 + 图表
   ======================================== */
.center-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 传送带卡片 */
.conveyor-card {
  flex-shrink: 0;
}

.conveyor-card h3 {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conveyor-status-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-muted);
  font-family: var(--font-mono);
  text-transform: none;
  letter-spacing: 0;
}

.conveyor-status-badge.active {
  background: rgba(74, 157, 110, 0.15);
  color: var(--success-color);
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
  padding: 12px;
  font-size: 14px;
  color: var(--success-color);
  font-family: var(--font-mono);
  border-top: 1px solid var(--border-color);
  margin-top: 12px;
}

.current-value strong {
  font-size: 18px;
  font-weight: 600;
}

.current-value.warning {
  color: var(--warning-color);
}

.current-value.danger {
  color: var(--danger-color);
  animation: value-pulse 1.5s ease-in-out infinite;
}

@keyframes value-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ========================================
   右侧面板
   ======================================== */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 视频流状态 */
.video-status {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.video-status.active {
  background: rgba(74, 157, 110, 0.15);
  color: var(--success-color);
}

.video-container {
  width: 100%;
  aspect-ratio: 4/3;
  background: var(--bg-primary);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-color);
}

.video-frame {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-placeholder {
  text-align: center;
  color: var(--text-muted);
}

.video-placeholder span {
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
}

.video-placeholder small {
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.7;
}

/* 检测状态 */
.detection-status {
  text-align: center;
  padding: 16px;
  border-radius: 6px;
  background: rgba(74, 157, 110, 0.08);
  border: 1px solid rgba(74, 157, 110, 0.2);
  transition: all var(--transition-normal) ease;
}

.detection-status.danger {
  background: rgba(199, 80, 80, 0.12);
  border-color: rgba(199, 80, 80, 0.3);
  animation: danger-glow 1.5s ease-in-out infinite;
}

@keyframes danger-glow {
  0%, 100% { box-shadow: 0 0 0 rgba(199, 80, 80, 0); }
  50% { box-shadow: 0 0 20px rgba(199, 80, 80, 0.2); }
}

.person-count {
  font-size: 14px;
  margin-bottom: 8px;
  color: var(--text-secondary);
}

.person-count strong {
  font-size: 28px;
  color: var(--primary-color);
  font-family: var(--font-mono);
  font-weight: 600;
}

.zone-status {
  font-size: 14px;
  color: var(--success-color);
}

.detection-status.danger .zone-status {
  color: var(--danger-color);
  font-weight: 600;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
  padding: 16px 8px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border: 1px solid var(--border-color);
  transition: border-color var(--transition-fast) ease;
}

.stat-item:hover {
  border-color: var(--border-glow);
}

.stat-value {
  display: block;
  font-size: 26px;
  font-weight: 600;
  color: var(--primary-color);
  font-family: var(--font-mono);
  margin-bottom: 4px;
}

.stat-value.danger {
  color: var(--danger-color);
}

.stat-value.warning {
  color: var(--warning-color);
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}

/* ========================================
   LED 指示灯
   ======================================== */
.led-card {
  flex-shrink: 0;
}

.led-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.led-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.led-item span {
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}

.led-light {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  transition: all var(--transition-normal) ease;
}

/* 报警灯 - 红色 */
.led-light.on {
  background: var(--danger-color);
  box-shadow: 0 0 12px var(--danger-color), 0 0 24px rgba(199, 80, 80, 0.4);
  border-color: rgba(199, 80, 80, 0.8);
}

/* 产品A灯 - 绿色 */
.led-light.product-a.on {
  background: var(--success-color);
  box-shadow: 0 0 12px var(--success-color), 0 0 24px rgba(74, 157, 110, 0.4);
  border-color: rgba(74, 157, 110, 0.8);
}

/* 产品B灯 - 蓝色 */
.led-light.product-b.on {
  background: var(--primary-color);
  box-shadow: 0 0 12px var(--primary-color), 0 0 24px rgba(58, 145, 199, 0.4);
  border-color: rgba(58, 145, 199, 0.8);
}

/* 运行灯 - 琥珀色 */
.led-light.running.on {
  background: var(--warning-color);
  box-shadow: 0 0 12px var(--warning-color), 0 0 24px rgba(212, 145, 94, 0.4);
  border-color: rgba(212, 145, 94, 0.8);
}

/* 闪烁动画 */
.led-light.blink {
  animation: led-blink 0.6s ease-in-out infinite;
}

@keyframes led-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* 设备信息 */
.device-info p {
  color: var(--text-secondary);
  margin-bottom: 10px;
  font-size: 13px;
  font-family: var(--font-mono);
}

/* ========================================
   报警器遮罩
   ======================================== */
.dashboard.alarm-active {
  animation: screen-alert 0.8s ease-in-out infinite;
}

@keyframes screen-alert {
  0%, 100% { }
  50% { box-shadow: inset 0 0 80px rgba(199, 80, 80, 0.15); }
}

.alarm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 15, 26, 0.92);
  backdrop-filter: blur(8px);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  animation: alarm-fade-in 0.2s ease;
}

@keyframes alarm-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.alarm-siren {
  position: relative;
  margin-bottom: 48px;
}

.siren-light {
  position: absolute;
  top: -24px;
  left: 50%;
  transform: translateX(-50%);
  width: 48px;
  height: 48px;
  background: var(--danger-color);
  border-radius: 50%;
  animation: siren-pulse 0.8s ease-in-out infinite;
}

@keyframes siren-pulse {
  0%, 100% { 
    box-shadow: 0 0 30px var(--danger-color), 0 0 60px rgba(199, 80, 80, 0.5);
    transform: translateX(-50%) scale(1);
  }
  50% { 
    box-shadow: 0 0 50px var(--danger-color), 0 0 100px rgba(199, 80, 80, 0.6);
    transform: translateX(-50%) scale(1.1);
  }
}

.siren-body {
  width: 100px;
  height: 70px;
  background: linear-gradient(180deg, #1a1f2e 0%, #0d1118 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 40px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.siren-icon {
  font-size: 36px;
}

.alarm-text {
  text-align: center;
}

.alarm-text h2 {
  font-size: 28px;
  color: var(--danger-color);
  margin-bottom: 16px;
  font-weight: 600;
  letter-spacing: 2px;
}

.alarm-text p {
  font-size: 18px;
  color: var(--text-primary);
  margin-bottom: 24px;
}

.alarm-text small {
  font-size: 13px;
  color: var(--text-muted);
}

/* ========================================
   Element Plus 组件覆盖样式
   ======================================== */

/* 按钮样式 */
.el-button {
  --el-button-bg-color: rgba(58, 145, 199, 0.15);
  --el-button-border-color: rgba(58, 145, 199, 0.3);
  --el-button-text-color: var(--primary-color);
  --el-button-hover-bg-color: rgba(58, 145, 199, 0.25);
  --el-button-hover-border-color: rgba(58, 145, 199, 0.5);
  font-weight: 500;
  transition: all var(--transition-fast) ease;
}

.el-button--success {
  --el-button-bg-color: rgba(74, 157, 110, 0.15);
  --el-button-border-color: rgba(74, 157, 110, 0.3);
  --el-button-text-color: var(--success-color);
  --el-button-hover-bg-color: rgba(74, 157, 110, 0.25);
  --el-button-hover-border-color: rgba(74, 157, 110, 0.5);
}

.el-button--danger {
  --el-button-bg-color: rgba(199, 80, 80, 0.15);
  --el-button-border-color: rgba(199, 80, 80, 0.3);
  --el-button-text-color: var(--danger-color);
  --el-button-hover-bg-color: rgba(199, 80, 80, 0.25);
  --el-button-hover-border-color: rgba(199, 80, 80, 0.5);
}

.el-button--warning {
  --el-button-bg-color: rgba(212, 145, 94, 0.15);
  --el-button-border-color: rgba(212, 145, 94, 0.3);
  --el-button-text-color: var(--warning-color);
  --el-button-hover-bg-color: rgba(212, 145, 94, 0.25);
  --el-button-hover-border-color: rgba(212, 145, 94, 0.5);
}

.el-button.is-disabled {
  opacity: 0.4;
}

/* Radio 样式 */
.el-radio {
  --el-radio-text-color: var(--text-secondary);
  --el-radio-input-border-color: var(--border-color);
}

.el-radio__input.is-checked .el-radio__inner {
  background: var(--primary-color);
  border-color: var(--primary-color);
}

.el-radio__input.is-checked + .el-radio__label {
  color: var(--primary-color);
}

/* Badge 样式 */
.el-badge__content {
  background-color: var(--danger-color);
  border: none;
}

/* Message 样式 */
.el-message {
  --el-message-bg-color: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--border-color);
}
</style>
