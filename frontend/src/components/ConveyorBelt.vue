<template>
  <div class="conveyor-container">
    <!-- 传送带主体 -->
    <div class="conveyor-belt" :class="{ running: isRunning }">
      <!-- 扫描线特效 -->
      <div class="scan-line" v-if="isRunning"></div>
      
      <!-- 网格背景 -->
      <div class="grid-bg"></div>
      
      <!-- 传送带轨道 -->
      <div class="belt-track">
        <div class="belt-surface" :style="beltStyle">
          <!-- 能量流动条 -->
          <div class="energy-flow" v-if="isRunning"></div>
        </div>
        <!-- 轨道边缘发光 -->
        <div class="track-glow" :class="{ active: isRunning }"></div>
      </div>
      
      <!-- 传送带上的物品 -->
      <div class="items-layer">
        <div 
          v-for="item in items" 
          :key="item.id"
          class="conveyor-item"
          :class="[item.shape, { 'item-new': item.position < 10 }]"
          :style="getItemStyle(item)"
        >
          <div class="item-glow" :style="{ background: item.color }"></div>
          <div class="item-body" :style="{ background: item.color }">
            <span class="item-label">{{ item.id }}</span>
          </div>
          <!-- 物品拖尾 -->
          <div class="item-trail" v-if="isRunning" :style="{ background: `linear-gradient(to left, ${item.color}, transparent)` }"></div>
        </div>
      </div>
      
      <!-- 起点标记 -->
      <div class="endpoint start">
        <div class="endpoint-ring" :class="{ pulse: isRunning }"></div>
        <div class="endpoint-icon">📥</div>
        <span>入口</span>
      </div>
      
      <!-- 终点标记 -->
      <div class="endpoint end">
        <div class="endpoint-ring" :class="{ pulse: isRunning }"></div>
        <div class="endpoint-icon">📤</div>
        <span>出口</span>
      </div>
      
      <!-- 滚轮装饰 -->
      <div class="roller roller-start" :class="{ spinning: isRunning }">
        <div class="roller-light" :class="{ on: isRunning }"></div>
      </div>
      <div class="roller roller-end" :class="{ spinning: isRunning }">
        <div class="roller-light" :class="{ on: isRunning }"></div>
      </div>
      
      <!-- 状态指示灯 -->
      <div class="status-lights">
        <div class="light" :class="{ on: isRunning, green: isRunning }"></div>
        <div class="light" :class="{ on: !isRunning, red: !isRunning }"></div>
      </div>
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

const isRunning = ref(false)
const speed = ref(1.0)
const items = ref([])
const completedCount = ref(0)

let beltOffset = ref(0)
let animationFrame = null

const beltStyle = computed(() => ({
  backgroundPosition: `${beltOffset.value}px 0`
}))

const getItemStyle = (item) => ({
  left: `${item.position}%`,
  transform: `translateX(-50%)`
})

const updateState = (state) => {
  if (state) {
    isRunning.value = state.is_running || false
    speed.value = state.speed || 1.0
    items.value = state.items || []
    completedCount.value = state.completed_count || 0
  }
}

const animateBelt = () => {
  if (isRunning.value) {
    beltOffset.value -= speed.value * 2
    if (beltOffset.value <= -40) beltOffset.value = 0
  }
  animationFrame = requestAnimationFrame(animateBelt)
}

defineExpose({ updateState })

onMounted(() => animateBelt())
onUnmounted(() => { if (animationFrame) cancelAnimationFrame(animationFrame) })
</script>

<style scoped>
.conveyor-container { width: 100%; padding: 16px; }

.conveyor-belt {
  position: relative;
  height: 140px;
  background: linear-gradient(180deg, #080c14 0%, #0d1520 50%, #111b2a 100%);
  border-radius: 8px;
  border: 1px solid rgba(58, 145, 199, 0.25);
  overflow: hidden;
  box-shadow: 
    0 0 30px rgba(58, 145, 199, 0.1),
    inset 0 0 60px rgba(0, 0, 0, 0.5);
}

/* 网格背景 */
.grid-bg {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(rgba(58, 145, 199, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(58, 145, 199, 0.03) 1px, transparent 1px);
  background-size: 20px 20px;
  pointer-events: none;
}

/* 扫描线特效 */
.scan-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(58, 145, 199, 0.8), transparent);
  animation: scan 2s linear infinite;
  z-index: 20;
}

@keyframes scan {
  0% { top: 0; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: 100%; opacity: 0; }
}

/* 传送带轨道 */
.belt-track {
  position: absolute;
  top: 50%;
  left: 70px;
  right: 70px;
  height: 44px;
  transform: translateY(-50%);
  background: linear-gradient(180deg, #1a2535 0%, #151d2a 100%);
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid rgba(58, 145, 199, 0.2);
}

.belt-surface {
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    90deg, 
    #252f3f 0px, #252f3f 18px, 
    #1e2836 18px, #1e2836 20px,
    #252f3f 20px, #252f3f 38px, 
    #1e2836 38px, #1e2836 40px
  );
  transition: background-position 0.05s linear;
  position: relative;
}

/* 能量流动条 */
.energy-flow {
  position: absolute;
  top: 50%;
  left: 0;
  width: 100%;
  height: 2px;
  transform: translateY(-50%);
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(58, 145, 199, 0.6) 20%, 
    rgba(45, 183, 181, 0.8) 50%, 
    rgba(58, 145, 199, 0.6) 80%, 
    transparent 100%
  );
  animation: flow 1.5s linear infinite;
}

@keyframes flow {
  0% { transform: translateY(-50%) translateX(-100%); }
  100% { transform: translateY(-50%) translateX(100%); }
}

/* 轨道边缘发光 */
.track-glow {
  position: absolute;
  inset: -1px;
  border-radius: 6px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s ease;
  box-shadow: 
    inset 0 0 10px rgba(58, 145, 199, 0.3),
    0 0 15px rgba(58, 145, 199, 0.2);
}

.track-glow.active { opacity: 1; }

/* 物品层 */
.items-layer {
  position: absolute;
  top: 50%;
  left: 70px;
  right: 70px;
  height: 70px;
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
  width: 40px;
  height: 40px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 
    0 4px 15px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    inset 0 -2px 5px rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.15);
  position: relative;
  z-index: 2;
}

.conveyor-item.cylinder .item-body { border-radius: 50%; }

/* 物品发光效果 */
.item-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  filter: blur(15px);
  opacity: 0.4;
  z-index: 1;
}

/* 物品拖尾 */
.item-trail {
  position: absolute;
  top: 50%;
  right: 100%;
  width: 30px;
  height: 4px;
  transform: translateY(-50%);
  opacity: 0.6;
  border-radius: 2px;
}

/* 新物品入场动画 */
.item-new .item-body {
  animation: itemEnter 0.3s ease-out;
}

@keyframes itemEnter {
  0% { transform: scale(0); opacity: 0; }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); opacity: 1; }
}

.item-label {
  font-size: 11px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  font-family: var(--font-mono, monospace);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

/* 端点标记 */
.endpoint {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  z-index: 10;
}

.endpoint.start { left: 15px; }
.endpoint.end { right: 15px; }

.endpoint-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 40px;
  height: 40px;
  border: 2px solid rgba(58, 145, 199, 0.3);
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.endpoint-ring.pulse {
  animation: ringPulse 2s ease-out infinite;
}

@keyframes ringPulse {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
  100% { transform: translate(-50%, -50%) scale(1.8); opacity: 0; }
}

.endpoint-icon { 
  font-size: 22px; 
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.5));
  position: relative;
  z-index: 2;
}

.endpoint span { 
  font-size: 10px; 
  color: rgba(255, 255, 255, 0.5); 
  letter-spacing: 1px;
  text-transform: uppercase;
}

/* 滚轮 */
.roller {
  position: absolute;
  top: 50%;
  width: 28px;
  height: 56px;
  background: linear-gradient(90deg, #2a3545 0%, #3a4858 50%, #2a3545 100%);
  border-radius: 6px;
  transform: translateY(-50%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
}

.roller-start { left: 55px; }
.roller-end { right: 55px; }

.roller::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 12px;
  height: 12px;
  background: radial-gradient(circle, #3a4858 0%, #1a2535 100%);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  border: 2px solid #4a5868;
}

.roller.spinning::before { 
  animation: spin 0.4s linear infinite;
  border-color: #5a9fcf;
}

@keyframes spin {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 滚轮指示灯 */
.roller-light {
  position: absolute;
  bottom: 6px;
  left: 50%;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  transform: translateX(-50%);
  background: #333;
  transition: all 0.3s ease;
}

.roller-light.on {
  background: #4a9d6e;
  box-shadow: 0 0 8px #4a9d6e;
}

/* 状态指示灯 */
.status-lights {
  position: absolute;
  top: 10px;
  right: 15px;
  display: flex;
  gap: 8px;
}

.light {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #222;
  transition: all 0.3s ease;
}

.light.on.green {
  background: #4a9d6e;
  box-shadow: 0 0 10px #4a9d6e;
}

.light.on.red {
  background: #c75050;
  box-shadow: 0 0 10px #c75050;
}

/* 运行时整体发光 */
.conveyor-belt.running {
  border-color: rgba(58, 145, 199, 0.4);
  box-shadow: 
    0 0 40px rgba(58, 145, 199, 0.15),
    inset 0 0 60px rgba(0, 0, 0, 0.5);
}

/* 状态面板 */
.conveyor-status {
  display: flex;
  justify-content: space-around;
  margin-top: 12px;
  padding: 14px;
  background: rgba(10, 15, 25, 0.6);
  border-radius: 6px;
  border: 1px solid rgba(58, 145, 199, 0.15);
  backdrop-filter: blur(5px);
}

.status-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.status-label { font-size: 10px; color: rgba(255, 255, 255, 0.4); text-transform: uppercase; letter-spacing: 1px; }
.status-value { font-size: 15px; font-weight: 600; color: rgba(255, 255, 255, 0.7); font-family: var(--font-mono, monospace); }
.status-value.active { color: #4a9d6e; text-shadow: 0 0 10px rgba(74, 157, 110, 0.5); }
.status-value.highlight { color: #3a91c7; text-shadow: 0 0 10px rgba(58, 145, 199, 0.5); }
</style>
