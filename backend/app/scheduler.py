"""
自动调度管理器 - 管理生产线的自动调度规则和生产计划

核心逻辑：
1. 环境超限自动暂停：当温度/湿度/压力超出阈值范围时，自动暂停生产线
2. 环境恢复自动启动：只有当生产线是因为环境异常被自动暂停时，恢复正常后才自动启动
3. 产量达标自动停止：达到目标产量后自动停止

关键状态：
- paused_by_scheduler: 记录是否是调度器自动暂停的（用于判断是否需要自动恢复）
- status_before_pause: 记录暂停前的状态（用于恢复时判断）
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, List
from datetime import datetime, timedelta
import asyncio
import time


@dataclass
class ScheduleRule:
    """调度规则"""
    id: str
    name: str
    enabled: bool = True
    rule_type: str = "temperature"  # temperature / humidity / pressure / production / all_normal_recover
    condition: str = "out_of_range"  # out_of_range / gt / lt / gte / all_normal
    threshold_min: float = 0  # 最小阈值
    threshold_max: float = 100  # 最大阈值
    action: str = "pause"  # pause / stop / start / switch_mode
    action_params: Dict = field(default_factory=dict)
    cooldown: float = 10.0  # 冷却时间（秒）
    last_triggered: float = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "rule_type": self.rule_type,
            "condition": self.condition,
            "threshold_min": self.threshold_min,
            "threshold_max": self.threshold_max,
            "action": self.action,
            "action_params": self.action_params,
            "cooldown": self.cooldown
        }


@dataclass
class ProductionPlan:
    """生产计划"""
    device_id: str
    target_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    auto_stop_on_complete: bool = True
    auto_switch_mode: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "target_count": self.target_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "auto_stop_on_complete": self.auto_stop_on_complete,
            "auto_switch_mode": self.auto_switch_mode
        }


class SchedulerManager:
    """
    调度管理器
    
    核心逻辑：
    1. 当任何环境参数超出阈值范围时，自动暂停生产线
    2. 只有当生产线是被调度器自动暂停的，且所有参数恢复正常后，才自动启动
    3. 如果用户手动停止/暂停，不会自动启动
    """
    
    def __init__(self):
        # 调度规则（按设备ID管理）
        self.rules: Dict[str, List[ScheduleRule]] = {}
        
        # 生产计划
        self.plans: Dict[str, ProductionPlan] = {}
        
        # 环境阈值配置
        self.thresholds: Dict[str, Dict] = {}
        
        # ========== 关键状态 ==========
        # 是否是调度器自动暂停的（只有这种情况才会自动恢复）
        self.paused_by_scheduler: Dict[str, bool] = {}
        
        # 暂停原因（用于显示和判断）
        self.pause_reasons: Dict[str, List[str]] = {}
        
        # 当前各参数是否超限
        self.temp_out_of_range: Dict[str, bool] = {}
        self.humidity_out_of_range: Dict[str, bool] = {}
        self.pressure_out_of_range: Dict[str, bool] = {}
        
        # 传感器历史（用于判断是否稳定恢复）
        self.temp_history: Dict[str, List[float]] = {}
        self.humidity_history: Dict[str, List[float]] = {}
        self.pressure_history: Dict[str, List[float]] = {}
        
        # 动作回调
        self.action_callback: Optional[Callable] = None
        
        # 上次检查时间（用于冷却）
        self.last_check_time: Dict[str, float] = {}
        
        print("✓ 调度管理器初始化完成")
    
    def init_device(self, device_id: str):
        """初始化设备"""
        if device_id in self.rules:
            return
        
        # 初始化规则
        self.rules[device_id] = [
            ScheduleRule(
                id="temp_danger_pause",
                name="温度超限自动停止",
                enabled=True,
                rule_type="temperature",
                condition="out_of_range",
                threshold_min=10.0,
                threshold_max=35.0,
                action="pause",
                cooldown=10.0
            ),
            ScheduleRule(
                id="humidity_danger_pause",
                name="湿度超限自动停止",
                enabled=True,
                rule_type="humidity",
                condition="out_of_range",
                threshold_min=20.0,
                threshold_max=80.0,
                action="pause",
                cooldown=10.0
            ),
            ScheduleRule(
                id="pressure_danger_pause",
                name="压力超限自动停止",
                enabled=True,
                rule_type="pressure",
                condition="out_of_range",
                threshold_min=90.0,
                threshold_max=110.0,
                action="pause",
                cooldown=10.0
            ),
            ScheduleRule(
                id="production_complete",
                name="产量达标自动停止",
                enabled=True,
                rule_type="production",
                condition="gte",
                threshold_min=0,
                threshold_max=0,
                action="stop",
                cooldown=5.0
            ),
            ScheduleRule(
                id="all_normal_start",
                name="全部正常自动启动",
                enabled=True,
                rule_type="all_normal_recover",
                condition="all_normal",
                threshold_min=0,
                threshold_max=0,
                action="start",
                cooldown=10.0
            )
        ]
        
        # 初始化状态
        self.paused_by_scheduler[device_id] = False
        self.pause_reasons[device_id] = []
        self.temp_out_of_range[device_id] = False
        self.humidity_out_of_range[device_id] = False
        self.pressure_out_of_range[device_id] = False
        self.temp_history[device_id] = []
        self.humidity_history[device_id] = []
        self.pressure_history[device_id] = []
        self.last_check_time[device_id] = 0
        
        # 默认阈值
        self.thresholds[device_id] = {
            "tempMin": 10.0,
            "tempMax": 35.0,
            "humidityMin": 20.0,
            "humidityMax": 80.0,
            "pressureMin": 90.0,
            "pressureMax": 110.0
        }
        
        print(f"📋 设备 {device_id} 调度规则已初始化")
    
    def update_thresholds(self, device_id: str, thresholds: Dict):
        """更新阈值配置"""
        self.init_device(device_id)
        self.thresholds[device_id] = thresholds
        
        # 同步更新规则中的阈值
        for rule in self.rules[device_id]:
            if rule.id == "temp_danger_pause":
                rule.threshold_min = thresholds.get("tempMin", 10.0)
                rule.threshold_max = thresholds.get("tempMax", 35.0)
            elif rule.id == "humidity_danger_pause":
                rule.threshold_min = thresholds.get("humidityMin", 20.0)
                rule.threshold_max = thresholds.get("humidityMax", 80.0)
            elif rule.id == "pressure_danger_pause":
                rule.threshold_min = thresholds.get("pressureMin", 90.0)
                rule.threshold_max = thresholds.get("pressureMax", 110.0)
        
        print(f"📊 设备 {device_id} 阈值已更新: {thresholds}")
    
    def set_action_callback(self, callback: Callable):
        """设置动作回调"""
        self.action_callback = callback
    
    def clear_scheduler_pause(self, device_id: str):
        """
        清除调度器暂停状态（当用户手动操作时调用）
        这样可以防止用户手动停止后，系统又自动启动
        """
        self.init_device(device_id)
        self.paused_by_scheduler[device_id] = False
        self.pause_reasons[device_id] = []
        print(f"🔄 设备 {device_id} 调度器暂停状态已清除")
    
    def _is_out_of_range(self, value: float, min_val: float, max_val: float) -> bool:
        """检查值是否超出范围"""
        return value < min_val or value > max_val
    
    def _add_history(self, history_list: List[float], value: float, max_len: int = 5):
        """添加历史记录"""
        history_list.append(value)
        if len(history_list) > max_len:
            history_list.pop(0)
    
    def _is_stable_normal(self, history: List[float], min_val: float, max_val: float, required_count: int = 3) -> bool:
        """检查是否稳定正常（连续N次都在正常范围内）"""
        if len(history) < required_count:
            return False
        recent = history[-required_count:]
        return all(min_val <= v <= max_val for v in recent)
    
    async def check_temperature(self, device_id: str, temperature: float) -> Optional[Dict]:
        """检查温度"""
        self.init_device(device_id)
        
        # 记录历史
        self._add_history(self.temp_history[device_id], temperature)
        
        # 获取阈值
        thresholds = self.thresholds[device_id]
        temp_min = thresholds.get("tempMin", 10.0)
        temp_max = thresholds.get("tempMax", 35.0)
        
        # 检查是否超限
        is_out = self._is_out_of_range(temperature, temp_min, temp_max)
        was_out = self.temp_out_of_range[device_id]
        self.temp_out_of_range[device_id] = is_out
        
        # 获取规则
        rule = self._get_rule(device_id, "temp_danger_pause")
        if not rule or not rule.enabled:
            return await self._check_all_normal(device_id)
        
        # 检查冷却时间
        current_time = time.time()
        if current_time - rule.last_triggered < rule.cooldown:
            return await self._check_all_normal(device_id)
        
        # 如果刚刚超限，触发暂停
        if is_out and not was_out:
            rule.last_triggered = current_time
            reason = f"温度 {temperature}°C 超出范围 [{temp_min}, {temp_max}]°C"
            return await self._trigger_pause(device_id, rule, reason, "temperature")
        
        return await self._check_all_normal(device_id)
    
    async def check_humidity(self, device_id: str, humidity: float) -> Optional[Dict]:
        """检查湿度"""
        self.init_device(device_id)
        
        # 记录历史
        self._add_history(self.humidity_history[device_id], humidity)
        
        # 获取阈值
        thresholds = self.thresholds[device_id]
        humidity_min = thresholds.get("humidityMin", 20.0)
        humidity_max = thresholds.get("humidityMax", 80.0)
        
        # 检查是否超限
        is_out = self._is_out_of_range(humidity, humidity_min, humidity_max)
        was_out = self.humidity_out_of_range[device_id]
        self.humidity_out_of_range[device_id] = is_out
        
        # 获取规则
        rule = self._get_rule(device_id, "humidity_danger_pause")
        if not rule or not rule.enabled:
            return await self._check_all_normal(device_id)
        
        # 检查冷却时间
        current_time = time.time()
        if current_time - rule.last_triggered < rule.cooldown:
            return await self._check_all_normal(device_id)
        
        # 如果刚刚超限，触发暂停
        if is_out and not was_out:
            rule.last_triggered = current_time
            reason = f"湿度 {humidity}% 超出范围 [{humidity_min}, {humidity_max}]%"
            return await self._trigger_pause(device_id, rule, reason, "humidity")
        
        return await self._check_all_normal(device_id)
    
    async def check_pressure(self, device_id: str, pressure: float) -> Optional[Dict]:
        """检查压力"""
        self.init_device(device_id)
        
        # 记录历史
        self._add_history(self.pressure_history[device_id], pressure)
        
        # 获取阈值
        thresholds = self.thresholds[device_id]
        pressure_min = thresholds.get("pressureMin", 90.0)
        pressure_max = thresholds.get("pressureMax", 110.0)
        
        # 检查是否超限
        is_out = self._is_out_of_range(pressure, pressure_min, pressure_max)
        was_out = self.pressure_out_of_range[device_id]
        self.pressure_out_of_range[device_id] = is_out
        
        # 获取规则
        rule = self._get_rule(device_id, "pressure_danger_pause")
        if not rule or not rule.enabled:
            return await self._check_all_normal(device_id)
        
        # 检查冷却时间
        current_time = time.time()
        if current_time - rule.last_triggered < rule.cooldown:
            return await self._check_all_normal(device_id)
        
        # 如果刚刚超限，触发暂停
        if is_out and not was_out:
            rule.last_triggered = current_time
            reason = f"压力 {pressure}kPa 超出范围 [{pressure_min}, {pressure_max}]kPa"
            return await self._trigger_pause(device_id, rule, reason, "pressure")
        
        return await self._check_all_normal(device_id)
    
    async def _trigger_pause(self, device_id: str, rule: ScheduleRule, reason: str, param_type: str) -> Optional[Dict]:
        """触发暂停"""
        # 记录暂停原因
        if reason not in self.pause_reasons[device_id]:
            self.pause_reasons[device_id].append(reason)
        
        # 标记为调度器暂停
        self.paused_by_scheduler[device_id] = True
        
        action = {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "action": rule.action,
            "params": rule.action_params,
            "reason": reason,
            "param_type": param_type
        }
        
        print(f"🔔 调度触发暂停: {rule.name} | {reason}")
        
        if self.action_callback:
            await self.action_callback(device_id, action)
        
        return action
    
    async def _check_all_normal(self, device_id: str) -> Optional[Dict]:
        """检查是否所有参数都恢复正常，可以自动启动"""
        # 只有当是调度器暂停的才考虑自动恢复
        if not self.paused_by_scheduler.get(device_id, False):
            return None
        
        # 获取规则
        rule = self._get_rule(device_id, "all_normal_start")
        if not rule or not rule.enabled:
            return None
        
        # 检查冷却时间
        current_time = time.time()
        if current_time - rule.last_triggered < rule.cooldown:
            return None
        
        # 检查当前是否有任何参数超限
        any_out_of_range = (
            self.temp_out_of_range.get(device_id, False) or
            self.humidity_out_of_range.get(device_id, False) or
            self.pressure_out_of_range.get(device_id, False)
        )
        
        if any_out_of_range:
            return None
        
        # 检查是否稳定正常（需要连续3次正常数据）
        thresholds = self.thresholds[device_id]
        
        temp_stable = self._is_stable_normal(
            self.temp_history.get(device_id, []),
            thresholds.get("tempMin", 10.0),
            thresholds.get("tempMax", 35.0)
        )
        
        humidity_stable = self._is_stable_normal(
            self.humidity_history.get(device_id, []),
            thresholds.get("humidityMin", 20.0),
            thresholds.get("humidityMax", 80.0)
        )
        
        pressure_stable = self._is_stable_normal(
            self.pressure_history.get(device_id, []),
            thresholds.get("pressureMin", 90.0),
            thresholds.get("pressureMax", 110.0)
        )
        
        # 如果某个参数没有历史数据，认为是正常的
        if len(self.temp_history.get(device_id, [])) == 0:
            temp_stable = True
        if len(self.humidity_history.get(device_id, [])) == 0:
            humidity_stable = True
        if len(self.pressure_history.get(device_id, [])) == 0:
            pressure_stable = True
        
        # 所有参数都稳定正常才能恢复
        if not (temp_stable and humidity_stable and pressure_stable):
            return None
        
        # 触发自动启动
        rule.last_triggered = current_time
        
        # 清除暂停状态
        self.paused_by_scheduler[device_id] = False
        self.pause_reasons[device_id] = []
        
        action = {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "action": rule.action,
            "params": rule.action_params,
            "reason": "所有环境参数恢复正常"
        }
        
        print(f"🔔 调度触发启动: {rule.name} | {action['reason']}")
        
        if self.action_callback:
            await self.action_callback(device_id, action)
        
        return action
    
    def _get_rule(self, device_id: str, rule_id: str) -> Optional[ScheduleRule]:
        """获取指定规则"""
        for rule in self.rules.get(device_id, []):
            if rule.id == rule_id:
                return rule
        return None
    
    async def check_production(self, device_id: str, current_count: int) -> Optional[Dict]:
        """检查产量"""
        self.init_device(device_id)
        
        plan = self.plans.get(device_id)
        if not plan or plan.target_count <= 0:
            return None
        
        rule = self._get_rule(device_id, "production_complete")
        if not rule or not rule.enabled:
            return None
        
        # 检查冷却时间
        current_time = time.time()
        if current_time - rule.last_triggered < rule.cooldown:
            return None
        
        # 检查是否达到目标
        if current_count >= plan.target_count:
            rule.last_triggered = current_time
            
            action = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "action": "stop" if plan.auto_stop_on_complete else "none",
                "params": {},
                "reason": f"产量达到目标 {current_count}/{plan.target_count}"
            }
            
            if plan.auto_switch_mode:
                action["action"] = "switch_mode"
                action["params"] = {"mode": plan.auto_switch_mode}
            
            print(f"🎯 调度触发: {rule.name} | {action['reason']}")
            
            if self.action_callback:
                await self.action_callback(device_id, action)
            
            return action
        
        return None
    
    # ========== 生产计划管理 ==========
    
    def set_production_plan(self, device_id: str, target_count: int, 
                           auto_stop: bool = True, auto_switch_mode: str = None) -> ProductionPlan:
        """设置生产计划"""
        plan = ProductionPlan(
            device_id=device_id,
            target_count=target_count,
            start_time=datetime.now(),
            auto_stop_on_complete=auto_stop,
            auto_switch_mode=auto_switch_mode
        )
        self.plans[device_id] = plan
        
        # 更新规则
        self.init_device(device_id)
        rule = self._get_rule(device_id, "production_complete")
        if rule:
            rule.threshold_max = target_count
            rule.enabled = target_count > 0
        
        print(f"📊 生产计划已设置: 设备={device_id}, 目标={target_count}")
        return plan
    
    def get_production_plan(self, device_id: str) -> Optional[ProductionPlan]:
        """获取生产计划"""
        return self.plans.get(device_id)
    
    def clear_production_plan(self, device_id: str):
        """清除生产计划"""
        if device_id in self.plans:
            del self.plans[device_id]
        rule = self._get_rule(device_id, "production_complete")
        if rule:
            rule.enabled = False
    
    def get_plan_progress(self, device_id: str, current_count: int) -> Dict:
        """获取生产计划进度"""
        plan = self.plans.get(device_id)
        
        if not plan or plan.target_count <= 0:
            return {
                "has_plan": False,
                "target": 0,
                "current": current_count,
                "progress": 0,
                "remaining": 0,
                "estimated_time": None
            }
        
        progress = min(100, (current_count / plan.target_count) * 100)
        remaining = max(0, plan.target_count - current_count)
        
        estimated_time = None
        if plan.start_time and current_count > 0 and progress < 100:
            elapsed = (datetime.now() - plan.start_time).total_seconds()
            rate = current_count / elapsed
            if rate > 0:
                remaining_seconds = remaining / rate
                estimated_complete = datetime.now() + timedelta(seconds=remaining_seconds)
                estimated_time = estimated_complete.strftime("%H:%M:%S")
        
        return {
            "has_plan": True,
            "target": plan.target_count,
            "current": current_count,
            "progress": round(progress, 1),
            "remaining": remaining,
            "estimated_time": estimated_time
        }
    
    # ========== 规则管理 ==========
    
    def update_rule(self, device_id: str, rule_id: str, **kwargs) -> bool:
        """更新规则"""
        self.init_device(device_id)
        rule = self._get_rule(device_id, rule_id)
        if rule:
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            return True
        return False
    
    def get_rules(self, device_id: str) -> List[Dict]:
        """获取所有规则"""
        self.init_device(device_id)
        return [rule.to_dict() for rule in self.rules[device_id]]
    
    def get_state(self, device_id: str) -> Dict:
        """获取调度器状态"""
        self.init_device(device_id)
        return {
            "rules": self.get_rules(device_id),
            "plan": self.plans.get(device_id, ProductionPlan(device_id)).to_dict(),
            "paused_by_scheduler": self.paused_by_scheduler.get(device_id, False),
            "pause_reasons": self.pause_reasons.get(device_id, []),
            "current_status": {
                "temp_out_of_range": self.temp_out_of_range.get(device_id, False),
                "humidity_out_of_range": self.humidity_out_of_range.get(device_id, False),
                "pressure_out_of_range": self.pressure_out_of_range.get(device_id, False)
            }
        }


# 全局实例
scheduler_manager = SchedulerManager()


def get_scheduler() -> SchedulerManager:
    """获取调度管理器实例"""
    return scheduler_manager
