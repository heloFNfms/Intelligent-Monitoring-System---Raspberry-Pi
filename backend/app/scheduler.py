"""
自动调度管理器 - 管理生产线的自动调度规则和生产计划
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, List
from datetime import datetime, timedelta
import asyncio


@dataclass
class ScheduleRule:
    """调度规则"""
    id: str
    name: str
    enabled: bool = True
    rule_type: str = "temperature"  # temperature / production / time
    condition: str = "gt"  # gt(大于) / lt(小于) / eq(等于)
    threshold: float = 0
    action: str = "pause"  # pause / stop / start / switch_mode
    action_params: Dict = field(default_factory=dict)
    cooldown: float = 60.0  # 冷却时间（秒）
    last_triggered: float = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "rule_type": self.rule_type,
            "condition": self.condition,
            "threshold": self.threshold,
            "action": self.action,
            "action_params": self.action_params,
            "cooldown": self.cooldown
        }


@dataclass
class ProductionPlan:
    """生产计划"""
    device_id: str
    target_count: int = 0  # 目标产量，0表示无限制
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    auto_stop_on_complete: bool = True  # 达到目标后自动停止
    auto_switch_mode: Optional[str] = None  # 达到目标后切换模式
    
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
    
    功能：
    1. 温度自动调度：温度过高自动暂停，恢复后自动启动
    2. 产量自动调度：达到目标产量后自动停止或切换模式
    3. 时间自动调度：定时启动/停止
    """
    
    # 默认调度规则
    DEFAULT_RULES = [
        ScheduleRule(
            id="temp_danger_pause",
            name="温度超限自动停止",
            enabled=True,
            rule_type="temperature",
            condition="gt",
            threshold=95.0,
            action="pause",
            cooldown=30.0
        ),
        ScheduleRule(
            id="humidity_danger_pause",
            name="湿度超限自动停止",
            enabled=True,
            rule_type="humidity",
            condition="gt",
            threshold=80.0,
            action="pause",
            cooldown=30.0
        ),
        ScheduleRule(
            id="pressure_danger_pause",
            name="压力超限自动停止",
            enabled=True,
            rule_type="pressure",
            condition="gt",
            threshold=110.0,
            action="pause",
            cooldown=30.0
        ),
        ScheduleRule(
            id="production_complete",
            name="产量达标自动停止",
            enabled=True,
            rule_type="production",
            condition="gte",
            threshold=0,  # 由生产计划设置
            action="stop",
            cooldown=5.0
        ),
        ScheduleRule(
            id="all_normal_start",
            name="全部正常自动启动",
            enabled=True,
            rule_type="all_normal_recover",
            condition="all_normal",
            threshold=0,
            action="start",
            cooldown=30.0
        )
    ]
    
    def __init__(self):
        # 调度规则（按设备ID管理）
        self.rules: Dict[str, List[ScheduleRule]] = {}
        
        # 生产计划（按设备ID管理）
        self.plans: Dict[str, ProductionPlan] = {}
        
        # 设备状态缓存
        self.device_states: Dict[str, Dict] = {}
        
        # 传感器历史（用于判断恢复）
        self.temp_history: Dict[str, List[float]] = {}
        self.humidity_history: Dict[str, List[float]] = {}
        self.pressure_history: Dict[str, List[float]] = {}
        
        # 是否因环境异常暂停（记录具体原因）
        self.paused_by_temp: Dict[str, bool] = {}
        self.paused_by_humidity: Dict[str, bool] = {}
        self.paused_by_pressure: Dict[str, bool] = {}
        
        # 环境阈值配置（从前端同步）
        self.thresholds: Dict[str, Dict] = {}
        
        # 动作回调
        self.action_callback: Optional[Callable] = None
        
        print("✓ 调度管理器初始化完成")
    
    def init_device(self, device_id: str):
        """初始化设备的调度规则"""
        if device_id not in self.rules:
            # 复制默认规则
            self.rules[device_id] = [
                ScheduleRule(
                    id=rule.id,
                    name=rule.name,
                    enabled=rule.enabled,
                    rule_type=rule.rule_type,
                    condition=rule.condition,
                    threshold=rule.threshold,
                    action=rule.action,
                    action_params=dict(rule.action_params),
                    cooldown=rule.cooldown
                )
                for rule in self.DEFAULT_RULES
            ]
            self.paused_by_temp[device_id] = False
            self.paused_by_humidity[device_id] = False
            self.paused_by_pressure[device_id] = False
            self.temp_history[device_id] = []
            self.humidity_history[device_id] = []
            self.pressure_history[device_id] = []
            # 默认阈值
            self.thresholds[device_id] = {
                "tempMax": 95.0,
                "humidityMax": 80.0,
                "pressureMax": 110.0
            }
            print(f"📋 设备 {device_id} 调度规则已初始化")
    
    def update_thresholds(self, device_id: str, thresholds: Dict):
        """更新设备的环境阈值配置"""
        self.init_device(device_id)
        self.thresholds[device_id] = thresholds
        
        # 同步更新规则中的阈值
        for rule in self.rules[device_id]:
            if rule.id == "temp_danger_pause" and "tempMax" in thresholds:
                rule.threshold = thresholds["tempMax"]
            elif rule.id == "humidity_danger_pause" and "humidityMax" in thresholds:
                rule.threshold = thresholds["humidityMax"]
            elif rule.id == "pressure_danger_pause" and "pressureMax" in thresholds:
                rule.threshold = thresholds["pressureMax"]
        
        print(f"📊 设备 {device_id} 阈值已更新: {thresholds}")
    
    def set_action_callback(self, callback: Callable):
        """设置动作回调函数"""
        self.action_callback = callback
    
    def set_production_plan(self, device_id: str, target_count: int, 
                           auto_stop: bool = True, auto_switch_mode: str = None) -> ProductionPlan:
        """
        设置生产计划
        
        Args:
            device_id: 设备ID
            target_count: 目标产量（0表示无限制）
            auto_stop: 达到目标后是否自动停止
            auto_switch_mode: 达到目标后切换到的模式
        """
        plan = ProductionPlan(
            device_id=device_id,
            target_count=target_count,
            start_time=datetime.now(),
            auto_stop_on_complete=auto_stop,
            auto_switch_mode=auto_switch_mode
        )
        self.plans[device_id] = plan
        
        # 更新产量规则的阈值
        self.init_device(device_id)
        for rule in self.rules[device_id]:
            if rule.id == "production_complete":
                rule.threshold = target_count
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
            # 禁用产量规则
            if device_id in self.rules:
                for rule in self.rules[device_id]:
                    if rule.id == "production_complete":
                        rule.enabled = False
    
    def update_rule(self, device_id: str, rule_id: str, **kwargs) -> bool:
        """更新调度规则"""
        self.init_device(device_id)
        
        for rule in self.rules[device_id]:
            if rule.id == rule_id:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                return True
        return False
    
    def get_rules(self, device_id: str) -> List[Dict]:
        """获取设备的所有调度规则"""
        self.init_device(device_id)
        return [rule.to_dict() for rule in self.rules[device_id]]
    
    def update_device_state(self, device_id: str, state: Dict):
        """更新设备状态"""
        self.device_states[device_id] = state
    
    async def check_temperature(self, device_id: str, temperature: float) -> Optional[Dict]:
        """
        检查温度并触发调度
        
        Returns:
            触发的动作，None表示无动作
        """
        import time
        
        self.init_device(device_id)
        current_time = time.time()
        
        # 记录温度历史
        if device_id not in self.temp_history:
            self.temp_history[device_id] = []
        self.temp_history[device_id].append(temperature)
        if len(self.temp_history[device_id]) > 10:
            self.temp_history[device_id].pop(0)
        
        for rule in self.rules[device_id]:
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            if current_time - rule.last_triggered < rule.cooldown:
                continue
            
            triggered = False
            
            # 温度超限暂停规则
            if rule.rule_type == "temperature" and rule.condition == "gt":
                if temperature > rule.threshold:
                    triggered = True
                    self.paused_by_temp[device_id] = True
            
            if triggered:
                rule.last_triggered = current_time
                action = {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "action": rule.action,
                    "params": rule.action_params,
                    "reason": f"温度 {temperature}°C 超过阈值 {rule.threshold}°C"
                }
                
                print(f"🔔 调度触发: {rule.name} | {action['reason']}")
                
                # 执行回调
                if self.action_callback:
                    await self.action_callback(device_id, action)
                
                return action
        
        # 检查是否全部正常可以自动启动
        return await self._check_all_normal_recover(device_id, current_time)
    
    async def check_humidity(self, device_id: str, humidity: float) -> Optional[Dict]:
        """
        检查湿度并触发调度
        
        Returns:
            触发的动作，None表示无动作
        """
        import time
        
        self.init_device(device_id)
        current_time = time.time()
        
        # 记录湿度历史
        if device_id not in self.humidity_history:
            self.humidity_history[device_id] = []
        self.humidity_history[device_id].append(humidity)
        if len(self.humidity_history[device_id]) > 10:
            self.humidity_history[device_id].pop(0)
        
        for rule in self.rules[device_id]:
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            if current_time - rule.last_triggered < rule.cooldown:
                continue
            
            triggered = False
            
            # 湿度超限暂停规则
            if rule.rule_type == "humidity" and rule.condition == "gt":
                if humidity > rule.threshold:
                    triggered = True
                    self.paused_by_humidity[device_id] = True
            
            if triggered:
                rule.last_triggered = current_time
                action = {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "action": rule.action,
                    "params": rule.action_params,
                    "reason": f"湿度 {humidity}% 超过阈值 {rule.threshold}%"
                }
                
                print(f"🔔 调度触发: {rule.name} | {action['reason']}")
                
                # 执行回调
                if self.action_callback:
                    await self.action_callback(device_id, action)
                
                return action
        
        # 检查是否全部正常可以自动启动
        return await self._check_all_normal_recover(device_id, current_time)
    
    async def check_pressure(self, device_id: str, pressure: float) -> Optional[Dict]:
        """
        检查压力并触发调度
        
        Returns:
            触发的动作，None表示无动作
        """
        import time
        
        self.init_device(device_id)
        current_time = time.time()
        
        # 记录压力历史
        if device_id not in self.pressure_history:
            self.pressure_history[device_id] = []
        self.pressure_history[device_id].append(pressure)
        if len(self.pressure_history[device_id]) > 10:
            self.pressure_history[device_id].pop(0)
        
        for rule in self.rules[device_id]:
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            if current_time - rule.last_triggered < rule.cooldown:
                continue
            
            triggered = False
            
            # 压力超限暂停规则
            if rule.rule_type == "pressure" and rule.condition == "gt":
                if pressure > rule.threshold:
                    triggered = True
                    self.paused_by_pressure[device_id] = True
            
            if triggered:
                rule.last_triggered = current_time
                action = {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "action": rule.action,
                    "params": rule.action_params,
                    "reason": f"压力 {pressure}kPa 超过阈值 {rule.threshold}kPa"
                }
                
                print(f"🔔 调度触发: {rule.name} | {action['reason']}")
                
                # 执行回调
                if self.action_callback:
                    await self.action_callback(device_id, action)
                
                return action
        
        # 检查是否全部正常可以自动启动
        return await self._check_all_normal_recover(device_id, current_time)
    
    async def _check_all_normal_recover(self, device_id: str, current_time: float) -> Optional[Dict]:
        """
        检查是否所有环境参数都恢复正常，可以自动启动
        
        Returns:
            触发的动作，None表示无动作
        """
        # 检查是否有任何环境异常导致的暂停
        paused_by_any = (
            self.paused_by_temp.get(device_id, False) or
            self.paused_by_humidity.get(device_id, False) or
            self.paused_by_pressure.get(device_id, False)
        )
        
        if not paused_by_any:
            return None
        
        # 获取阈值配置
        thresholds = self.thresholds.get(device_id, {})
        temp_max = thresholds.get("tempMax", 95.0)
        humidity_max = thresholds.get("humidityMax", 80.0)
        pressure_max = thresholds.get("pressureMax", 110.0)
        
        # 检查最近的传感器数据是否都正常
        recent_temps = self.temp_history.get(device_id, [])
        recent_humidity = self.humidity_history.get(device_id, [])
        recent_pressure = self.pressure_history.get(device_id, [])
        
        # 需要至少3次连续正常数据才能恢复
        temp_normal = len(recent_temps) >= 3 and all(t <= temp_max for t in recent_temps[-3:])
        humidity_normal = len(recent_humidity) >= 3 and all(h <= humidity_max for h in recent_humidity[-3:])
        pressure_normal = len(recent_pressure) >= 3 and all(p <= pressure_max for p in recent_pressure[-3:])
        
        # 如果没有数据，默认为正常
        if len(recent_temps) == 0:
            temp_normal = True
        if len(recent_humidity) == 0:
            humidity_normal = True
        if len(recent_pressure) == 0:
            pressure_normal = True
        
        # 所有参数都正常才能恢复
        all_normal = temp_normal and humidity_normal and pressure_normal
        
        if not all_normal:
            return None
        
        # 查找全部正常自动启动规则
        for rule in self.rules[device_id]:
            if rule.id != "all_normal_start" or not rule.enabled:
                continue
            
            # 检查冷却时间
            if current_time - rule.last_triggered < rule.cooldown:
                continue
            
            # 重置所有暂停标志
            self.paused_by_temp[device_id] = False
            self.paused_by_humidity[device_id] = False
            self.paused_by_pressure[device_id] = False
            
            rule.last_triggered = current_time
            action = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "action": rule.action,
                "params": rule.action_params,
                "reason": "温度、湿度、压力全部恢复正常"
            }
            
            print(f"🔔 调度触发: {rule.name} | {action['reason']}")
            
            # 执行回调
            if self.action_callback:
                await self.action_callback(device_id, action)
            
            return action
        
        return None
    
    async def check_production(self, device_id: str, current_count: int) -> Optional[Dict]:
        """
        检查产量并触发调度
        
        Returns:
            触发的动作，None表示无动作
        """
        import time
        
        self.init_device(device_id)
        current_time = time.time()
        
        plan = self.plans.get(device_id)
        if not plan or plan.target_count <= 0:
            return None
        
        for rule in self.rules[device_id]:
            if not rule.enabled or rule.rule_type != "production":
                continue
            
            # 检查冷却时间
            if current_time - rule.last_triggered < rule.cooldown:
                continue
            
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
                
                # 如果设置了切换模式
                if plan.auto_switch_mode:
                    action["action"] = "switch_mode"
                    action["params"] = {"mode": plan.auto_switch_mode}
                
                print(f"🎯 调度触发: {rule.name} | {action['reason']}")
                
                # 执行回调
                if self.action_callback:
                    await self.action_callback(device_id, action)
                
                return action
        
        return None
    
    def get_plan_progress(self, device_id: str, current_count: int) -> Dict:
        """
        获取生产计划进度
        
        Returns:
            {
                "has_plan": bool,
                "target": int,
                "current": int,
                "progress": float (0-100),
                "remaining": int,
                "estimated_time": str or None
            }
        """
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
        
        # 估算完成时间（基于启动时间和当前进度）
        estimated_time = None
        if plan.start_time and current_count > 0 and progress < 100:
            elapsed = (datetime.now() - plan.start_time).total_seconds()
            rate = current_count / elapsed  # 每秒产量
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
    
    def get_state(self, device_id: str) -> Dict:
        """获取调度器状态"""
        self.init_device(device_id)
        
        return {
            "rules": self.get_rules(device_id),
            "plan": self.plans.get(device_id, ProductionPlan(device_id)).to_dict(),
            "paused_by_temp": self.paused_by_temp.get(device_id, False)
        }


# 全局调度管理器实例
scheduler_manager = SchedulerManager()


def get_scheduler() -> SchedulerManager:
    """获取调度管理器实例"""
    return scheduler_manager
