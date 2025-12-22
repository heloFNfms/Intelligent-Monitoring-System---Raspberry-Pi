<template>
  <div class="dashboard" :class="{ 'alarm-active': alarmActive }">
    <!-- 超炫酷背景特效层 -->
    <div class="bg-effects">
      <!-- 深空星云背景 -->
      <div class="nebula-bg"></div>
      
      <!-- 粒子系统 - 分层视差 -->
      <div class="particles-container">
        <!-- 远景星空 -->
        <div class="particle star-sm" v-for="n in 100" :key="'sm'+n" :style="getStarStyle(n, 'sm')"></div>
        <!-- 中景粒子 -->
        <div class="particle star-md" v-for="n in 50" :key="'md'+n" :style="getStarStyle(n, 'md')"></div>
        <!-- 近景浮尘 -->
        <div class="particle star-lg" v-for="n in 20" :key="'lg'+n" :style="getStarStyle(n, 'lg')"></div>
      </div>
      
      <!-- 能量流动线条 -->
      <div class="energy-lines">
        <div class="energy-line line-1"></div>
        <div class="energy-line line-2"></div>
        <div class="energy-line line-3"></div>
        <div class="energy-line line-4"></div>
      </div>
      
      <!-- 光斑效果 -->
      <div class="light-orbs">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
        <div class="orb orb-3"></div>
      </div>
      
      <!-- 扫描线 -->
      <div class="scan-line-bg"></div>
      
      <!-- 数据流背景 -->
      <div class="data-stream">
        <div class="stream-line" v-for="n in 5" :key="'s'+n" :style="getStreamStyle(n)"></div>
      </div>
      
      <!-- 六边形网格 -->
      <div class="hex-grid"></div>
      
      <!-- 🔥 蓝色幽冥火特效 -->
      <div class="ghost-fire-container">
        <!-- 火焰底层光晕 -->
        <div class="fire-glow"></div>
        <!-- 多个火焰 -->
        <div class="ghost-flame flame-1"></div>
        <div class="ghost-flame flame-2"></div>
        <div class="ghost-flame flame-3"></div>
        <div class="ghost-flame flame-4"></div>
        <div class="ghost-flame flame-5"></div>
        <div class="ghost-flame flame-6"></div>
        <div class="ghost-flame flame-7"></div>
        <div class="ghost-flame flame-8"></div>
        <!-- 火焰火花 - 增加数量以增强粒子感 -->
        <div class="fire-spark" v-for="n in 40" :key="'spark'+n" :style="getFireSparkStyle(n)"></div>
      </div>
    </div>
    
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
      <!-- 左侧面板 - 核心控制 -->
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
          <div class="speed-control">
            <span>传送带速度:</span>
            <el-slider v-model="conveyorSpeed" :min="0.5" :max="2" :step="0.1" 
                       :format-tooltip="(val) => val + 'x'" @change="setConveyorSpeed" />
          </div>
        </div>

        <!-- 生产计划 -->
        <div class="card plan-card">
          <h3>
            生产计划
            <el-tag v-if="planProgress.has_plan" size="small" type="success">进行中</el-tag>
          </h3>
          <div class="plan-content">
            <div class="plan-input">
              <span>目标产量:</span>
              <el-input-number v-model="targetCount" :min="0" :max="9999" size="small" />
              <el-button type="primary" size="small" @click="setPlan" :disabled="targetCount <= 0">
                设置
              </el-button>
              <el-button size="small" @click="clearPlan" v-if="planProgress.has_plan">
                清除
              </el-button>
            </div>
            <div v-if="planProgress.has_plan" class="plan-progress">
              <div class="progress-info">
                <span>进度: {{ planProgress.current }} / {{ planProgress.target }}</span>
                <span>{{ planProgress.progress }}%</span>
              </div>
              <el-progress :percentage="planProgress.progress" :stroke-width="8" 
                          :color="planProgress.progress >= 100 ? '#4a9d6e' : '#3a91c7'" />
              <div class="progress-detail">
                <span>剩余: {{ planProgress.remaining }} 件</span>
                <span v-if="planProgress.estimated_time">预计完成: {{ planProgress.estimated_time }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 自动调度 -->
        <div class="card schedule-card">
          <h3>
            自动调度
            <el-switch v-model="autoScheduleEnabled" size="small" @change="toggleAutoSchedule" />
          </h3>
          <div class="schedule-rules">
            <div class="rule-item" :class="{ disabled: !scheduleRules.tempPause }">
              <el-checkbox v-model="scheduleRules.tempPause" @change="updateScheduleRule('temp_danger_pause', $event)">
                🌡️ 温度超限自动停止 (>{{ thresholds.tempMax }}°C)
              </el-checkbox>
            </div>
            <div class="rule-item" :class="{ disabled: !scheduleRules.humidityPause }">
              <el-checkbox v-model="scheduleRules.humidityPause" @change="updateScheduleRule('humidity_danger_pause', $event)">
                💧 湿度超限自动停止 (>{{ thresholds.humidityMax }}%)
              </el-checkbox>
            </div>
            <div class="rule-item" :class="{ disabled: !scheduleRules.pressurePause }">
              <el-checkbox v-model="scheduleRules.pressurePause" @change="updateScheduleRule('pressure_danger_pause', $event)">
                📊 压力超限自动停止 (>{{ thresholds.pressureMax }}kPa)
              </el-checkbox>
            </div>
            <div class="rule-item" :class="{ disabled: !scheduleRules.productionStop }">
              <el-checkbox v-model="scheduleRules.productionStop" @change="updateScheduleRule('production_complete', $event)">
                🎯 产量达标自动停止
              </el-checkbox>
            </div>
            <div class="rule-item" :class="{ disabled: !scheduleRules.allNormalStart }">
              <el-checkbox v-model="scheduleRules.allNormalStart" @change="updateScheduleRule('all_normal_start', $event)">
                ✅ 全部正常自动启动
              </el-checkbox>
            </div>
          </div>
          <div v-if="lastScheduleAction" class="schedule-log">
            <span class="log-icon">⚡</span>
            <span class="log-text">{{ lastScheduleAction }}</span>
          </div>
        </div>

        <!-- 环境阈值配置 -->
        <div class="card threshold-card">
          <h3>
            环境阈值配置
            <el-button size="small" type="primary" @click="saveThresholds" :loading="savingThresholds">
              保存
            </el-button>
          </h3>
          <div class="threshold-settings">
            <div class="threshold-item">
              <span class="threshold-label">🌡️ 温度范围 (°C)</span>
              <div class="threshold-inputs">
                <el-input-number v-model="thresholds.tempMin" :min="-20" :max="50" size="small" />
                <span class="threshold-separator">~</span>
                <el-input-number v-model="thresholds.tempMax" :min="20" :max="100" size="small" />
              </div>
            </div>
            <div class="threshold-item">
              <span class="threshold-label">💧 湿度范围 (%)</span>
              <div class="threshold-inputs">
                <el-input-number v-model="thresholds.humidityMin" :min="0" :max="50" size="small" />
                <span class="threshold-separator">~</span>
                <el-input-number v-model="thresholds.humidityMax" :min="50" :max="100" size="small" />
              </div>
            </div>
            <div class="threshold-item">
              <span class="threshold-label">📊 压力范围 (kPa)</span>
              <div class="threshold-inputs">
                <el-input-number v-model="thresholds.pressureMin" :min="80" :max="100" size="small" />
                <span class="threshold-separator">~</span>
                <el-input-number v-model="thresholds.pressureMax" :min="100" :max="120" size="small" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 中间面板 - 传送带 + 图表 + 历史数据 -->
      <section class="center-panel">
        <!-- 传送带可视化 -->
        <div class="card conveyor-card">
          <h3>
            生产线传送带
            <span class="conveyor-status-badge" :class="{ active: wsConnected }">
              {{ wsConnected ? '● 在线' : '○ 离线' }}
            </span>
          </h3>
          <ConveyorBelt ref="conveyorRef" />
        </div>

        <!-- 图表区域 - 实时曲线和历史数据并排 -->
        <div class="charts-row">
          <!-- 环境监测曲线（温度/湿度/压力可切换） -->
          <div class="card chart-card">
            <h3>
              {{ chartTypeLabels[chartType] }}
              <div class="chart-switch">
                <el-button-group size="small">
                  <el-button :type="chartType === 'temperature' ? 'primary' : 'default'" 
                             @click="switchChartType('temperature')">🌡️ 温度</el-button>
                  <el-button :type="chartType === 'humidity' ? 'primary' : 'default'" 
                             @click="switchChartType('humidity')">💧 湿度</el-button>
                  <el-button :type="chartType === 'pressure' ? 'primary' : 'default'" 
                             @click="switchChartType('pressure')">📊 压力</el-button>
                </el-button-group>
              </div>
            </h3>
            <div ref="mainChartRef" class="chart-container"></div>
            <div class="current-value" :class="currentValueClass">
              {{ currentValueLabel }}: <strong>{{ currentValueDisplay }}</strong>
            </div>
          </div>

          <!-- 历史数据查询 -->
          <div class="card history-card">
            <h3>
              历史数据
              <el-select v-model="historyType" size="small" style="width: 90px; margin-left: 10px;">
                <el-option label="温度" value="temperature" />
                <el-option label="湿度" value="humidity" />
                <el-option label="压力" value="pressure" />
              </el-select>
            </h3>
            <div class="history-range">
              <el-radio-group v-model="historyRange" size="small" @change="loadHistoryData">
                <el-radio-button label="1h">1小时</el-radio-button>
                <el-radio-button label="6h">6小时</el-radio-button>
                <el-radio-button label="24h">24小时</el-radio-button>
              </el-radio-group>
            </div>
            <div ref="historyChartRef" class="history-chart-container"></div>
          </div>
        </div>
      </section>

      <!-- 右侧面板 -->
      <section class="right-panel">
        <!-- 检测状态 + 视频流 -->
        <div class="card detection-card">
          <h3>
            {{ detectionMode === 'zone' ? '区域检测' : '产品检测' }}
            <span class="video-status" :class="{ active: videoConnected }">
              {{ videoConnected ? '📹 直播中' : '📹 等待连接' }}
            </span>
          </h3>
          
          <!-- 检测模式切换 -->
          <div class="detection-mode-switch">
            <el-radio-group v-model="detectionMode" size="small" @change="switchDetectionMode">
              <el-radio-button label="zone">安全检测</el-radio-button>
              <el-radio-button label="product">产品检测</el-radio-button>
            </el-radio-group>
          </div>
          
          <!-- 视频流显示 -->
          <div class="video-container">
            <img v-if="videoFrame" :src="'data:image/jpeg;base64,' + videoFrame" 
                 class="video-frame" alt="实时监控" />
            <div v-else class="video-placeholder">
              <span>等待视频流...</span>
              <small>请运行 unified_detection.py</small>
            </div>
          </div>
          
          <!-- 区域检测状态 -->
          <div v-if="detectionMode === 'zone'" class="detection-status" :class="{ danger: inDangerZone }">
            <div class="person-count">
              检测人数: <strong>{{ personCount }}</strong>
            </div>
            <div class="zone-status">
              {{ inDangerZone ? '⚠️ 危险区域有人!' : '✓ 安全' }}
            </div>
            <!-- 危险区域实时统计 -->
            <div class="zone-statistics">
              <div class="zone-stat-item danger-stat">
                <span class="stat-icon">🚨</span>
                <span class="stat-label">当前危险区人数</span>
                <span class="stat-value">{{ zoneStatistics.current_in_danger }}</span>
              </div>
              <div class="zone-stat-row">
                <div class="zone-stat-item">
                  <span class="stat-label">进入次数</span>
                  <span class="stat-value enter">{{ zoneStatistics.total_entries }}</span>
                </div>
                <div class="zone-stat-item">
                  <span class="stat-label">离开次数</span>
                  <span class="stat-value exit">{{ zoneStatistics.total_exits }}</span>
                </div>
              </div>
              <!-- 一键清除按钮 -->
              <div class="zone-actions">
                <el-button type="danger" size="small" plain @click="resetZoneStats(false)">
                  🔄 重置统计
                </el-button>
                <el-button type="warning" size="small" plain @click="resetZoneStats(true)">
                  🗑️ 清除全部
                </el-button>
              </div>
              <!-- 最后事件时间 -->
              <div class="zone-last-time" v-if="zoneStatistics.last_entry_time || zoneStatistics.last_exit_time">
                <small v-if="zoneStatistics.last_entry_time">
                  最后进入: {{ formatDateTime(zoneStatistics.last_entry_time) }}
                </small>
                <small v-if="zoneStatistics.last_exit_time">
                  最后离开: {{ formatDateTime(zoneStatistics.last_exit_time) }}
                </small>
              </div>
            </div>
          </div>
          
          <!-- 产品检测状态 -->
          <div v-else class="detection-status product-status">
            <div class="product-result" v-if="lastProductDetection">
              <span class="product-type" :class="lastProductDetection.product_type">
                {{ lastProductDetection.product_type === 'product_a' ? '产品A' : 
                   lastProductDetection.product_type === 'product_b' ? '产品B' : '未知' }}
              </span>
              <span class="product-info">{{ lastProductDetection.color }} | {{ lastProductDetection.shape }}</span>
            </div>
            <div v-else class="no-product">
              等待检测产品...
            </div>
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
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getDashboard, sendControl, getAlerts, resolveAlert } from './api'
import { wsClient } from './utils/websocket'
import ConveyorBelt from './components/ConveyorBelt.vue'

const deviceId = ref('device_001')

// 传送带相关
const conveyorRef = ref(null)

const wsConnected = ref(false)
const currentTime = ref('')

// 生产状态
const productionStatus = ref('stopped')
const productionMode = ref('product_a')
const productionCount = ref(0)
const selectedMode = ref('product_a')
const conveyorSpeed = ref(1.0)

// 生产计划
const targetCount = ref(100)
const planProgress = ref({
  has_plan: false,
  target: 0,
  current: 0,
  progress: 0,
  remaining: 0,
  estimated_time: null
})

// 自动调度
const autoScheduleEnabled = ref(true)
const scheduleRules = ref({
  tempPause: true,
  humidityPause: true,
  pressurePause: true,
  productionStop: true,
  allNormalStart: true
})
const lastScheduleAction = ref('')

// 传感器数据
const currentTemp = ref(null)
const currentPressure = ref(null)
const currentHumidity = ref(null)
const tempData = ref([])
const pressureData = ref([])
const humidityData = ref([])  // 湿度历史数据

// 图表类型切换（温度/湿度）
const chartType = ref('temperature')  // 'temperature' 或 'humidity'

// 检测数据
const personCount = ref(0)
const inDangerZone = ref(false)

// 危险区域统计
const zoneStatistics = ref({
  total_entries: 0,
  total_exits: 0,
  current_in_danger: 0,
  last_entry_time: null,
  last_exit_time: null
})

// 检测模式
const detectionMode = ref('zone')  // zone=安全检测, product=产品检测
const lastProductDetection = ref(null)

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
const mainChartRef = ref(null)
const historyChartRef = ref(null)
let mainChart = null
let historyChart = null

// 图表类型标签
const chartTypeLabels = {
  temperature: '温度实时曲线',
  humidity: '湿度实时曲线',
  pressure: '压力实时曲线'
}

// 环境阈值配置
const thresholds = ref({
  tempMin: 10,
  tempMax: 35,
  humidityMin: 20,
  humidityMax: 80,
  pressureMin: 90,
  pressureMax: 110
})
const savingThresholds = ref(false)

// 历史数据查询
const historyType = ref('temperature')
const historyRange = ref('1h')
const historyData = ref([])

// 产品检测计数
const productACount = ref(0)
const productBCount = ref(0)

// 声音报警
let alarmAudio = null

// 星空粒子样式生成
const getStarStyle = (n, type) => {
  const seed = (n * 1337) % 100
  const top = (n * 7919) % 100
  
  let size, opacity, duration, delay
  
  if (type === 'sm') {
    // 远景星空：极小，几乎静止，闪烁
    size = Math.random() * 2 + 1
    opacity = Math.random() * 0.5 + 0.1
    duration = Math.random() * 3 + 2
    delay = Math.random() * 5
  } else if (type === 'md') {
    // 中景粒子：中等大小，缓慢漂浮
    size = Math.random() * 3 + 2
    opacity = Math.random() * 0.4 + 0.2
    duration = Math.random() * 10 + 10
    delay = Math.random() * 5
  } else {
    // 近景浮尘：较大，明显移动
    size = Math.random() * 4 + 3
    opacity = Math.random() * 0.3 + 0.1
    duration = Math.random() * 20 + 15
    delay = Math.random() * 5
  }

  return {
    left: `${seed}%`,
    top: `${top}%`,
    width: `${size}px`,
    height: `${size}px`,
    opacity: opacity,
    animationDelay: `${delay}s`,
    animationDuration: `${duration}s`
  }
}

// 废弃旧的粒子函数，但保留以防万一引用
const getParticleBgStyle = (n) => ({
  left: `${(n * 3.3) % 100}%`,
  top: `${(n * 7.1) % 100}%`,
  width: `${2 + (n % 4)}px`,
  height: `${2 + (n % 4)}px`,
  animationDelay: `${(n * 0.3) % 8}s`,
  animationDuration: `${4 + (n % 4)}s`
})

// 数据流样式生成
const getStreamStyle = (n) => ({
  left: `${n * 20}%`,
  animationDelay: `${n * 0.5}s`,
  animationDuration: `${3 + n * 0.5}s`
})

// 幽冥火火花样式生成
const getFireSparkStyle = (n) => ({
  left: `${5 + (n * 6.5) % 90}%`,
  animationDelay: `${(n * 0.4) % 5}s`,
  animationDuration: `${2 + (n % 3)}s`
})

// 计算属性
const statusText = computed(() => {
  const map = { running: '运行中', stopped: '已停止', paused: '已暂停' }
  return map[productionStatus.value] || '未知'
})

const modeText = computed(() => {
  const map = { product_a: '产品A', product_b: '产品B' }
  return map[productionMode.value] || '未知'
})

// 当前值显示（根据图表类型）
const currentValueLabel = computed(() => {
  const labels = { temperature: '当前温度', humidity: '当前湿度', pressure: '当前压力' }
  return labels[chartType.value]
})

const currentValueDisplay = computed(() => {
  if (chartType.value === 'temperature') {
    return currentTemp.value?.toFixed(1) ? `${currentTemp.value.toFixed(1)}°C` : '--°C'
  } else if (chartType.value === 'humidity') {
    return currentHumidity.value?.toFixed(1) ? `${currentHumidity.value.toFixed(1)}%` : '--%'
  } else {
    return currentPressure.value?.toFixed(1) ? `${currentPressure.value.toFixed(1)} kPa` : '-- kPa'
  }
})

const currentValueClass = computed(() => {
  if (chartType.value === 'temperature') {
    return { warning: currentTemp.value >= 80, danger: currentTemp.value >= 95 }
  } else if (chartType.value === 'humidity') {
    return { warning: currentHumidity.value >= 70, danger: currentHumidity.value >= 85 }
  } else {
    return { warning: currentPressure.value >= 115, danger: currentPressure.value >= 120 }
  }
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

// 图表配置
const chartConfigs = {
  temperature: {
    name: '°C',
    min: 0,
    max: 120,
    color: '#409eff',
    gradientStart: 'rgba(64, 158, 255, 0.35)',
    gradientEnd: 'rgba(64, 158, 255, 0.05)',
    visualMap: {
      show: false,
      pieces: [
        { lte: 80, color: '#3a91c7' },
        { gt: 80, lte: 95, color: '#d4915e' },
        { gt: 95, color: '#c75050' }
      ]
    }
  },
  humidity: {
    name: '%',
    min: 0,
    max: 100,
    color: '#67c23a',
    gradientStart: 'rgba(103, 194, 58, 0.35)',
    gradientEnd: 'rgba(103, 194, 58, 0.05)',
    visualMap: {
      show: false,
      pieces: [
        { lte: 70, color: '#67c23a' },
        { gt: 70, lte: 85, color: '#d4915e' },
        { gt: 85, color: '#c75050' }
      ]
    }
  },
  pressure: {
    name: 'kPa',
    min: 80,
    max: 150,
    color: '#2db7b5',
    gradientStart: 'rgba(45, 183, 181, 0.35)',
    gradientEnd: 'rgba(45, 183, 181, 0.05)',
    visualMap: null
  }
}

// 初始化图表
const initCharts = () => {
  // 主图表（温度/湿度/压力共用）
  mainChart = echarts.init(mainChartRef.value)
  const config = chartConfigs.temperature
  
  const option = {
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
      name: config.name, 
      min: config.min, 
      max: config.max,
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
          { offset: 0, color: config.gradientStart },
          { offset: 1, color: config.gradientEnd }
        ])
      },
      lineStyle: { color: config.color, width: 2 },
      itemStyle: { color: config.color, borderColor: '#0d2b45', borderWidth: 2 }
    }],
    animation: true,
    animationDuration: 180,
    animationEasing: 'linear'
  }
  
  if (config.visualMap) {
    option.visualMap = config.visualMap
  }
  
  mainChart.setOption(option)
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

// 只添加数据点，不更新图表
const addDataPoint = (dataArray, newValue, maxPoints = 30) => {
  const time = new Date().toLocaleTimeString('zh-CN')
  dataArray.push({ time, value: newValue })
  if (dataArray.length > maxPoints) dataArray.shift()
}

// 切换图表类型（温度/湿度/压力）
const switchChartType = (type) => {
  chartType.value = type
  
  const config = chartConfigs[type]
  let dataArray = tempData.value
  if (type === 'humidity') dataArray = humidityData.value
  else if (type === 'pressure') dataArray = pressureData.value
  
  const option = {
    yAxis: { 
      name: config.name, 
      min: config.min, 
      max: config.max 
    },
    series: [{
      data: dataArray.map(d => d.value),
      areaStyle: { 
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: config.gradientStart },
          { offset: 1, color: config.gradientEnd }
        ])
      },
      lineStyle: { color: config.color },
      itemStyle: { color: config.color, borderColor: '#0d2b45', borderWidth: 2 }
    }],
    xAxis: { data: dataArray.map(d => d.time) }
  }
  
  if (config.visualMap) {
    option.visualMap = config.visualMap
  }
  
  mainChart.setOption(option)
}

// ========== 环境阈值配置 ==========
const saveThresholds = async () => {
  savingThresholds.value = true
  try {
    // 发送阈值到后端
    const response = await fetch(`http://${window.location.hostname}:8000/api/thresholds/${deviceId.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(thresholds.value)
    })
    if (response.ok) {
      ElMessage.success('阈值配置已保存')
    } else {
      ElMessage.warning('阈值配置保存失败，本地生效')
    }
  } catch (e) {
    ElMessage.warning('网络错误，阈值配置仅本地生效')
  }
  savingThresholds.value = false
}

// ========== 历史数据查询 ==========
const initHistoryChart = () => {
  if (!historyChartRef.value) return
  historyChart = echarts.init(historyChartRef.value)
  historyChart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 20, right: 15, bottom: 30, left: 55 },
    xAxis: { 
      type: 'category', 
      data: [],
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
      axisLabel: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 10 }
    },
    yAxis: { 
      type: 'value',
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
      splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
      axisLabel: { color: 'rgba(255, 255, 255, 0.5)', fontSize: 10 }
    },
    series: [{
      type: 'line',
      smooth: true,
      data: [],
      areaStyle: { 
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.35)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      },
      lineStyle: { color: '#409eff', width: 2 }
    }]
  })
}

const loadHistoryData = async () => {
  // 根据选择的时间范围获取历史数据
  const rangeMap = { '1h': 1, '6h': 6, '24h': 24 }
  const hours = rangeMap[historyRange.value] || 1
  
  try {
    // 从后端API获取历史数据
    const response = await fetch(
      `http://${window.location.hostname}:8000/api/sensor/history?device_id=${deviceId.value}&sensor_type=${historyType.value}&hours=${hours}`
    )
    
    let sourceData = []
    if (response.ok) {
      const data = await response.json()
      // 转换数据格式并按时间排序
      sourceData = data.map(item => ({
        time: new Date(item.timestamp).toLocaleTimeString('zh-CN'),
        value: item.value
      })).reverse()  // 按时间正序
    }
    
    // 如果后端没有数据，使用本地缓存的实时数据
    if (sourceData.length === 0) {
      if (historyType.value === 'temperature') {
        sourceData = tempData.value
      } else if (historyType.value === 'humidity') {
        sourceData = humidityData.value
      } else {
        sourceData = pressureData.value
      }
    }
    
    // 更新图表
    if (historyChart) {
      const colors = {
        temperature: '#409eff',
        humidity: '#67c23a',
        pressure: '#2db7b5'
      }
      const color = colors[historyType.value]
      const units = { temperature: '°C', humidity: '%', pressure: 'kPa' }
      
      historyChart.setOption({
        yAxis: { name: units[historyType.value] },
        xAxis: { data: sourceData.map(d => d.time) },
        series: [{
          data: sourceData.map(d => d.value),
          lineStyle: { color },
          itemStyle: { color },
          areaStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: color + '59' },
              { offset: 1, color: color + '0d' }
            ])
          }
        }]
      })
    }
  } catch (e) {
    console.log('加载历史数据失败:', e)
  }
}

// ========== 声音报警 ==========
// playAlarmSound 函数定义在下方 triggerAlarm 附近

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

// 设置传送带速度
const setConveyorSpeed = async (speed) => {
  try {
    const response = await fetch(`/api/conveyor/${deviceId.value}/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'set_speed', params: { speed } })
    })
    if (response.ok) {
      ElMessage.success(`速度已设置为 ${speed}x`)
    }
  } catch (e) {
    ElMessage.error('设置速度失败')
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

// 设置生产计划
const setPlan = async () => {
  try {
    const response = await fetch(`/api/scheduler/${deviceId.value}/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        target_count: targetCount.value,
        auto_stop: scheduleRules.value.productionStop
      })
    })
    if (response.ok) {
      ElMessage.success(`生产计划已设置: 目标 ${targetCount.value} 件`)
      await loadPlanProgress()
    }
  } catch (e) {
    ElMessage.error('设置计划失败')
  }
}

// 清除生产计划
const clearPlan = async () => {
  try {
    const response = await fetch(`/api/scheduler/${deviceId.value}/plan`, {
      method: 'DELETE'
    })
    if (response.ok) {
      ElMessage.success('生产计划已清除')
      planProgress.value = { has_plan: false, target: 0, current: 0, progress: 0, remaining: 0, estimated_time: null }
    }
  } catch (e) {
    ElMessage.error('清除计划失败')
  }
}

// 加载生产计划进度
const loadPlanProgress = async () => {
  try {
    const response = await fetch(`/api/scheduler/${deviceId.value}/progress`)
    if (response.ok) {
      planProgress.value = await response.json()
    }
  } catch (e) {
    console.error('加载计划进度失败:', e)
  }
}

// 切换自动调度
const toggleAutoSchedule = async (enabled) => {
  // 批量更新所有规则
  const ruleIds = ['temp_danger_pause', 'humidity_danger_pause', 'pressure_danger_pause', 'production_complete', 'all_normal_start']
  for (const ruleId of ruleIds) {
    await updateScheduleRule(ruleId, enabled)
  }
  scheduleRules.value.tempPause = enabled
  scheduleRules.value.humidityPause = enabled
  scheduleRules.value.pressurePause = enabled
  scheduleRules.value.productionStop = enabled
  scheduleRules.value.allNormalStart = enabled
}

// 更新调度规则
const updateScheduleRule = async (ruleId, enabled) => {
  try {
    await fetch(`/api/scheduler/${deviceId.value}/rules/${ruleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    })
  } catch (e) {
    console.error('更新规则失败:', e)
  }
}

// 加载调度规则
const loadScheduleRules = async () => {
  try {
    const response = await fetch(`/api/scheduler/${deviceId.value}/rules`)
    if (response.ok) {
      const rules = await response.json()
      for (const rule of rules) {
        if (rule.id === 'temp_danger_pause') scheduleRules.value.tempPause = rule.enabled
        if (rule.id === 'humidity_danger_pause') scheduleRules.value.humidityPause = rule.enabled
        if (rule.id === 'pressure_danger_pause') scheduleRules.value.pressurePause = rule.enabled
        if (rule.id === 'production_complete') scheduleRules.value.productionStop = rule.enabled
        if (rule.id === 'all_normal_start') scheduleRules.value.allNormalStart = rule.enabled
      }
    }
  } catch (e) {
    console.error('加载规则失败:', e)
  }
}

// 切换检测模式
const switchDetectionMode = async (mode) => {
  try {
    const response = await fetch(`/api/detection/mode/${deviceId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    })
    if (response.ok) {
      ElMessage.success(`已切换到${mode === 'zone' ? '安全检测' : '产品检测'}模式`)
    }
  } catch (e) {
    ElMessage.error('切换模式失败')
  }
}

// 加载检测模式
const loadDetectionMode = async () => {
  try {
    const response = await fetch(`/api/detection/mode/${deviceId.value}`)
    if (response.ok) {
      const data = await response.json()
      detectionMode.value = data.mode
    }
  } catch (e) {
    console.error('加载检测模式失败:', e)
  }
}

// 加载危险区域统计
const loadZoneStatistics = async () => {
  try {
    const response = await fetch(`/api/zone/statistics/${deviceId.value}`)
    if (response.ok) {
      const data = await response.json()
      zoneStatistics.value = data.statistics
      inDangerZone.value = data.statistics.current_in_danger > 0
    }
  } catch (e) {
    console.error('加载危险区域统计失败:', e)
  }
}

// 重置危险区域统计
const resetZoneStats = async (clearEvents = false) => {
  try {
    const url = `/api/zone/statistics/${deviceId.value}?clear_events=${clearEvents}`
    const response = await fetch(url, {
      method: 'DELETE'
    })
    if (response.ok) {
      const data = await response.json()
      zoneStatistics.value = data.statistics
      ElMessage.success(data.message)
    }
  } catch (e) {
    ElMessage.error('重置统计失败')
  }
}

// 格式化日期时间
const formatDateTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 触发报警器
const triggerAlarm = () => {
  alarmActive.value = true
  ledStatus.value.alert = true
  
  // 播放声音报警（循环播放直到关闭）
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
        // 只有当前显示温度图表时才更新图表
        if (chartType.value === 'temperature') {
          updateChart(mainChart, tempData.value, data.value)
        } else {
          addDataPoint(tempData.value, data.value)
        }
      } else if (data.sensor_type === 'pressure') {
        currentPressure.value = data.value
        // 只有当前显示压力图表时才更新图表
        if (chartType.value === 'pressure') {
          updateChart(mainChart, pressureData.value, data.value)
        } else {
          addDataPoint(pressureData.value, data.value)
        }
      } else if (data.sensor_type === 'humidity') {
        currentHumidity.value = data.value
        // 只有当前显示湿度图表时才更新图表
        if (chartType.value === 'humidity') {
          updateChart(mainChart, humidityData.value, data.value)
        } else {
          addDataPoint(humidityData.value, data.value)
        }
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
      
      // 如果是入侵报警或进入危险区，触发全屏报警器
      if (data.alert_type === 'intrusion' || data.alert_type === 'zone_enter') {
        triggerAlarm()
        dangerEntries.value++
      } else if (data.alert_type === 'zone_exit') {
        // 离开危险区，显示提示信息
        ElMessage({
          message: data.message,
          type: 'success',
          duration: 3000
        })
      } else {
        // 其他报警只闪烁LED
        ledStatus.value.alert = true
        setTimeout(() => {
          ledStatus.value.alert = false
        }, 5000)
      }
    })
    
    // 危险区域统计更新
    wsClient.on('zone_statistics', (data) => {
      if (data.device_id === deviceId.value) {
        zoneStatistics.value = data.statistics
        inDangerZone.value = data.statistics.current_in_danger > 0
        
        // 根据事件类型显示不同提示
        if (data.event_type === 'enter') {
          ElMessage({
            message: `🚨 ${data.message}`,
            type: 'error',
            duration: 5000
          })
        } else if (data.event_type === 'exit') {
          ElMessage({
            message: `✅ ${data.message}`,
            type: 'success',
            duration: 3000
          })
        } else if (data.event_type === 'reset') {
          ElMessage({
            message: '📊 危险区域统计已重置',
            type: 'info',
            duration: 2000
          })
        }
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
      
      // 更新生产计划进度
      loadPlanProgress()
    })
    
    // 调度动作事件
    wsClient.on('schedule_action', (data) => {
      lastScheduleAction.value = `${data.message} (${new Date().toLocaleTimeString()})`
      ElMessage({
        message: `⚡ 自动调度: ${data.message}`,
        type: 'info',
        duration: 5000
      })
    })
    
    // 产品检测结果
    wsClient.on('product_detection', (data) => {
      if (data.device_id === deviceId.value) {
        lastProductDetection.value = {
          product_type: data.product_type,
          color: data.color,
          shape: data.shape,
          confidence: data.confidence
        }
        
        // 累计产品计数并同步到后端
        if (data.product_type === 'product_a' || data.product_type === 'product_b') {
          if (data.product_type === 'product_a') {
            productACount.value++
          } else {
            productBCount.value++
          }
          productionCount.value++
          
          // 同步到后端数据库
          syncProductionCount()
        }
        
        // 显示检测成功提示
        ElMessage({
          message: `📦 检测到 ${data.product_type === 'product_a' ? '产品A' : '产品B'} (${data.color}/${data.shape})`,
          type: 'success',
          duration: 2000
        })
      }
    })
    
    // 检测模式变化
    wsClient.on('detection_mode_change', (data) => {
      if (data.device_id === deviceId.value) {
        detectionMode.value = data.mode
      }
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
    
    // 传送带状态更新
    wsClient.on('conveyor_update', (data) => {
      if (data.device_id === deviceId.value) {
        nextTick(() => {
          if (conveyorRef.value && typeof conveyorRef.value.updateState === 'function') {
            conveyorRef.value.updateState(data)
          }
        })
      }
    })
    
  } catch (e) {
    console.error('WebSocket连接失败:', e)
    wsConnected.value = false
  }
}

// 监听历史数据类型变化
watch(historyType, () => {
  loadHistoryData()
})

// 生命周期
let timeInterval = null

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  
  initCharts()
  await loadDashboard()
  await loadAlerts()
  await loadScheduleRules()
  await loadPlanProgress()
  await loadDetectionMode()
  await loadZoneStatistics()
  await loadThresholds()
  await setupWebSocket()
  
  // 初始化历史图表
  nextTick(() => {
    initHistoryChart()
    loadHistoryData()
  })
  
  // 窗口大小变化时重绘图表
  window.addEventListener('resize', () => {
    mainChart?.resize()
    historyChart?.resize()
  })
})

onUnmounted(() => {
  clearInterval(timeInterval)
  if (videoTimeout) clearTimeout(videoTimeout)
  if (alarmTimeout) clearTimeout(alarmTimeout)
  stopAlarmSound()
  wsClient.close()
  mainChart?.dispose()
  historyChart?.dispose()
})

// 加载阈值配置
const loadThresholds = async () => {
  try {
    const response = await fetch(`http://${window.location.hostname}:8000/api/thresholds/${deviceId.value}`)
    if (response.ok) {
      const data = await response.json()
      thresholds.value = data
    }
  } catch (e) {
    console.log('加载阈值配置失败，使用默认值')
  }
}

// 同步产品计数到后端（防抖处理）
let syncTimeout = null
const syncProductionCount = () => {
  if (syncTimeout) clearTimeout(syncTimeout)
  syncTimeout = setTimeout(async () => {
    try {
      await fetch(`http://${window.location.hostname}:8000/api/status/${deviceId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ production_count: productionCount.value })
      })
    } catch (e) {
      console.log('同步产品计数失败')
    }
  }, 500)  // 500ms防抖，避免频繁请求
}
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
    radial-gradient(circle at 50% 50%, rgba(20, 30, 50, 0.4) 0%, transparent 80%),
    linear-gradient(180deg, #020408 0%, #050a14 40%, #081020 100%);
  color: var(--text-primary);
  font-family: 'Microsoft YaHei', 'PingFang SC', -apple-system, sans-serif;
  position: relative;
  overflow: hidden;
}

/* 微妙的网格背景 - 增强可见度 */
.dashboard::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(rgba(58, 145, 199, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(58, 145, 199, 0.05) 1px, transparent 1px);
  background-size: 60px 60px;
  pointer-events: none;
  z-index: 0;
  animation: gridMove 40s linear infinite;
  opacity: 0.6;
}

@keyframes gridMove {
  0% { transform: perspective(1000px) rotateX(5deg) translateY(0); }
  100% { transform: perspective(1000px) rotateX(5deg) translateY(60px); }
}

/* ========================================
   超炫酷背景特效层
   ======================================== */
.bg-effects {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

/* 星云背景 */
.nebula-bg {
  position: absolute;
  inset: -50%;
  width: 200%;
  height: 200%;
  background: 
    radial-gradient(circle at 30% 40%, rgba(58, 145, 199, 0.15) 0%, transparent 40%),
    radial-gradient(circle at 70% 60%, rgba(45, 183, 181, 0.1) 0%, transparent 40%),
    radial-gradient(circle at 50% 20%, rgba(70, 30, 100, 0.1) 0%, transparent 50%);
  filter: blur(60px);
  animation: nebulaRotate 120s linear infinite;
  opacity: 0.7;
}

@keyframes nebulaRotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 粒子系统 */
.particles-container {
  position: absolute;
  inset: 0;
}

.particles-container .particle {
  position: absolute;
  background: white;
  border-radius: 50%;
  box-shadow: 0 0 4px rgba(255, 255, 255, 0.8);
}

/* 远景星空 - 闪烁 */
.particle.star-sm {
  background: rgba(255, 255, 255, 0.6);
  animation: twinkle 4s ease-in-out infinite;
}

/* 中景粒子 - 漂浮 */
.particle.star-md {
  background: rgba(180, 220, 255, 0.7);
  box-shadow: 0 0 6px rgba(180, 220, 255, 0.5);
  animation: floatUp 20s linear infinite;
}

/* 近景浮尘 - 缓慢移动 */
.particle.star-lg {
  background: rgba(100, 200, 255, 0.4);
  box-shadow: 0 0 10px rgba(100, 200, 255, 0.3);
  filter: blur(1px);
  animation: floatUp 40s linear infinite;
}

@keyframes twinkle {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

@keyframes floatUp {
  0% { transform: translateY(0); }
  100% { transform: translateY(-100vh); }
}

/* 能量流动线条 */
.energy-lines {
  position: absolute;
  inset: 0;
}

.energy-line {
  position: absolute;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(58, 145, 199, 0.1) 20%,
    rgba(58, 145, 199, 0.6) 50%, 
    rgba(58, 145, 199, 0.1) 80%,
    transparent 100%
  );
  filter: blur(0.5px);
  animation: energyFlow 8s linear infinite;
}

.energy-line.line-1 {
  top: 15%;
  width: 60%;
  left: -60%;
  animation-delay: 0s;
}

.energy-line.line-2 {
  top: 45%;
  width: 80%;
  left: -80%;
  animation-delay: 2s;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(45, 183, 181, 0.1) 20%,
    rgba(45, 183, 181, 0.5) 50%, 
    rgba(45, 183, 181, 0.1) 80%,
    transparent 100%
  );
}

.energy-line.line-3 {
  top: 70%;
  width: 50%;
  left: -50%;
  animation-delay: 4s;
}

.energy-line.line-4 {
  top: 90%;
  width: 70%;
  left: -70%;
  animation-delay: 6s;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(45, 183, 181, 0.1) 20%,
    rgba(45, 183, 181, 0.4) 50%, 
    rgba(45, 183, 181, 0.1) 80%,
    transparent 100%
  );
}

@keyframes energyFlow {
  0% { transform: translateX(0); }
  100% { transform: translateX(200%); }
}

/* 光斑效果 */
.light-orbs {
  position: absolute;
  inset: 0;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  animation: orbFloat 15s ease-in-out infinite;
}

.orb-1 {
  top: 10%;
  left: 15%;
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(58, 145, 199, 0.15) 0%, transparent 70%);
  animation-delay: 0s;
}

.orb-2 {
  top: 60%;
  right: 10%;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(45, 183, 181, 0.12) 0%, transparent 70%);
  animation-delay: 5s;
}

.orb-3 {
  bottom: 20%;
  left: 40%;
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, rgba(58, 145, 199, 0.1) 0%, transparent 70%);
  animation-delay: 10s;
}

@keyframes orbFloat {
  0%, 100% { 
    transform: translate(0, 0) scale(1);
    opacity: 0.6;
  }
  25% { 
    transform: translate(30px, -40px) scale(1.1);
    opacity: 0.8;
  }
  50% { 
    transform: translate(-20px, 30px) scale(0.9);
    opacity: 0.5;
  }
  75% { 
    transform: translate(40px, 20px) scale(1.05);
    opacity: 0.7;
  }
}

/* 扫描线 */
.scan-line-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 200px;
  background: linear-gradient(180deg, 
    rgba(58, 145, 199, 0.08) 0%,
    rgba(58, 145, 199, 0.02) 50%,
    transparent 100%
  );
  animation: scanBg 6s ease-in-out infinite;
}

@keyframes scanBg {
  0%, 100% { 
    transform: translateY(-100%);
    opacity: 0;
  }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { 
    transform: translateY(100vh);
    opacity: 0;
  }
}

/* 数据流 */
.data-stream {
  position: absolute;
  inset: 0;
}

.stream-line {
  position: absolute;
  top: 0;
  width: 1px;
  height: 100%;
  background: linear-gradient(180deg, 
    transparent 0%,
    transparent 40%,
    rgba(58, 145, 199, 0.4) 50%,
    transparent 60%,
    transparent 100%
  );
  animation: streamFlow 5s linear infinite;
}

@keyframes streamFlow {
  0% { 
    background-position: 0 -100%;
  }
  100% { 
    background-position: 0 100%;
  }
}

/* 六边形网格 */
.hex-grid {
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='49' viewBox='0 0 28 49'%3E%3Cg fill-rule='evenodd'%3E%3Cg fill='%233a91c7' fill-opacity='0.02'%3E%3Cpath d='M13.99 9.25l13 7.5v15l-13 7.5L1 31.75v-15l12.99-7.5zM3 17.9v12.7l10.99 6.34 11-6.35V17.9l-11-6.34L3 17.9zM0 15l12.98-7.5V0h-2v6.35L0 12.69v2.3zm0 18.5L12.98 41v8h-2v-6.85L0 35.81v-2.3zM15 0v7.5L27.99 15H28v-2.31h-.01L17 6.35V0h-2zm0 49v-8l12.99-7.5H28v2.31h-.01L17 42.15V49h-2z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  opacity: 0.5;
  animation: hexMove 30s linear infinite;
}

@keyframes hexMove {
  0% { background-position: 0 0; }
  100% { background-position: 56px 98px; }
}

/* ========================================
   🔥 蓝色火焰特效 - 升起飘散版
   ======================================== */
.ghost-fire-container {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 400px; /* 增加高度以便观察升起过程 */
  pointer-events: none;
  z-index: 1;
  overflow: hidden;
}

/* 幽冥火焰 - 升起主体 */
.ghost-flame {
  position: absolute;
  bottom: -50px; /* 起始位置在屏幕外 */
  width: 60px;
  height: 100px;
  opacity: 0;
  transform-origin: center bottom;
  /* 基础动画：升起并消散 */
  animation: flameCycle 6s ease-in-out infinite;
}

/* 火焰升起循环动画 */
@keyframes flameCycle {
  0% {
    bottom: -50px;
    transform: scale(0.5);
    opacity: 0;
    filter: blur(5px);
  }
  20% {
    bottom: 20px;
    transform: scale(1);
    opacity: 0.8;
    filter: blur(2px);
  }
  50% {
    bottom: 80px;
    transform: scale(1.1);
    opacity: 0.6;
    filter: blur(4px);
  }
  80% {
    bottom: 150px;
    transform: scale(1.3);
    opacity: 0.2;
    filter: blur(10px);
  }
  100% {
    bottom: 200px;
    transform: scale(1.5);
    opacity: 0;
    filter: blur(20px);
  }
}

/* 火焰内部结构 - 保持摇曳感 */
.ghost-flame::before,
.ghost-flame::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
}

/* 外焰 */
.ghost-flame::before {
  width: 100%;
  height: 100%;
  background: linear-gradient(0deg,
    rgba(30, 144, 255, 0.8) 0%,
    rgba(100, 200, 255, 0.4) 60%,
    rgba(200, 240, 255, 0) 100%
  );
  animation: flickerBody 1s ease-in-out infinite alternate;
}

/* 内焰 */
.ghost-flame::after {
  width: 60%;
  height: 70%;
  background: linear-gradient(0deg,
    rgba(220, 250, 255, 0.9) 0%,
    rgba(150, 220, 255, 0.5) 50%,
    transparent 100%
  );
  filter: blur(4px);
  animation: flickerCore 0.6s ease-in-out infinite alternate;
}

@keyframes flickerBody {
  0% { transform: translateX(-50%) scaleX(1) skewX(0deg); }
  100% { transform: translateX(-50%) scaleX(0.95) skewX(2deg); }
}

@keyframes flickerCore {
  0% { transform: translateX(-50%) scaleY(1); opacity: 0.8; }
  100% { transform: translateX(-50%) scaleY(1.1); opacity: 1; }
}

/* 8组火焰 - 错落升起 */
.flame-1 { left: 10%; animation-delay: 0s; animation-duration: 5s; }
.flame-2 { left: 22%; animation-delay: 1.5s; animation-duration: 6s; }
.flame-3 { left: 35%; animation-delay: 0.5s; animation-duration: 5.5s; }
.flame-4 { left: 48%; animation-delay: 2.5s; animation-duration: 6.5s; }
.flame-5 { left: 60%; animation-delay: 1s; animation-duration: 5.2s; }
.flame-6 { left: 72%; animation-delay: 3s; animation-duration: 5.8s; }
.flame-7 { left: 85%; animation-delay: 2s; animation-duration: 6.2s; }
.flame-8 { left: 5%; animation-delay: 4s; animation-duration: 5.3s; }

/* 火花粒子 - 飘散效果 */
.fire-spark {
  position: absolute;
  /* 初始位置较低，随后飘起 */
  bottom: 0; 
  width: 4px;
  height: 4px;
  background: rgba(180, 230, 255, 0.9);
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(100, 200, 255, 0.8);
  /* 基础动画 */
  opacity: 0;
  animation: sparkDrift 5s linear infinite;
}

@keyframes sparkDrift {
  0% {
    bottom: 20px;
    transform: translateX(0) scale(0.5);
    opacity: 0;
  }
  20% {
    opacity: 1;
    transform: translateX(5px) scale(1);
  }
  50% {
    transform: translateX(-10px) scale(0.8);
    opacity: 0.8;
  }
  100% {
    bottom: 350px; /* 飘得更高 */
    transform: translateX(20px) scale(0);
    opacity: 0;
  }
}

/* 底部微弱光晕 */
.fire-glow {
  position: absolute;
  bottom: -40px;
  left: 0;
  right: 0;
  height: 100px;
  background: radial-gradient(ellipse 60% 60% at 50% 100%, 
    rgba(30, 144, 255, 0.2) 0%, 
    transparent 70%
  );
  animation: glowPulse 4s ease-in-out infinite;
}

/* ========================================
   顶部标题栏 - 赛博HUD风格
   ======================================== */
.header {
  position: relative;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
  height: 70px;
  background: rgba(10, 15, 25, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(58, 145, 199, 0.3);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
}

/* 顶部流光线条 */
.header::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    var(--primary-color) 20%, 
    var(--accent-light) 50%, 
    var(--primary-color) 80%, 
    transparent 100%
  );
  box-shadow: 0 0 10px var(--primary-color);
  opacity: 0.8;
}

.header h1 {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #fff;
  text-shadow: 0 0 10px rgba(58, 145, 199, 0.8);
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(180deg, #fff 0%, #bde6ff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* LOGO图标发光 */
.header h1::before {
  content: '◈';
  font-size: 28px;
  background: none;
  -webkit-text-fill-color: var(--accent-light);
  filter: drop-shadow(0 0 5px var(--accent-light));
  animation: logoSpin 10s linear infinite;
}

@keyframes logoSpin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.header-info {
  display: flex;
  gap: 30px;
  align-items: center;
  background: rgba(0, 0, 0, 0.3);
  padding: 8px 20px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.connection-status {
  font-size: 13px;
  color: var(--danger-color);
  font-family: var(--font-mono);
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 8px;
  text-transform: uppercase;
}

.connection-status::before {
  content: '';
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}

.connection-status.connected {
  color: var(--success-color);
}

.connection-status.connected::before {
  animation: blink 2s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.time {
  font-size: 14px;
  color: var(--primary-light);
  font-family: var(--font-mono);
  letter-spacing: 1px;
  text-shadow: 0 0 5px rgba(58, 145, 199, 0.5);
}

/* ========================================
   主内容区域 - 响应式布局
   ======================================== */
.main-content {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  grid-template-rows: 1fr; /* 关键：让子元素填满可用高度 */
  gap: 16px;
  padding: 16px;
  height: calc(100vh - 70px); /* 使用固定高度 */
  overflow: hidden;
}

/* 响应式布局 - 中等屏幕 */
@media (max-width: 1400px) {
  .main-content {
    grid-template-columns: 260px 1fr 240px;
    gap: 12px;
    padding: 12px;
  }
}

/* 响应式布局 - 小屏幕 */
@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 240px 1fr 220px;
    gap: 10px;
    padding: 10px;
  }
}

/* 响应式布局 - 平板 */
@media (max-width: 1024px) {
  .main-content {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
    height: auto;
    overflow-y: auto;
    padding-bottom: 40px;
  }
}

/* ========================================
   卡片组件 - 赛博边框升级版
   ======================================== */
.card {
  background: rgba(10, 15, 25, 0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 4px; /* 减小圆角以配合硬朗风格 */
  padding: 16px;
  border: 1px solid rgba(58, 145, 199, 0.2);
  box-shadow: 
    0 4px 24px rgba(0, 0, 0, 0.4),
    inset 0 0 30px rgba(58, 145, 199, 0.05);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  /* 确保卡片内容不会被截断 */
  min-height: fit-content;
  flex-shrink: 0;
}

/* 顶部流光 */
.card::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--primary-color), transparent);
  transition: left 0.5s ease;
  z-index: 1;
}

.card:hover::before {
  left: 100%;
  transition: left 0.8s ease;
}

/* 四角装饰 */
.card::after {
  content: '';
  position: absolute;
  inset: 0;
  border: 1px solid transparent;
  /* 使用 gradient 模拟四角 */
  background: 
    linear-gradient(135deg, var(--primary-color) 0%, var(--primary-color) 100%) top left,
    linear-gradient(135deg, var(--primary-color) 0%, var(--primary-color) 100%) top right,
    linear-gradient(135deg, var(--primary-color) 0%, var(--primary-color) 100%) bottom left,
    linear-gradient(135deg, var(--primary-color) 0%, var(--primary-color) 100%) bottom right;
  background-size: 8px 8px; /* 边角大小 */
  background-repeat: no-repeat;
  mask: 
    linear-gradient(#fff 0 0) content-box, 
    linear-gradient(#fff 0 0);
  -webkit-mask: 
    linear-gradient(#fff 0 0) content-box, 
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  opacity: 0.5;
  transition: opacity 0.3s ease;
}

/* 真正的四角SVG替代方案（用CSS模拟） */
.card > .corner-marker {
  position: absolute;
  width: 10px;
  height: 10px;
  border-color: var(--primary-light);
  border-style: solid;
  transition: all 0.3s ease;
  pointer-events: none;
  opacity: 0.6;
}

.card:hover {
  border-color: rgba(58, 145, 199, 0.5);
  transform: translateY(-2px);
  box-shadow: 
    0 10px 40px rgba(0, 0, 0, 0.6),
    0 0 20px rgba(58, 145, 199, 0.1),
    inset 0 0 50px rgba(58, 145, 199, 0.1);
}

.card:hover::after {
  opacity: 1;
  background-size: 12px 12px; /* 悬停时边角变大 */
}

.card h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--primary-light);
  text-transform: uppercase;
  letter-spacing: 2px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(58, 145, 199, 0.1);
}

/* 标题前的装饰块 */
.card h3::before {
  content: '';
  display: block;
  width: 4px;
  height: 16px;
  background: var(--accent-color);
  box-shadow: 0 0 8px var(--accent-color);
}

/* ========================================
   自定义控件样式 - 赛博按钮
   ======================================== */
.el-button {
  border: none !important;
  background: rgba(58, 145, 199, 0.15) !important;
  color: var(--primary-light) !important;
  border: 1px solid rgba(58, 145, 199, 0.3) !important;
  transition: all 0.3s ease !important;
  font-family: var(--font-mono) !important;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.el-button:hover, .el-button:focus {
  background: rgba(58, 145, 199, 0.3) !important;
  box-shadow: 0 0 15px rgba(58, 145, 199, 0.4) !important;
  color: #fff !important;
  border-color: var(--primary-light) !important;
  transform: translateY(-1px);
}

.el-button--primary {
  background: rgba(58, 145, 199, 0.3) !important;
  border-color: var(--primary-color) !important;
}

.el-button--success {
  background: rgba(74, 157, 110, 0.2) !important;
  color: var(--success-color) !important;
  border-color: rgba(74, 157, 110, 0.4) !important;
}

.el-button--success:hover {
  background: rgba(74, 157, 110, 0.4) !important;
  box-shadow: 0 0 15px rgba(74, 157, 110, 0.4) !important;
  color: #fff !important;
}

.el-button--danger {
  background: rgba(199, 80, 80, 0.2) !important;
  color: var(--danger-color) !important;
  border-color: rgba(199, 80, 80, 0.4) !important;
}

.el-button--danger:hover {
  background: rgba(199, 80, 80, 0.4) !important;
  box-shadow: 0 0 15px rgba(199, 80, 80, 0.4) !important;
  color: #fff !important;
}

.el-button.is-disabled {
  opacity: 0.4;
  cursor: not-allowed;
  filter: grayscale(1);
  box-shadow: none !important;
  transform: none !important;
}

/* 自定义开关 */
.el-switch__core {
  background: rgba(0, 0, 0, 0.5) !important;
  border: 1px solid rgba(255, 255, 255, 0.2) !important;
}

.el-switch.is-checked .el-switch__core {
  background: var(--primary-color) !important;
  border-color: var(--primary-light) !important;
  box-shadow: 0 0 10px rgba(58, 145, 199, 0.5);
}

/* 自定义输入框 */
.el-input__wrapper {
  background-color: rgba(0, 0, 0, 0.3) !important;
  box-shadow: 0 0 0 1px rgba(58, 145, 199, 0.3) inset !important;
  color: var(--text-primary) !important;
}

.el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--primary-color) inset !important;
}

.el-input__inner {
  color: #fff !important;
  font-family: var(--font-mono);
}

/* ========================================
   左侧面板 - 可滚动
   ======================================== */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: scroll !important; /* 强制显示滚动条 */
  overflow-x: hidden;
  padding-right: 4px;
  padding-bottom: 20px;
  /* 关键：Grid子项必须有这些属性才能滚动 */
  height: 100%;
  min-height: 0;
}

/* 自定义滚动条样式 - 增强可见性 */
.left-panel::-webkit-scrollbar {
  width: 8px; /* 加宽以便拖动 */
}

.left-panel::-webkit-scrollbar-track {
  background: rgba(10, 20, 30, 0.6); /* 更深的背景增加对比度 */
  border-radius: 4px;
}

.left-panel::-webkit-scrollbar-thumb {
  background: rgba(58, 145, 199, 0.5); /* 默认可见 */
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.left-panel::-webkit-scrollbar-thumb:hover {
  background: var(--primary-color);
  box-shadow: 0 0 10px rgba(58, 145, 199, 0.5);
}

/* ========================================
   中间面板 - 可滚动
   ======================================== */
.center-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: scroll !important; /* 强制显示滚动条 */
  overflow-x: hidden;
  padding-right: 4px;
  padding-bottom: 20px;
  /* 关键：Grid子项必须有这些属性才能滚动 */
  height: 100%;
  min-height: 0;
}

.center-panel::-webkit-scrollbar {
  width: 8px;
}

.center-panel::-webkit-scrollbar-track {
  background: rgba(10, 20, 30, 0.6);
  border-radius: 4px;
}

.center-panel::-webkit-scrollbar-thumb {
  background: rgba(58, 145, 199, 0.5);
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.center-panel::-webkit-scrollbar-thumb:hover {
  background: var(--primary-color);
  box-shadow: 0 0 10px rgba(58, 145, 199, 0.5);
}

/* 传送带卡片 */
.conveyor-card {
  flex-shrink: 0;
  min-height: 280px;
}

/* 图表行 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  flex-shrink: 0;
}

@media (max-width: 1200px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}

.chart-card,
.history-card {
  min-height: 300px;
}

/* ========================================
   右侧面板 - 可滚动
   ======================================== */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: scroll !important; /* 强制显示滚动条 */
  overflow-x: hidden;
  padding-right: 4px;
  padding-bottom: 20px;
  /* 关键：Grid子项必须有这些属性才能滚动 */
  height: 100%;
  min-height: 0;
}

.right-panel::-webkit-scrollbar {
  width: 8px;
}

.right-panel::-webkit-scrollbar-track {
  background: rgba(10, 20, 30, 0.6);
  border-radius: 4px;
}

.right-panel::-webkit-scrollbar-thumb {
  background: rgba(58, 145, 199, 0.5);
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.right-panel::-webkit-scrollbar-thumb:hover {
  background: var(--primary-color);
  box-shadow: 0 0 10px rgba(58, 145, 199, 0.5);
}

/* 检测卡片 */
.detection-card {
  flex-shrink: 0;
  min-height: 350px;
}

/* 报警卡片 */
.alert-card {
  flex-shrink: 0;
}

/* 统计信息卡片 */
.stats-card {
  flex-shrink: 0;
}

/* LED状态卡片 */
.led-card {
  flex-shrink: 0;
}

/* 设备信息卡片 */
.device-card {
  flex-shrink: 0;
}

/* 生产状态卡片 - 终极增强版 */
.status-card {
  position: relative;
  overflow: hidden;
}

/* 状态指示器 - 晶体呼吸效果 */
.status-indicator {
  display: inline-block;
  padding: 12px 32px;
  border-radius: 4px;
  font-size: 26px;
  font-weight: 700;
  margin-bottom: 16px;
  letter-spacing: 6px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  min-width: 160px;
  text-align: center;
  position: relative;
  overflow: hidden;
  transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(10px);
  z-index: 1;
}

/* 玻璃质感光泽 */
.status-indicator::before {
  content: '';
  position: absolute;
  top: 0;
  left: -150%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    rgba(255, 255, 255, 0.4),
    rgba(255, 255, 255, 0.2),
    transparent
  );
  transform: skewX(-25deg);
  animation: shine-sweep 4s infinite ease-in-out;
  pointer-events: none;
}

/* 运行状态 - 绿色脉冲 */
.status-indicator.running {
  background: rgba(74, 157, 110, 0.1);
  color: #4fffa3;
  border: 1px solid rgba(74, 157, 110, 0.6);
  box-shadow: 
    0 0 15px rgba(74, 157, 110, 0.3),
    inset 0 0 20px rgba(74, 157, 110, 0.1);
  text-shadow: 0 0 10px rgba(79, 255, 163, 0.8);
  animation: pulse-green 2s infinite ease-in-out;
}

/* 停止状态 - 红色警示 */
.status-indicator.stopped {
  background: rgba(199, 80, 80, 0.1);
  color: #ff5c5c;
  border: 1px solid rgba(199, 80, 80, 0.6);
  box-shadow: 
    0 0 15px rgba(199, 80, 80, 0.3),
    inset 0 0 20px rgba(199, 80, 80, 0.1);
  text-shadow: 0 0 10px rgba(255, 92, 92, 0.8);
  animation: pulse-red 2s infinite ease-in-out;
}

/* 暂停状态 - 黄色呼吸 */
.status-indicator.paused {
  background: rgba(212, 145, 94, 0.1);
  color: #ffd166;
  border: 1px solid rgba(212, 145, 94, 0.6);
  box-shadow: 
    0 0 15px rgba(212, 145, 94, 0.3),
    inset 0 0 20px rgba(212, 145, 94, 0.1);
  text-shadow: 0 0 10px rgba(255, 209, 102, 0.8);
  animation: pulse-yellow 2s infinite ease-in-out;
}

/* 模式显示 - 科技标签 */
.mode-display {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 14px;
  letter-spacing: 2px;
  margin-bottom: 20px;
  text-transform: uppercase;
}

.mode-display strong {
  color: var(--accent-light);
  font-size: 16px;
  padding: 2px 8px;
  background: rgba(45, 183, 181, 0.15);
  border: 1px solid rgba(45, 183, 181, 0.4);
  border-radius: 4px;
  box-shadow: 0 0 10px rgba(45, 183, 181, 0.2);
}

/* 生产计数器 - 全息能量槽 */
.production-count {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: 
    linear-gradient(180deg, rgba(10, 20, 30, 0.6) 0%, rgba(10, 20, 30, 0.8) 100%),
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(58, 145, 199, 0.05) 2px,
      rgba(58, 145, 199, 0.05) 4px
    );
  border-radius: 4px;
  border: 1px solid rgba(58, 145, 199, 0.3);
  position: relative;
  overflow: hidden;
  box-shadow: inset 0 0 30px rgba(0, 0, 0, 0.5);
}

/* 四角装饰 */
.production-count::after {
  content: '';
  position: absolute;
  inset: 0;
  border: 1px solid transparent;
  background: 
    linear-gradient(135deg, var(--primary-color) 0%, transparent 5%) top left,
    linear-gradient(225deg, var(--primary-color) 0%, transparent 5%) top right,
    linear-gradient(45deg, var(--primary-color) 0%, transparent 5%) bottom left,
    linear-gradient(315deg, var(--primary-color) 0%, transparent 5%) bottom right;
  background-size: 20px 20px;
  background-repeat: no-repeat;
  pointer-events: none;
}

/* 扫描线动画 */
.production-count::before {
  content: '';
  position: absolute;
  top: -50%;
  left: 0;
  width: 100%;
  height: 20%;
  background: linear-gradient(
    180deg,
    transparent,
    rgba(58, 145, 199, 0.2),
    rgba(58, 145, 199, 0.5),
    rgba(58, 145, 199, 0.2),
    transparent
  );
  animation: scan-vertical 3s linear infinite;
  pointer-events: none;
}

.count-value {
  font-size: 56px;
  line-height: 1;
  font-weight: 700;
  color: #fff;
  margin: 8px 0;
  font-family: var(--font-mono);
  letter-spacing: 4px;
  text-shadow: 
    0 0 10px rgba(58, 145, 199, 0.8),
    0 0 20px rgba(58, 145, 199, 0.6),
    0 0 40px rgba(58, 145, 199, 0.4);
  position: relative;
  z-index: 2;
  filter: drop-shadow(0 0 5px rgba(58, 145, 199, 0.5));
}

.count-label {
  color: var(--text-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 4px;
  z-index: 2;
}

.count-unit {
  color: var(--primary-light);
  font-size: 14px;
  position: absolute;
  bottom: 15px;
  right: 15px;
  opacity: 0.8;
  font-family: var(--font-mono);
  border: 1px solid rgba(58, 145, 199, 0.3);
  padding: 2px 6px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.3);
}

/* 动画定义 */
@keyframes shine-sweep {
  0% { left: -150%; opacity: 0; }
  20% { opacity: 1; }
  40% { left: 150%; opacity: 0; }
  100% { left: 150%; opacity: 0; }
}

@keyframes pulse-green {
  0%, 100% { box-shadow: 0 0 15px rgba(74, 157, 110, 0.3), inset 0 0 20px rgba(74, 157, 110, 0.1); border-color: rgba(74, 157, 110, 0.6); }
  50% { box-shadow: 0 0 25px rgba(74, 157, 110, 0.6), inset 0 0 30px rgba(74, 157, 110, 0.3); border-color: rgba(74, 157, 110, 1); }
}

@keyframes pulse-red {
  0%, 100% { box-shadow: 0 0 15px rgba(199, 80, 80, 0.3), inset 0 0 20px rgba(199, 80, 80, 0.1); border-color: rgba(199, 80, 80, 0.6); }
  50% { box-shadow: 0 0 25px rgba(199, 80, 80, 0.6), inset 0 0 30px rgba(199, 80, 80, 0.3); border-color: rgba(199, 80, 80, 1); }
}

@keyframes pulse-yellow {
  0%, 100% { box-shadow: 0 0 15px rgba(212, 145, 94, 0.3), inset 0 0 20px rgba(212, 145, 94, 0.1); border-color: rgba(212, 145, 94, 0.6); }
  50% { box-shadow: 0 0 25px rgba(212, 145, 94, 0.6), inset 0 0 30px rgba(212, 145, 94, 0.3); border-color: rgba(212, 145, 94, 1); }
}

@keyframes scan-vertical {
  0% { top: -20%; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: 120%; opacity: 0; }
}

/* 控制面板 */
.control-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.control-buttons .el-button {
  flex: 1 1 70px;
  min-width: 60px;
  font-weight: 500;
  letter-spacing: 0.5px;
  padding: 6px 10px;
  font-size: 12px;
}

.mode-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.speed-control {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 12px;
}

.speed-control .el-slider {
  flex: 1;
  --el-slider-main-bg-color: var(--primary-color);
  --el-slider-runway-bg-color: rgba(58, 145, 199, 0.2);
}

/* 报警列表 */
.alert-card {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.alert-list {
  flex: 1;
  overflow-y: auto;
  max-height: 150px;
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
  gap: 12px;
  overflow: hidden;
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

/* 图表区域 - 并排布局 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.chart-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chart-card h3 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.chart-switch {
  display: flex;
  gap: 4px;
}

.chart-switch .el-button {
  padding: 4px 8px;
  font-size: 11px;
}

.chart-container {
  flex: 1;
  min-height: 180px;
}

.current-value {
  text-align: center;
  padding: 8px;
  font-size: 13px;
  color: var(--success-color);
  font-family: var(--font-mono);
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}

.current-value strong {
  font-size: 16px;
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
  gap: 12px;
  overflow-y: auto;
  padding-right: 4px;
}

.right-panel::-webkit-scrollbar {
  width: 4px;
}

.right-panel::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 2px;
}

.right-panel::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 2px;
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
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-color);
  max-height: 180px;
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
  padding: 10px;
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
  font-size: 12px;
  margin-bottom: 6px;
  color: var(--text-secondary);
}

.person-count strong {
  font-size: 22px;
  color: var(--primary-color);
  font-family: var(--font-mono);
  font-weight: 600;
}

.zone-status {
  font-size: 12px;
  color: var(--success-color);
}

.detection-status.danger .zone-status {
  color: var(--danger-color);
  font-weight: 600;
}

/* 危险区域统计 */
.zone-statistics {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.zone-stat-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
}

.zone-stat-item.danger-stat {
  background: rgba(199, 80, 80, 0.1);
  border: 1px solid rgba(199, 80, 80, 0.2);
  margin-bottom: 8px;
}

.zone-stat-item .stat-icon {
  font-size: 14px;
}

.zone-stat-item .stat-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.zone-stat-item .stat-value {
  font-size: 16px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--danger-color);
  margin-bottom: 0;
}

.zone-stat-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.zone-stat-row .zone-stat-item {
  flex-direction: column;
  gap: 2px;
}

.zone-stat-row .stat-value {
  font-size: 14px;
}

.zone-stat-row .stat-value.enter {
  color: var(--danger-color);
}

.zone-stat-row .stat-value.exit {
  color: var(--success-color);
}

/* 危险区域操作按钮 */
.zone-actions {
  display: flex;
  gap: 6px;
  justify-content: center;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.zone-actions .el-button {
  font-size: 10px;
  padding: 4px 8px;
}

/* 最后事件时间 */
.zone-last-time {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
}

.zone-last-time small {
  font-size: 9px;
  color: var(--text-muted);
  text-align: center;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.stat-item {
  text-align: center;
  padding: 10px 6px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border: 1px solid var(--border-color);
  transition: border-color var(--transition-fast) ease;
}

.stat-item:hover {
  border-color: var(--border-glow);
}

.stats-card .stat-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: var(--primary-color);
  font-family: var(--font-mono);
  margin-bottom: 2px;
}

.stats-card .stat-value.danger {
  color: var(--danger-color);
}

.stats-card .stat-value.warning {
  color: var(--warning-color);
}

.stats-card .stat-label {
  font-size: 10px;
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
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.led-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.led-item span {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.3px;
}

.led-light {
  width: 16px;
  height: 16px;
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
  margin-bottom: 6px;
  font-size: 11px;
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

/* ========================================
   生产计划卡片
   ======================================== */
.plan-card .plan-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plan-input {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.plan-input span {
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.plan-input .el-input-number {
  width: 100px;
}

.plan-progress {
  padding: 12px;
  background: rgba(58, 145, 199, 0.08);
  border-radius: 6px;
  border: 1px solid rgba(58, 145, 199, 0.15);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.progress-info span:last-child {
  color: var(--primary-color);
  font-weight: 600;
  font-family: var(--font-mono);
}

.progress-detail {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

/* ========================================
   自动调度卡片
   ======================================== */
.schedule-card .schedule-rules {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rule-item {
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
  font-size: 12px;
}

.rule-item:hover {
  border-color: var(--border-glow);
}

.rule-item.disabled {
  opacity: 0.5;
}

.rule-item .el-checkbox {
  --el-checkbox-text-color: var(--text-secondary);
  --el-checkbox-input-border-color: var(--border-color);
}

.rule-item .el-checkbox.is-checked .el-checkbox__inner {
  background: var(--primary-color);
  border-color: var(--primary-color);
}

.schedule-log {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(74, 157, 110, 0.1);
  border-radius: 4px;
  border-left: 3px solid var(--success-color);
  display: flex;
  align-items: center;
  gap: 6px;
}

.schedule-log .log-icon {
  font-size: 12px;
}

.schedule-log .log-text {
  font-size: 11px;
  color: var(--text-secondary);
}

/* Element Plus 输入框样式 */
.el-input-number {
  --el-input-bg-color: rgba(20, 30, 50, 0.9);
  --el-input-border-color: var(--border-color);
  --el-input-text-color: var(--text-primary);
  --el-fill-color-light: rgba(30, 45, 70, 0.9);
}

.el-input-number .el-input__inner {
  background: rgba(20, 30, 50, 0.9) !important;
  border-color: var(--border-color) !important;
  color: #ffffff !important;
}

.el-input-number .el-input-number__decrease,
.el-input-number .el-input-number__increase {
  background: rgba(30, 45, 70, 0.9) !important;
  border-color: var(--border-color) !important;
  color: var(--text-secondary) !important;
}

.el-input-number .el-input-number__decrease:hover,
.el-input-number .el-input-number__increase:hover {
  color: var(--primary-color) !important;
}

/* Switch 样式 */
.el-switch {
  --el-switch-on-color: var(--primary-color);
}

/* ========================================
   检测模式切换
   ======================================== */
.detection-mode-switch {
  margin-bottom: 12px;
  display: flex;
  justify-content: center;
}

.detection-mode-switch .el-radio-group {
  --el-radio-button-checked-bg-color: var(--primary-color);
  --el-radio-button-checked-border-color: var(--primary-color);
}

.detection-mode-switch .el-radio-button__inner {
  background: rgba(255, 255, 255, 0.05);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

.detection-mode-switch .el-radio-button__original-radio:checked + .el-radio-button__inner {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

/* 产品检测状态 */
.product-status {
  background: rgba(58, 145, 199, 0.08) !important;
  border-color: rgba(58, 145, 199, 0.2) !important;
}

.product-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.product-type {
  font-size: 18px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 4px;
}

.product-type.product_a {
  background: rgba(58, 145, 199, 0.2);
  color: #5ba8d9;
}

.product-type.product_b {
  background: rgba(45, 183, 181, 0.2);
  color: #4dcfcd;
}

.product-info {
  font-size: 12px;
  color: var(--text-muted);
}

.no-product {
  color: var(--text-muted);
  font-size: 13px;
}

/* ========================================
   环境阈值配置样式 - 增强版
   ======================================== */
.threshold-card {
  flex-shrink: 0;
}

.threshold-card h3 {
  margin-bottom: 16px;
}

.threshold-card .threshold-settings {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.threshold-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(58, 145, 199, 0.05);
  border-radius: 8px;
  border: 1px solid rgba(58, 145, 199, 0.1);
}

.threshold-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}

.threshold-inputs {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.threshold-separator {
  color: var(--primary-color);
  font-weight: bold;
  font-size: 14px;
  padding: 0 4px;
}

/* 输入框样式增强 */
.threshold-inputs .el-input-number {
  width: 90px;
}

.threshold-inputs .el-input-number .el-input__wrapper {
  background: rgba(10, 20, 35, 0.8) !important;
  border: 1px solid rgba(58, 145, 199, 0.3) !important;
  border-radius: 6px !important;
  box-shadow: none !important;
}

.threshold-inputs .el-input-number .el-input__inner {
  color: var(--text-primary) !important;
  font-family: var(--font-mono);
  font-size: 13px;
}

.threshold-inputs .el-input-number .el-input-number__decrease,
.threshold-inputs .el-input-number .el-input-number__increase {
  background: rgba(58, 145, 199, 0.15) !important;
  border-color: rgba(58, 145, 199, 0.2) !important;
  color: var(--primary-color) !important;
}

.threshold-inputs .el-input-number .el-input-number__decrease:hover,
.threshold-inputs .el-input-number .el-input-number__increase:hover {
  background: rgba(58, 145, 199, 0.3) !important;
  color: var(--primary-light) !important;
}

/* ========================================
   历史数据样式
   ======================================== */
.history-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.history-card h3 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.history-card .history-range {
  margin: 8px 0;
  text-align: center;
}

.history-chart-container {
  flex: 1;
  min-height: 180px;
}

.history-card .el-select {
  --el-select-input-color: var(--text-primary);
  --el-select-border-color: var(--border-color);
}

.history-card .el-radio-group {
  --el-radio-button-checked-bg-color: var(--primary-color);
  --el-radio-button-checked-border-color: var(--primary-color);
}

.history-card .el-radio-button__inner {
  background: rgba(255, 255, 255, 0.05);
  border-color: var(--border-color);
  color: var(--text-secondary);
  padding: 4px 10px;
  font-size: 12px;
}

/* ========================================
   响应式设计
   ======================================== */
@media (max-width: 1400px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
  
  .history-chart-container {
    min-height: 150px;
  }
}

@media (max-width: 1200px) {
  .dashboard .main-content {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    height: auto;
    overflow-y: auto;
  }
  
  .left-panel, .right-panel {
    grid-column: 1;
    overflow-y: visible;
  }
  
  .center-panel {
    grid-column: 1;
    grid-row: 2;
  }
  
  .charts-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
