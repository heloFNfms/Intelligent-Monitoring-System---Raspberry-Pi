"""
FastAPI主应用 - 智能生产线监控系统后端
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List

from .database import get_db, init_db, DetectionRecord, SensorData, ProductionStatus, AlertRecord, cleanup_old_data, get_data_statistics, SessionLocal
from .schemas import (
    DetectionReport, DetectionResponse,
    SensorReport, SensorResponse,
    ProductionStatusUpdate, ProductionStatusResponse,
    ControlCommand, ControlResponse,
    AlertCreate, AlertResponse,
    DashboardData
)
from .websocket_manager import manager
from .config import settings

# 创建FastAPI应用
app = FastAPI(
    title="智能生产线监控系统",
    description="基于多源数据的智能生产线监控与调度系统API",
    version="1.0.0"
)

# 配置CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


import asyncio

# 数据清理配置
DATA_RETENTION_DAYS = 7  # 数据保留天数
AUTO_CLEANUP_INTERVAL = 3600 * 6  # 自动清理间隔（秒），每6小时清理一次


async def auto_cleanup_task():
    """后台自动清理任务"""
    while True:
        await asyncio.sleep(AUTO_CLEANUP_INTERVAL)
        try:
            db = SessionLocal()
            deleted = cleanup_old_data(db, DATA_RETENTION_DAYS)
            if deleted > 0:
                print(f"🧹 自动清理完成，删除 {deleted} 条过期数据")
            db.close()
        except Exception as e:
            print(f"自动清理失败: {e}")


@app.on_event("startup")
async def startup():
    """应用启动时初始化数据库"""
    init_db()
    
    # 启动自动清理任务
    asyncio.create_task(auto_cleanup_task())
    
    print("🚀 智能生产线监控系统已启动")
    print(f"🧹 数据保留 {DATA_RETENTION_DAYS} 天，每 {AUTO_CLEANUP_INTERVAL//3600} 小时自动清理")


# ==================== WebSocket端点 ====================
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """前端大屏WebSocket连接"""
    await manager.connect_dashboard(websocket)
    try:
        while True:
            # 接收前端消息（如控制指令）
            data = await websocket.receive_json()
            # 处理控制指令
            if data.get("type") == "control":
                await handle_control_command(data.get("data", {}))
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)


@app.websocket("/ws/device/{device_id}")
async def websocket_device(websocket: WebSocket, device_id: str):
    """设备端WebSocket连接（树莓派等）"""
    await manager.connect_device(websocket, device_id)
    try:
        while True:
            data = await websocket.receive_json()
            # 处理设备上报的数据
            await handle_device_data(device_id, data)
    except WebSocketDisconnect:
        manager.disconnect_device(device_id)


async def handle_device_data(device_id: str, data: dict):
    """处理设备上报的数据"""
    data_type = data.get("type")
    
    if data_type == "sensor":
        # 传感器数据
        await process_sensor_data(device_id, data.get("data", {}))
    elif data_type == "detection":
        # 检测数据
        await process_detection_data(device_id, data.get("data", {}))


async def handle_control_command(data: dict):
    """处理控制指令"""
    device_id = data.get("device_id")
    command = data.get("command")
    
    # 发送指令到设备
    success = await manager.send_to_device(device_id, {
        "type": "control",
        "command": command,
        "params": data.get("params", {})
    })
    
    return success


async def process_sensor_data(device_id: str, data: dict):
    """处理传感器数据并广播"""
    # 这里可以添加数据库存储逻辑
    sensor_type = data.get("sensor_type")
    value = data.get("value")
    unit = data.get("unit", "")
    
    # 广播到前端
    await manager.broadcast_sensor_update(device_id, sensor_type, value, unit)
    
    # 检查是否需要报警
    if sensor_type == "temperature":
        if value >= settings.TEMP_DANGER_THRESHOLD:
            await manager.broadcast_alert(device_id, "temperature", 
                f"温度过高警报: {value}°C", "danger")
        elif value >= settings.TEMP_WARNING_THRESHOLD:
            await manager.broadcast_alert(device_id, "temperature", 
                f"温度警告: {value}°C", "warning")


async def process_detection_data(device_id: str, data: dict):
    """处理检测数据并广播"""
    person_count = data.get("person_count", 0)
    in_danger = data.get("in_danger_zone", False)
    alert = data.get("alert_triggered", False)
    
    # 广播到前端
    await manager.broadcast_detection(device_id, person_count, in_danger, alert)
    
    # 如果触发报警
    if alert:
        await manager.broadcast_alert(device_id, "intrusion", 
            "检测到人员进入危险区域！", "danger")


# ==================== HTTP API端点 ====================

# ---------- 检测数据API ----------
@app.post("/api/detection", response_model=DetectionResponse, tags=["检测数据"])
async def report_detection(report: DetectionReport, db: Session = Depends(get_db)):
    """树莓派上报检测数据"""
    record = DetectionRecord(
        device_id=report.device_id,
        person_count=report.person_count,
        in_danger_zone=report.in_danger_zone,
        alert_triggered=report.alert_triggered,
        details=report.details
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    
    # 广播到前端
    await manager.broadcast_detection(
        report.device_id, report.person_count, 
        report.in_danger_zone, report.alert_triggered
    )
    
    # 如果触发报警，记录报警
    if report.alert_triggered:
        alert = AlertRecord(
            device_id=report.device_id,
            alert_type="intrusion",
            message="检测到人员进入危险区域",
            level="danger"
        )
        db.add(alert)
        db.commit()
        
        await manager.broadcast_alert(report.device_id, "intrusion", 
            "检测到人员进入危险区域！", "danger")
    
    return record


@app.get("/api/detection/history", response_model=List[DetectionResponse], tags=["检测数据"])
async def get_detection_history(
    device_id: str = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取检测历史记录"""
    query = db.query(DetectionRecord)
    if device_id:
        query = query.filter(DetectionRecord.device_id == device_id)
    records = query.order_by(DetectionRecord.timestamp.desc()).limit(limit).all()
    return records


# ---------- 传感器数据API ----------
@app.post("/api/sensor", response_model=SensorResponse, tags=["传感器数据"])
async def report_sensor(report: SensorReport, db: Session = Depends(get_db)):
    """上报传感器数据"""
    record = SensorData(
        device_id=report.device_id,
        sensor_type=report.sensor_type,
        value=report.value,
        unit=report.unit
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    
    # 广播到前端
    await manager.broadcast_sensor_update(
        report.device_id, report.sensor_type, report.value, report.unit
    )
    
    # 检查温度报警
    if report.sensor_type == "temperature":
        if report.value >= settings.TEMP_DANGER_THRESHOLD:
            alert = AlertRecord(
                device_id=report.device_id,
                alert_type="temperature",
                message=f"温度过高: {report.value}°C",
                level="danger"
            )
            db.add(alert)
            db.commit()
            await manager.broadcast_alert(report.device_id, "temperature", 
                f"温度过高警报: {report.value}°C", "danger")
    
    return record


@app.get("/api/sensor/latest", tags=["传感器数据"])
async def get_latest_sensor(device_id: str = "device_001", db: Session = Depends(get_db)):
    """获取最新传感器数据"""
    # 获取各类型传感器的最新值
    result = {}
    for sensor_type in ["temperature", "pressure", "humidity"]:
        record = db.query(SensorData).filter(
            SensorData.device_id == device_id,
            SensorData.sensor_type == sensor_type
        ).order_by(SensorData.timestamp.desc()).first()
        
        if record:
            result[sensor_type] = {
                "value": record.value,
                "unit": record.unit,
                "timestamp": record.timestamp.isoformat()
            }
    
    return result


@app.get("/api/sensor/history", response_model=List[SensorResponse], tags=["传感器数据"])
async def get_sensor_history(
    device_id: str = None,
    sensor_type: str = None,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """获取传感器历史数据"""
    query = db.query(SensorData)
    
    if device_id:
        query = query.filter(SensorData.device_id == device_id)
    if sensor_type:
        query = query.filter(SensorData.sensor_type == sensor_type)
    
    # 只获取最近N小时的数据
    since = datetime.now() - timedelta(hours=hours)
    query = query.filter(SensorData.timestamp >= since)
    
    records = query.order_by(SensorData.timestamp.desc()).limit(500).all()
    return records


# ---------- 生产状态API ----------
@app.get("/api/status/{device_id}", response_model=ProductionStatusResponse, tags=["生产状态"])
async def get_production_status(device_id: str, db: Session = Depends(get_db)):
    """获取生产状态"""
    status = db.query(ProductionStatus).filter(
        ProductionStatus.device_id == device_id
    ).first()
    
    if not status:
        # 创建默认状态
        status = ProductionStatus(
            device_id=device_id,
            status="stopped",
            mode="product_a",
            production_count=0
        )
        db.add(status)
        db.commit()
        db.refresh(status)
    
    return status


@app.put("/api/status/{device_id}", response_model=ProductionStatusResponse, tags=["生产状态"])
async def update_production_status(
    device_id: str, 
    update: ProductionStatusUpdate, 
    db: Session = Depends(get_db)
):
    """更新生产状态"""
    status = db.query(ProductionStatus).filter(
        ProductionStatus.device_id == device_id
    ).first()
    
    if not status:
        status = ProductionStatus(device_id=device_id)
        db.add(status)
    
    if update.status is not None:
        status.status = update.status
    if update.mode is not None:
        status.mode = update.mode
    if update.production_count is not None:
        status.production_count = update.production_count
    
    db.commit()
    db.refresh(status)
    
    # 广播状态变化
    await manager.broadcast_status_change(
        device_id, status.status, status.mode, status.production_count
    )
    
    return status


# ---------- 控制指令API ----------
@app.post("/api/control", response_model=ControlResponse, tags=["控制指令"])
async def send_control(command: ControlCommand, db: Session = Depends(get_db)):
    """发送控制指令到设备"""
    device_id = command.device_id
    cmd = command.command
    
    # 更新数据库中的状态
    status = db.query(ProductionStatus).filter(
        ProductionStatus.device_id == device_id
    ).first()
    
    if not status:
        status = ProductionStatus(device_id=device_id)
        db.add(status)
    
    message = ""
    if cmd == "start":
        status.status = "running"
        message = "生产线已启动"
    elif cmd == "stop":
        status.status = "stopped"
        message = "生产线已停止"
    elif cmd == "pause":
        status.status = "paused"
        message = "生产线已暂停"
    elif cmd == "switch_mode":
        new_mode = command.params.get("mode", "product_a") if command.params else "product_a"
        status.mode = new_mode
        message = f"已切换到{new_mode}模式"
    elif cmd == "reset_count":
        status.production_count = 0
        message = "生产计数已重置"
    else:
        raise HTTPException(status_code=400, detail=f"未知指令: {cmd}")
    
    db.commit()
    db.refresh(status)
    
    # 广播状态变化
    await manager.broadcast_status_change(
        device_id, status.status, status.mode, status.production_count
    )
    
    # 尝试发送到设备
    await manager.send_to_device(device_id, {
        "type": "control",
        "command": cmd,
        "params": command.params
    })
    
    return ControlResponse(success=True, message=message, command=cmd)


# ---------- 报警API ----------
@app.get("/api/alerts", response_model=List[AlertResponse], tags=["报警管理"])
async def get_alerts(
    device_id: str = None,
    resolved: bool = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取报警记录"""
    query = db.query(AlertRecord)
    
    if device_id:
        query = query.filter(AlertRecord.device_id == device_id)
    if resolved is not None:
        query = query.filter(AlertRecord.resolved == resolved)
    
    records = query.order_by(AlertRecord.timestamp.desc()).limit(limit).all()
    return records


@app.put("/api/alerts/{alert_id}/resolve", response_model=AlertResponse, tags=["报警管理"])
async def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """处理报警"""
    alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="报警记录不存在")
    
    alert.resolved = True
    db.commit()
    db.refresh(alert)
    return alert


# ---------- 仪表盘API ----------
@app.get("/api/dashboard", response_model=DashboardData, tags=["仪表盘"])
async def get_dashboard(device_id: str = "device_001", db: Session = Depends(get_db)):
    """获取仪表盘汇总数据"""
    # 获取生产状态
    status = db.query(ProductionStatus).filter(
        ProductionStatus.device_id == device_id
    ).first()
    
    # 获取最新传感器数据
    temp_record = db.query(SensorData).filter(
        SensorData.device_id == device_id,
        SensorData.sensor_type == "temperature"
    ).order_by(SensorData.timestamp.desc()).first()
    
    pressure_record = db.query(SensorData).filter(
        SensorData.device_id == device_id,
        SensorData.sensor_type == "pressure"
    ).order_by(SensorData.timestamp.desc()).first()
    
    # 统计报警
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    active_alerts = db.query(func.count(AlertRecord.id)).filter(
        AlertRecord.resolved == False
    ).scalar()
    
    today_alerts = db.query(func.count(AlertRecord.id)).filter(
        AlertRecord.timestamp >= today
    ).scalar()
    
    # 统计检测
    today_detections = db.query(func.count(DetectionRecord.id)).filter(
        DetectionRecord.timestamp >= today
    ).scalar()
    
    danger_entries = db.query(func.count(DetectionRecord.id)).filter(
        DetectionRecord.timestamp >= today,
        DetectionRecord.in_danger_zone == True
    ).scalar()
    
    return DashboardData(
        production_status=status.status if status else "stopped",
        production_mode=status.mode if status else "product_a",
        total_production=status.production_count if status else 0,
        current_temperature=temp_record.value if temp_record else None,
        current_pressure=pressure_record.value if pressure_record else None,
        active_alerts=active_alerts or 0,
        today_alerts=today_alerts or 0,
        today_detections=today_detections or 0,
        danger_zone_entries=danger_entries or 0
    )


# ---------- 视频流API ----------
# 存储最新的视频帧
latest_video_frames = {}


@app.post("/api/video/frame", tags=["视频流"])
async def receive_video_frame(data: dict):
    """接收视频帧并广播到前端"""
    device_id = data.get("device_id", "device_001")
    frame_base64 = data.get("frame")
    detection = data.get("detection", {})
    timestamp = data.get("timestamp")
    
    if not frame_base64:
        raise HTTPException(status_code=400, detail="缺少视频帧数据")
    
    # 存储最新帧
    latest_video_frames[device_id] = {
        "frame": frame_base64,
        "detection": detection,
        "timestamp": timestamp
    }
    
    # 广播到前端
    await manager.broadcast_to_dashboard({
        "type": "video_frame",
        "data": {
            "device_id": device_id,
            "frame": frame_base64,
            "detection": detection
        },
        "timestamp": timestamp
    })
    
    return {"success": True}


@app.get("/api/video/latest/{device_id}", tags=["视频流"])
async def get_latest_frame(device_id: str):
    """获取最新视频帧"""
    if device_id not in latest_video_frames:
        raise HTTPException(status_code=404, detail="没有可用的视频帧")
    
    return latest_video_frames[device_id]


# ---------- LED状态API ----------
@app.post("/api/led", tags=["LED控制"])
async def report_led_status(data: dict):
    """
    上报LED状态（开发板调用）
    
    Body:
        device_id: 设备ID
        led_type: LED类型 (alert/product_a/product_b/running)
        state: 状态 (true/false)
    """
    device_id = data.get("device_id", "device_001")
    led_type = data.get("led_type")
    state = data.get("state", False)
    
    if led_type not in ["alert", "product_a", "product_b", "running"]:
        raise HTTPException(status_code=400, detail="无效的LED类型")
    
    # 广播到前端
    await manager.broadcast_led_status(device_id, led_type, state)
    
    return {"success": True, "led_type": led_type, "state": state}


# ---------- 数据管理API ----------
@app.get("/api/data/statistics", tags=["数据管理"])
async def get_statistics(db: Session = Depends(get_db)):
    """获取数据库统计信息"""
    stats = get_data_statistics(db)
    return {
        "sensor_data_count": stats["sensor_data_count"],
        "detection_count": stats["detection_count"],
        "alert_count": stats["alert_count"],
        "total_records": sum(stats.values())
    }


@app.delete("/api/data/cleanup", tags=["数据管理"])
async def cleanup_data(days_to_keep: int = 7, db: Session = Depends(get_db)):
    """
    清理过期数据
    
    Args:
        days_to_keep: 保留最近N天的数据，默认7天
    """
    if days_to_keep < 1:
        raise HTTPException(status_code=400, detail="保留天数必须大于0")
    
    deleted_count = cleanup_old_data(db, days_to_keep)
    return {
        "success": True,
        "message": f"已清理 {deleted_count} 条过期数据",
        "deleted_count": deleted_count,
        "days_kept": days_to_keep
    }


# ---------- 健康检查 ----------
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
