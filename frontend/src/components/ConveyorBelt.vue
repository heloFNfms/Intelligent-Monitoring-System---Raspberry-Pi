<template>
  <div class="conveyor-container">
    <!-- 粒子背景 -->
    <div class="particles-bg" v-if="isRunning">
      <div class="particle" v-for="n in 20" :key="n" :style="getParticleStyle(n)"></div>
    </div>
    
    <!-- 传送带主体 -->
    <div class="conveyor-belt" :class="{ running: isRunning }">
      <!-- 霓虹边框 -->
      <div class="neon-border" :class="{ active: isRunning }"></div>
      
      <!-- 多层扫描线特效 -->
      <div class="scan-line" v-if="isRunning"></div>
      <div class="scan-line-reverse" v-if="isRunning"></div>
      <div class="hologram-scan" v-if="isRunning"></div>
      
      <!-- 动态网格背景 -->
      <div class="grid-bg" :class="{ animated: isRunning }"></div>
      <div class="data-flow-bg" v-if="isRunning"></div>
      
      <!-- 电弧光效 -->
      <div class="electric-arcs" v-if="isRunning">
        <div class="arc arc-1"></div>
        <div class="arc arc-2"></div>
        <div class="arc arc-3"></div>
      </div>
      
      <!-- 传送带轨道 - 3D透视效果 -->
      <div class="belt-track">
        <div class="belt-surface" :style="beltStyle">
          <!-- 双层能量流动条 -->
          <div class="energy-flow" v-if="isRunning"></div>
          <div class="energy-flow-reverse" v-if="isRunning"></div>
          <div class="energy-pulse" v-if="isRunning"></div>
        </div>
        <!-- 轨道边缘发光 -->
        <div class="track-glow" :class="{ active: isRunning }"></div>
        <div class="track-reflection"></div>
      </div>
      
      <!-- 传送带上的物品 -->
      <div class="items-layer">
        <div 
          v-for="item in items" 
          :key="item.id"
          class="conveyor-item"
          :class="[item.shape, { 'item-new': item.position < 10, 'item-exit': item.position > 90 }]"
          :style="getItemStyle(item)"
        >
          <!-- 物品全息光圈 -->
          <div class="item-hologram" :style="{ borderColor: item.color }"></div>
          <div class="item-glow" :style="{ background: item.color }"></div>
          <div class="item-body" :style="getItemBodyStyle(item)">
            <span class="item-label">{{ item.id }}</span>
            <div class="item-shine"></div>
          </div>
          <!-- 物品能量拖尾 -->
          <div class="item-trail" v-if="isRunning" :style="{ background: `linear-gradient(to left, ${item.color}, transparent)` }"></div>
          <div class="item-trail-glow" v-if="isRunning" :style="{ background: item.color }"></div>
          <!-- 物品数据标签 -->
          <div class="item-data-tag" :style="{ borderColor: item.color }">
            <span class="data-text">ID:{{ item.id }}</span>
          </div>
        </div>
      </div>
      
      <!-- 起点标记 - 增强版 -->
      <div class="endpoint start">
        <div class="endpoint-outer-ring" :class="{ pulse: isRunning }"></div>
        <div class="endpoint-ring" :class="{ pulse: isRunning }"></div>
        <div class="endpoint-core" :class="{ active: isRunning }"></div>
        <div class="endpoint-icon">📥</div>
        <span>入口</span>
        <div class="endpoint-beam" v-if="isRunning"></div>
      </div>
      
      <!-- 终点标记 - 增强版 -->
      <div class="endpoint end">
        <div class="endpoint-outer-ring" :class="{ pulse: isRunning }"></div>
        <div class="endpoint-ring" :class="{ pulse: isRunning }"></div>
        <div class="endpoint-core" :class="{ active: isRunning }"></div>
        <div class="endpoint-icon">📤</div>
        <span>出口</span>
        <div class="endpoint-beam" v-if="isRunning"></div>
      </div>
      
      <!-- 滚轮装饰 - 增强版 -->
      <div class="roller roller-start" :class="{ spinning: isRunning }">
        <div class="roller-ring"></div>
        <div class="roller-light" :class="{ on: isRunning }"></div>
        <div class="roller-spark" v-if="isRunning"></div>
      </div>
      <div class="roller roller-end" :class="{ spinning: isRunning }">
        <div class="roller-ring"></div>
        <div class="roller-light" :class="{ on: isRunning }"></div>
        <div class="roller-spark" v-if="isRunning"></div>
      </div>
      
      <!-- 状态指示灯 - 增强版 -->
      <div class="status-lights">
        <div class="light-container">
          <div class="light" :class="{ on: isRunning, green: isRunning }"></div>
          <div class="light-ring" :class="{ active: isRunning && true }"></div>
        </div>
        <div class="light-container">
          <div class="light" :class="{ on: !isRunning, red: !isRunning }"></div>
          <div class="light-ring" :class="{ active: !isRunning }"></div>
        </div>
      </div>
      
      <!-- 速度仪表 -->
      <div class="speed-gauge">
        <div class="gauge-bg"></div>
        <div class="gauge-fill" :style="{ width: `${speed * 50}%` }"></div>
        <span class="gauge-label">{{ speed.toFixed(1) }}x</span>
      </div>
      
      <!-- 角落装饰 -->
      <div class="corner-decor top-left"></div>
      <div class="corner-decor top-right"></div>
      <div class="corner-decor bottom-left"></div>
      <div class="corner-decor bottom-right"></div>
    </div>
    
    <!-- 状态面板 - 增强版 -->
    <div class="conveyor-status" :class="{ active: isRunning }">
      <div class="status-item">
        <div class="status-icon">⚡</div>
        <span class="status-label">状态</span>
        <span class="status-value" :class="{ active: isRunning }">
          {{ isRunning ? '运行中' : '已停止' }}
        </span>
        <div class="status-bar" :class="{ running: isRunning }"></div>
      </div>
      <div class="status-item">
        <div class="status-icon">🚀</div>
        <span class="status-label">速度</span>
        <span class="status-value speed">{{ speed.toFixed(1) }}x</span>
        <div class="status-bar-speed" :style="{ width: `${speed * 50}%` }"></div>
      </div>
      <div class="status-item">
        <div class="status-icon">✅</div>
        <span class="status-label">完成</span>
        <span class="status-value highlight">{{ completedCount }}</span>
        <div class="counter-glow"></div>
      </div>
      <div class="status-item">
        <div class="status-icon">📦</div>
        <span class="status-label">在线</span>
        <span class="status-value online">{{ items.length }}</span>
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

const getItemBodyStyle = (item) => ({
  background: `linear-gradient(135deg, ${item.color} 0%, ${adjustColor(item.color, -30)} 100%)`,
  boxShadow: `0 0 20px ${item.color}40, inset 0 1px 0 rgba(255,255,255,0.3)`
})

const adjustColor = (color, amount) => {
  const hex = color.replace('#', '')
  const r = Math.min(255, Math.max(0, parseInt(hex.substr(0, 2), 16) + amount))
  const g = Math.min(255, Math.max(0, parseInt(hex.substr(2, 2), 16) + amount))
  const b = Math.min(255, Math.max(0, parseInt(hex.substr(4, 2), 16) + amount))
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

const getParticleStyle = (n) => ({
  left: `${(n * 5) % 100}%`,
  animationDelay: `${(n * 0.2) % 3}s`,
  animationDuration: `${2 + (n % 3)}s`
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
.conveyor-container { 
  width: 100%; 
  padding: 16px; 
  position: relative;
}

/* 粒子背景 */
.particles-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}

.particle {
  position: absolute;
  width: 4px;
  height: 4px;
  background: radial-gradient(circle, #3a91c7 0%, transparent 70%);
  border-radius: 50%;
  animation: particleFloat 3s ease-in-out infinite;
}

@keyframes particleFloat {
  0%, 100% { transform: translateY(100%) scale(0); opacity: 0; }
  20% { opacity: 1; }
  50% { transform: translateY(0) scale(1); opacity: 0.8; }
  80% { opacity: 0.5; }
}

.conveyor-belt {
  position: relative;
  height: 160px;
  background: linear-gradient(180deg, #050810 0%, #0a1018 30%, #0d1520 60%, #111b2a 100%);
  border-radius: 12px;
  border: 1px solid rgba(58, 145, 199, 0.2);
  overflow: hidden;
  box-shadow: 
    0 0 40px rgba(58, 145, 199, 0.1),
    0 0 80px rgba(58, 145, 199, 0.05),
    inset 0 0 100px rgba(0, 0, 0, 0.8);
  z-index: 1;
}

/* 霓虹边框 */
.neon-border {
  position: absolute;
  inset: -2px;
  border-radius: 14px;
  background: linear-gradient(45deg, transparent, transparent);
  opacity: 0;
  transition: all 0.5s ease;
  pointer-events: none;
  z-index: 100;
}

.neon-border.active {
  opacity: 1;
  background: linear-gradient(45deg, 
    #3a91c7 0%, 
    #2db7b5 25%, 
    #3a91c7 50%, 
    #2db7b5 75%, 
    #3a91c7 100%
  );
  background-size: 400% 400%;
  animation: neonFlow 3s linear infinite;
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  padding: 2px;
}

@keyframes neonFlow {
  0% { background-position: 0% 50%; filter: drop-shadow(0 0 10px #3a91c7); }
  50% { background-position: 100% 50%; filter: drop-shadow(0 0 20px #2db7b5); }
  100% { background-position: 0% 50%; filter: drop-shadow(0 0 10px #3a91c7); }
}

/* 角落装饰 */
.corner-decor {
  position: absolute;
  width: 20px;
  height: 20px;
  border: 2px solid rgba(58, 145, 199, 0.4);
  z-index: 50;
}

.corner-decor.top-left { top: 5px; left: 5px; border-right: none; border-bottom: none; }
.corner-decor.top-right { top: 5px; right: 5px; border-left: none; border-bottom: none; }
.corner-decor.bottom-left { bottom: 5px; left: 5px; border-right: none; border-top: none; }
.corner-decor.bottom-right { bottom: 5px; right: 5px; border-left: none; border-top: none; }

/* 动态网格背景 */
.grid-bg {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(rgba(58, 145, 199, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(58, 145, 199, 0.05) 1px, transparent 1px);
  background-size: 25px 25px;
  pointer-events: none;
}

.grid-bg.animated {
  animation: gridScroll 10s linear infinite;
}

@keyframes gridScroll {
  0% { background-position: 0 0; }
  100% { background-position: 25px 25px; }
}

/* 数据流动背景 */
.data-flow-bg {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    90deg,
    transparent 0px,
    transparent 50px,
    rgba(58, 145, 199, 0.02) 50px,
    rgba(58, 145, 199, 0.02) 52px
  );
  animation: dataFlow 2s linear infinite;
  pointer-events: none;
}

@keyframes dataFlow {
  0% { transform: translateX(-52px); }
  100% { transform: translateX(0); }
}

/* 多层扫描线特效 */
.scan-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(58, 145, 199, 0.3) 20%,
    rgba(58, 145, 199, 1) 50%, 
    rgba(58, 145, 199, 0.3) 80%,
    transparent 100%
  );
  box-shadow: 0 0 20px rgba(58, 145, 199, 0.8), 0 0 40px rgba(58, 145, 199, 0.4);
  animation: scan 2.5s linear infinite;
  z-index: 20;
}

.scan-line-reverse {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(45, 183, 181, 0.6), transparent);
  animation: scanReverse 3s linear infinite;
  z-index: 20;
}

@keyframes scanReverse {
  0% { bottom: 100%; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { bottom: 0; opacity: 0; }
}

/* 全息扫描 */
.hologram-scan {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, 
    transparent 0%,
    rgba(58, 145, 199, 0.1) 45%,
    rgba(45, 183, 181, 0.15) 50%,
    rgba(58, 145, 199, 0.1) 55%,
    transparent 100%
  );
  animation: holoScan 4s ease-in-out infinite;
  pointer-events: none;
}

@keyframes holoScan {
  0%, 100% { transform: translateY(-100%); }
  50% { transform: translateY(100%); }
}

@keyframes scan {
  0% { top: -5px; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: 100%; opacity: 0; }
}

/* 电弧光效 */
.electric-arcs {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 15;
}

.arc {
  position: absolute;
  width: 100px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #3a91c7, rgba(58, 145, 199, 0.8), transparent);
  filter: blur(1px);
  opacity: 0;
}

.arc-1 {
  top: 20%;
  left: 10%;
  animation: arcFlash 2s ease-in-out infinite;
}

.arc-2 {
  top: 60%;
  right: 15%;
  width: 80px;
  animation: arcFlash 2.5s ease-in-out infinite 0.5s;
}

.arc-3 {
  bottom: 25%;
  left: 40%;
  width: 60px;
  animation: arcFlash 1.8s ease-in-out infinite 1s;
}

@keyframes arcFlash {
  0%, 90%, 100% { opacity: 0; transform: scaleX(0); }
  5%, 15% { opacity: 0.8; transform: scaleX(1); }
  20% { opacity: 0; transform: scaleX(1); }
}

/* 传送带轨道 - 3D透视效果 */
.belt-track {
  position: absolute;
  top: 50%;
  left: 70px;
  right: 70px;
  height: 50px;
  transform: translateY(-50%) perspective(500px) rotateX(5deg);
  background: linear-gradient(180deg, #1a2535 0%, #151d2a 50%, #121a26 100%);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(58, 145, 199, 0.25);
  box-shadow: 
    0 10px 30px rgba(0, 0, 0, 0.5),
    inset 0 2px 10px rgba(0, 0, 0, 0.5),
    inset 0 -2px 10px rgba(58, 145, 199, 0.1);
}

.track-reflection {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.03) 0%, transparent 100%);
  pointer-events: none;
}

.belt-surface {
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    90deg, 
    #2a3545 0px, #2a3545 16px, 
    #1e2836 16px, #1e2836 18px,
    #303c4f 18px, #303c4f 34px, 
    #1e2836 34px, #1e2836 36px
  );
  transition: background-position 0.05s linear;
  position: relative;
}

/* 双层能量流动条 */
.energy-flow {
  position: absolute;
  top: 35%;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(58, 145, 199, 0.4) 15%, 
    rgba(45, 183, 181, 1) 50%, 
    rgba(58, 145, 199, 0.4) 85%, 
    transparent 100%
  );
  box-shadow: 0 0 15px rgba(45, 183, 181, 0.8);
  animation: flow 1.2s linear infinite;
}

.energy-flow-reverse {
  position: absolute;
  top: 65%;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, 
    transparent 0%, 
    rgba(45, 183, 181, 0.3) 20%, 
    rgba(58, 145, 199, 0.8) 50%, 
    rgba(45, 183, 181, 0.3) 80%, 
    transparent 100%
  );
  animation: flowReverse 1.8s linear infinite;
}

.energy-pulse {
  position: absolute;
  top: 50%;
  left: 0;
  width: 100%;
  height: 100%;
  transform: translateY(-50%);
  background: radial-gradient(ellipse 100px 30px at 50% 50%, rgba(58, 145, 199, 0.3) 0%, transparent 70%);
  animation: pulseMove 2s ease-in-out infinite;
}

@keyframes pulseMove {
  0% { transform: translateY(-50%) translateX(-100%); opacity: 0; }
  20% { opacity: 1; }
  80% { opacity: 1; }
  100% { transform: translateY(-50%) translateX(100%); opacity: 0; }
}

@keyframes flow {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

@keyframes flowReverse {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

/* 轨道边缘发光 */
.track-glow {
  position: absolute;
  inset: -2px;
  border-radius: 10px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.5s ease;
  box-shadow: 
    inset 0 0 20px rgba(58, 145, 199, 0.4),
    0 0 30px rgba(58, 145, 199, 0.3),
    0 0 60px rgba(45, 183, 181, 0.2);
}

.track-glow.active { 
  opacity: 1; 
  animation: glowPulse 2s ease-in-out infinite;
}

@keyframes glowPulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; }
}

/* 物品层 */
.items-layer {
  position: absolute;
  top: 50%;
  left: 70px;
  right: 70px;
  height: 80px;
  transform: translateY(-50%);
  pointer-events: none;
  z-index: 10;
}

/* 物品样式 */
.conveyor-item {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  transition: left 0.05s linear;
}

/* 物品全息光圈 */
.item-hologram {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 60px;
  height: 60px;
  border: 1px dashed;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  animation: holoRotate 3s linear infinite;
  opacity: 0.5;
}

@keyframes holoRotate {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

.item-body {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 
    0 6px 25px rgba(0, 0, 0, 0.6),
    inset 0 2px 0 rgba(255, 255, 255, 0.25),
    inset 0 -3px 8px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  position: relative;
  z-index: 2;
  overflow: hidden;
}

.item-shine {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: linear-gradient(
    45deg,
    transparent 40%,
    rgba(255, 255, 255, 0.3) 50%,
    transparent 60%
  );
  animation: itemShine 2s ease-in-out infinite;
}

@keyframes itemShine {
  0% { transform: translateX(-100%) translateY(-100%); }
  100% { transform: translateX(100%) translateY(100%); }
}

.conveyor-item.cylinder .item-body { border-radius: 50%; }

/* 物品发光效果 */
.item-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  filter: blur(20px);
  opacity: 0.5;
  z-index: 1;
  animation: itemGlowPulse 1.5s ease-in-out infinite;
}

@keyframes itemGlowPulse {
  0%, 100% { opacity: 0.4; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.6; transform: translate(-50%, -50%) scale(1.1); }
}

/* 物品拖尾 */
.item-trail {
  position: absolute;
  top: 50%;
  right: 100%;
  width: 40px;
  height: 6px;
  transform: translateY(-50%);
  opacity: 0.7;
  border-radius: 3px;
  filter: blur(2px);
}

.item-trail-glow {
  position: absolute;
  top: 50%;
  right: 100%;
  width: 20px;
  height: 20px;
  transform: translateY(-50%);
  border-radius: 50%;
  filter: blur(10px);
  opacity: 0.3;
}

/* 物品数据标签 */
.item-data-tag {
  position: absolute;
  top: -25px;
  left: 50%;
  transform: translateX(-50%);
  padding: 2px 6px;
  background: rgba(10, 15, 25, 0.9);
  border: 1px solid;
  border-radius: 4px;
  font-size: 8px;
  white-space: nowrap;
  opacity: 0.8;
}

.data-text {
  color: rgba(255, 255, 255, 0.8);
  font-family: var(--font-mono, monospace);
}

/* 新物品入场动画 */
.item-new .item-body {
  animation: itemEnter 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.item-new .item-glow {
  animation: glowEnter 0.5s ease-out;
}

@keyframes itemEnter {
  0% { transform: scale(0) rotate(-180deg); opacity: 0; }
  60% { transform: scale(1.3) rotate(10deg); }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}

@keyframes glowEnter {
  0% { opacity: 0; transform: translate(-50%, -50%) scale(0); }
  50% { opacity: 1; transform: translate(-50%, -50%) scale(2); }
  100% { opacity: 0.5; transform: translate(-50%, -50%) scale(1); }
}

/* 物品退出动画 */
.item-exit .item-body {
  animation: itemExit 0.3s ease-in forwards;
}

@keyframes itemExit {
  0% { transform: scale(1); opacity: 1; }
  100% { transform: scale(0.5) translateX(20px); opacity: 0; }
}

.item-label {
  font-size: 12px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  font-family: var(--font-mono, monospace);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
  z-index: 5;
}

/* 端点标记 - 增强版 */
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

.endpoint.start { left: 12px; }
.endpoint.end { right: 12px; }

.endpoint-outer-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 55px;
  height: 55px;
  border: 1px dashed rgba(58, 145, 199, 0.3);
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.endpoint-outer-ring.pulse {
  animation: outerRingPulse 3s ease-out infinite;
}

@keyframes outerRingPulse {
  0% { transform: translate(-50%, -50%) scale(1) rotate(0deg); opacity: 0.5; }
  100% { transform: translate(-50%, -50%) scale(2) rotate(90deg); opacity: 0; }
}

.endpoint-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 45px;
  height: 45px;
  border: 2px solid rgba(58, 145, 199, 0.4);
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.endpoint-ring.pulse {
  animation: ringPulse 2s ease-out infinite;
}

@keyframes ringPulse {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
  100% { transform: translate(-50%, -50%) scale(1.6); opacity: 0; }
}

.endpoint-core {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 30px;
  height: 30px;
  background: radial-gradient(circle, rgba(58, 145, 199, 0.2) 0%, transparent 70%);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: all 0.3s ease;
}

.endpoint-core.active {
  background: radial-gradient(circle, rgba(58, 145, 199, 0.5) 0%, rgba(45, 183, 181, 0.2) 50%, transparent 70%);
  animation: corePulse 1.5s ease-in-out infinite;
}

@keyframes corePulse {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
  50% { transform: translate(-50%, -50%) scale(1.2); opacity: 1; }
}

.endpoint-icon { 
  font-size: 24px; 
  filter: drop-shadow(0 2px 10px rgba(0, 0, 0, 0.5)) drop-shadow(0 0 10px rgba(58, 145, 199, 0.3));
  position: relative;
  z-index: 2;
  animation: iconFloat 2s ease-in-out infinite;
}

@keyframes iconFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

.endpoint span { 
  font-size: 10px; 
  color: rgba(255, 255, 255, 0.6); 
  letter-spacing: 2px;
  text-transform: uppercase;
  text-shadow: 0 0 10px rgba(58, 145, 199, 0.5);
}

.endpoint-beam {
  position: absolute;
  top: 100%;
  left: 50%;
  width: 2px;
  height: 30px;
  background: linear-gradient(180deg, rgba(58, 145, 199, 0.6), transparent);
  transform: translateX(-50%);
  animation: beamPulse 1s ease-in-out infinite;
}

@keyframes beamPulse {
  0%, 100% { opacity: 0.5; height: 30px; }
  50% { opacity: 1; height: 40px; }
}

/* 滚轮 - 增强版 */
.roller {
  position: absolute;
  top: 50%;
  width: 32px;
  height: 60px;
  background: linear-gradient(90deg, #2a3545 0%, #3a4858 30%, #4a5868 50%, #3a4858 70%, #2a3545 100%);
  border-radius: 8px;
  transform: translateY(-50%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 
    0 6px 15px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.roller-start { left: 52px; }
.roller-end { right: 52px; }

.roller-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 18px;
  height: 18px;
  border: 3px solid #4a5868;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, #3a4858 0%, #1a2535 100%);
}

.roller.spinning .roller-ring { 
  animation: spin 0.3s linear infinite;
  border-color: #5a9fcf;
  box-shadow: 0 0 10px rgba(90, 159, 207, 0.5);
}

@keyframes spin {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 滚轮火花 */
.roller-spark {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 30px;
  height: 30px;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(90, 159, 207, 0.6) 0%, transparent 60%);
  border-radius: 50%;
  animation: sparkPulse 0.5s ease-out infinite;
}

@keyframes sparkPulse {
  0% { transform: translate(-50%, -50%) scale(0.5); opacity: 1; }
  100% { transform: translate(-50%, -50%) scale(1.5); opacity: 0; }
}

/* 滚轮指示灯 */
.roller-light {
  position: absolute;
  bottom: 8px;
  left: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  transform: translateX(-50%);
  background: #333;
  transition: all 0.3s ease;
}

.roller-light.on {
  background: #4aff9d;
  box-shadow: 0 0 12px #4aff9d, 0 0 24px rgba(74, 255, 157, 0.5);
}

/* 状态指示灯 - 增强版 */
.status-lights {
  position: absolute;
  top: 12px;
  right: 15px;
  display: flex;
  gap: 12px;
}

.light-container {
  position: relative;
}

.light {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #222;
  transition: all 0.3s ease;
  position: relative;
  z-index: 2;
}

.light-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.light-ring.active {
  animation: lightRingPulse 1s ease-out infinite;
}

@keyframes lightRingPulse {
  0% { transform: translate(-50%, -50%) scale(0.5); opacity: 0.8; }
  100% { transform: translate(-50%, -50%) scale(2); opacity: 0; }
}

.light.on.green {
  background: radial-gradient(circle, #6aff9d 0%, #4aff7a 50%, #3ad968 100%);
  box-shadow: 0 0 15px #4aff9d, 0 0 30px rgba(74, 255, 157, 0.5);
}

.light.on.green + .light-ring {
  background: rgba(74, 255, 157, 0.3);
}

.light.on.red {
  background: radial-gradient(circle, #ff6a6a 0%, #ff4a4a 50%, #d93a3a 100%);
  box-shadow: 0 0 15px #ff6a6a, 0 0 30px rgba(255, 74, 74, 0.5);
}

.light.on.red + .light-ring {
  background: rgba(255, 74, 74, 0.3);
}

/* 速度仪表 */
.speed-gauge {
  position: absolute;
  top: 12px;
  left: 15px;
  width: 80px;
  height: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.gauge-bg {
  position: absolute;
  width: 50px;
  height: 6px;
  background: rgba(20, 30, 40, 0.8);
  border-radius: 3px;
  border: 1px solid rgba(58, 145, 199, 0.2);
  overflow: hidden;
}

.gauge-fill {
  position: absolute;
  height: 6px;
  background: linear-gradient(90deg, #3a91c7, #2db7b5);
  border-radius: 3px;
  transition: width 0.3s ease;
  box-shadow: 0 0 10px rgba(58, 145, 199, 0.5);
}

.gauge-label {
  position: absolute;
  left: 55px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.7);
  font-family: var(--font-mono, monospace);
}

/* 运行时整体发光 */
.conveyor-belt.running {
  border-color: rgba(58, 145, 199, 0.5);
  box-shadow: 
    0 0 50px rgba(58, 145, 199, 0.2),
    0 0 100px rgba(45, 183, 181, 0.1),
    inset 0 0 100px rgba(0, 0, 0, 0.8);
}

/* 状态面板 - 增强版 */
.conveyor-status {
  display: flex;
  justify-content: space-around;
  margin-top: 14px;
  padding: 16px 20px;
  background: linear-gradient(180deg, rgba(10, 15, 25, 0.7) 0%, rgba(15, 22, 35, 0.8) 100%);
  border-radius: 10px;
  border: 1px solid rgba(58, 145, 199, 0.15);
  backdrop-filter: blur(10px);
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

.conveyor-status.active {
  border-color: rgba(58, 145, 199, 0.3);
  box-shadow: 0 0 30px rgba(58, 145, 199, 0.1);
}

.conveyor-status::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(58, 145, 199, 0.05), transparent);
  animation: statusShine 3s ease-in-out infinite;
}

@keyframes statusShine {
  0% { left: -100%; }
  100% { left: 100%; }
}

.status-item { 
  display: flex; 
  flex-direction: column; 
  align-items: center; 
  gap: 6px; 
  position: relative;
  padding: 0 15px;
}

.status-icon {
  font-size: 16px;
  filter: drop-shadow(0 0 5px rgba(255, 255, 255, 0.3));
}

.status-label { 
  font-size: 10px; 
  color: rgba(255, 255, 255, 0.4); 
  text-transform: uppercase; 
  letter-spacing: 1.5px; 
}

.status-value { 
  font-size: 16px; 
  font-weight: 600; 
  color: rgba(255, 255, 255, 0.75); 
  font-family: var(--font-mono, monospace); 
  transition: all 0.3s ease;
}

.status-value.active { 
  color: #4aff9d; 
  text-shadow: 0 0 15px rgba(74, 255, 157, 0.6); 
}

.status-value.speed {
  color: #3a91c7;
}

.status-value.highlight { 
  color: #2db7b5; 
  text-shadow: 0 0 15px rgba(45, 183, 181, 0.6); 
  font-size: 18px;
}

.status-value.online {
  color: #f0a030;
}

.status-bar {
  width: 50px;
  height: 3px;
  background: rgba(50, 50, 50, 0.5);
  border-radius: 2px;
  overflow: hidden;
  position: relative;
}

.status-bar.running::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 100%;
  background: linear-gradient(90deg, #4aff9d, #2db7b5);
  animation: statusBarPulse 1s ease-in-out infinite;
}

@keyframes statusBarPulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.status-bar-speed {
  height: 3px;
  background: linear-gradient(90deg, #3a91c7, #2db7b5);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.counter-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 60px;
  height: 60px;
  background: radial-gradient(circle, rgba(45, 183, 181, 0.1) 0%, transparent 70%);
  transform: translate(-50%, -50%);
  animation: counterGlow 2s ease-in-out infinite;
}

@keyframes counterGlow {
  0%, 100% { opacity: 0.3; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.6; transform: translate(-50%, -50%) scale(1.2); }
}
</style>
