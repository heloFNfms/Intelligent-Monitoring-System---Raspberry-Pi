"""
Pydantic数据模型 - 用于API请求和响应
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ==================== 检测相关 ====================
class DetectionReport(BaseModel):
    """树莓派上报的检测数据"""
    device_id: str
    person_count: int = 0
    in_danger_zone: bool = False
    alert_triggered: bool = False
    details: Optional[str] = None


class DetectionResponse(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    person_count: int
    in_danger_zone: bool
    alert_triggered: bool
    
    class Config:
        from_attributes = True


# ==================== 传感器相关 ====================
class SensorReport(BaseModel):
    """传感器上报数据"""
    device_id: str
    sensor_type: str  # temperature/pressure/humidity
    value: float
    unit: str = ""


class SensorResponse(BaseModel):
    id: int
    device_id: str
    sensor_type: str
    timestamp: datetime
    value: float
    unit: str
    
    class Config:
        from_attributes = True


# ==================== 生产状态相关 ====================
class ProductionStatusUpdate(BaseModel):
    """更新生产状态"""
    status: Optional[str] = None  # running/stopped/paused
    mode: Optional[str] = None    # product_a/product_b
    production_count: Optional[int] = None


class ProductionStatusResponse(BaseModel):
    device_id: str
    status: str
    mode: str
    production_count: int
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 控制指令相关 ====================
class ControlCommand(BaseModel):
    """控制指令"""
    device_id: str
    command: str  # start/stop/pause/switch_mode
    params: Optional[dict] = None


class ControlResponse(BaseModel):
    success: bool
    message: str
    command: str


# ==================== 报警相关 ====================
class AlertCreate(BaseModel):
    device_id: str
    alert_type: str
    message: str
    level: str = "warning"


class AlertResponse(BaseModel):
    id: int
    device_id: str
    alert_type: str
    timestamp: datetime
    message: str
    level: str
    resolved: bool
    
    class Config:
        from_attributes = True


# ==================== 仪表盘数据 ====================
class DashboardData(BaseModel):
    """仪表盘汇总数据"""
    # 生产状态
    production_status: str
    production_mode: str
    total_production: int
    
    # 最新传感器数据
    current_temperature: Optional[float] = None
    current_pressure: Optional[float] = None
    
    # 报警统计
    active_alerts: int
    today_alerts: int
    
    # 检测统计
    today_detections: int
    danger_zone_entries: int


# ==================== WebSocket消息 ====================
class WSMessage(BaseModel):
    """WebSocket消息格式"""
    type: str  # sensor_update/detection/alert/status_change/control_response
    data: dict
    timestamp: datetime = None
    
    def __init__(self, **data):
        if 'timestamp' not in data or data['timestamp'] is None:
            data['timestamp'] = datetime.now()
        super().__init__(**data)
