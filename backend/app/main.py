"""
FastAPI主应用 - 智能生产线监控系统后端
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List
import time

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
from .conveyor import get_conveyor_manager, conveyor_managers
from .scheduler import get_scheduler, scheduler_manager

# 检测模式管理（zone=危险区域检测, product=产品检测）
detection_modes = {}  # device_id -> mode


def get_detection_mode(device_id: str) -> str:
    """获取设备的检测模式"""
    return detection_modes.get(device_id, "zone")


def set_detection_mode(device_id: str, mode: str):
    """设置设备的检测模式"""
    if mode in ["zone", "product"]:
        detection_modes[device_id] = mode


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
CONVEYOR_UPDATE_INTERVAL = 0.05  # 传送带更新间隔（秒），20 FPS


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


async def conveyor_simulation_task():
    """传送带模拟后台任务 - 定时更新并广播状态"""
    last_time = time.time()
    
    while True:
        current_time = time.time()
        delta_time = current_time - last_time
        last_time = current_time
        
        # 复制字典避免迭代时修改
        conveyors_copy = dict(conveyor_managers)
        
        # 更新所有传送带
        for device_id, conveyor in conveyors_copy.items():
            # 只要有传送带管理器就处理（不管是否运行）
            old_completed = conveyor.completed_count
            events = conveyor.update(delta_time)
            
            # 如果有物品完成，同步更新生产计数
            if events.get("completed") and conveyor.completed_count > old_completed:
                db = None
                try:
                    db = SessionLocal()
                    status = db.query(ProductionStatus).filter(
                        ProductionStatus.device_id == device_id
                    ).first()
                    if status:
                        new_items = conveyor.completed_count - old_completed
                        status.production_count += new_items
                        db.commit()
                        # 广播生产状态更新
                        await manager.broadcast_status_change(
                            device_id, status.status, status.mode, status.production_count
                        )
                        # 检查产量调度规则
                        scheduler = get_scheduler()
                        await scheduler.check_production(device_id, status.production_count)
                except Exception as e:
                    print(f"同步生产计数失败: {e}")
                finally:
                    if db:
                        db.close()
            
            # 广播传送带更新到前端（只要有连接就广播）
            if manager.dashboard_connections:
                await manager.broadcast_conveyor_update(device_id, conveyor.get_state())
        
        await asyncio.sleep(CONVEYOR_UPDATE_INTERVAL)


@app.on_event("startup")
async def startup():
    """应用启动时初始化数据库"""
    init_db()
    
    # 初始化默认设备的传送带管理器，并同步数据库状态
    default_device = "device_001"
    db = SessionLocal()
    try:
        status = db.query(ProductionStatus).filter(
            ProductionStatus.device_id == default_device
        ).first()
        
        conveyor = get_conveyor_manager(default_device)
        if status:
            conveyor.sync_with_production(status.status, status.mode)
            print(f"📦 传送带已同步: 状态={status.status}, 模式={status.mode}")
        else:
            print(f"📦 传送带已初始化: 设备={default_device}")
    finally:
        db.close()
    
    # 启动自动清理任务
    asyncio.create_task(auto_cleanup_task())
    
    # 启动传送带模拟任务
    asyncio.create_task(conveyor_simulation_task())
    
    # 初始化调度管理器
    scheduler = get_scheduler()
    scheduler.init_device(default_device)
    scheduler.set_action_callback(execute_schedule_action)
    
    print("🚀 智能生产线监控系统已启动")
    print("📋 自动调度规则已启用")
    print(f"🧹 数据保留 {DATA_RETENTION_DAYS} 天，每 {AUTO_CLEANUP_INTERVAL//3600} 小时自动清理")
    print(f"🔄 传送带模拟已启动，更新频率: {1/CONVEYOR_UPDATE_INTERVAL:.0f} FPS")


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


async def execute_schedule_action(device_id: str, action: dict):
    """执行调度动作"""
    cmd = action.get("action")
    params = action.get("params", {})
    reason = action.get("reason", "自动调度")
    
    if cmd == "none":
        return
    
    db = SessionLocal()
    try:
        status = db.query(ProductionStatus).filter(
            ProductionStatus.device_id == device_id
        ).first()
        
        if not status:
            return
        
        message = ""
        if cmd == "start":
            if status.status != "running":
                status.status = "running"
                message = f"自动启动: {reason}"
        elif cmd == "stop":
            if status.status != "stopped":
                status.status = "stopped"
                message = f"自动停止: {reason}"
        elif cmd == "pause":
            if status.status == "running":
                status.status = "paused"
                message = f"自动暂停: {reason}"
        elif cmd == "switch_mode":
            new_mode = params.get("mode", "product_a")
            status.mode = new_mode
            message = f"自动切换模式: {new_mode}"
        
        if message:
            db.commit()
            
            # 同步传送带状态
            conveyor = get_conveyor_manager(device_id)
            conveyor.sync_with_production(status.status, status.mode)
            
            # 广播状态变化
            await manager.broadcast_status_change(
                device_id, status.status, status.mode, status.production_count
            )
            
            # 广播调度事件
            await manager.broadcast_to_dashboard({
                "type": "schedule_action",
                "data": {
                    "device_id": device_id,
                    "action": cmd,
                    "reason": reason,
                    "message": message
                },
                "timestamp": datetime.now().isoformat()
            })
            
            print(f"⚡ 调度执行: {message}")
    except Exception as e:
        print(f"调度执行失败: {e}")
    finally:
        db.close()


async def process_sensor_data(device_id: str, data: dict):
    """处理传感器数据并广播"""
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
        
        # 检查温度调度规则
        scheduler = get_scheduler()
        await scheduler.check_temperature(device_id, value)


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
    
    # 同步传送带状态
    conveyor = get_conveyor_manager(device_id)
    conveyor.sync_with_production(status.status, status.mode)
    
    # 广播状态变化
    await manager.broadcast_status_change(
        device_id, status.status, status.mode, status.production_count
    )
    
    # 立即广播传送带状态
    await manager.broadcast_conveyor_update(device_id, conveyor.get_state())
    
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


# ---------- 传送带API ----------
@app.get("/api/conveyor/{device_id}", tags=["传送带"])
async def get_conveyor_state(device_id: str):
    """获取传送带状态"""
    conveyor = get_conveyor_manager(device_id)
    return conveyor.get_state()


@app.post("/api/conveyor/{device_id}/control", tags=["传送带"])
async def control_conveyor(device_id: str, data: dict):
    """
    传送带控制
    
    Body:
        command: start/stop/pause/add_item/clear/set_speed
        params: 可选参数 (如 speed)
    """
    conveyor = get_conveyor_manager(device_id)
    cmd = data.get("command")
    params = data.get("params", {})
    
    result = {"success": True, "command": cmd}
    
    if cmd == "start":
        conveyor.start()
        result["message"] = "传送带已启动"
    elif cmd == "stop":
        conveyor.stop()
        result["message"] = "传送带已停止"
    elif cmd == "pause":
        conveyor.pause()
        result["message"] = "传送带已暂停"
    elif cmd == "add_item":
        item = conveyor.add_item_manual()
        if item:
            result["message"] = "已添加物品"
            result["item"] = item
        else:
            result["success"] = False
            result["message"] = "无法添加物品（传送带已满或入口被占用）"
    elif cmd == "clear":
        conveyor.clear_items()
        result["message"] = "已清空物品"
    elif cmd == "set_speed":
        speed = params.get("speed", 1.0)
        conveyor.set_speed(speed)
        result["message"] = f"速度已设置为 {conveyor.speed}x"
    elif cmd == "reset":
        conveyor.reset()
        result["message"] = "传送带已重置"
    else:
        raise HTTPException(status_code=400, detail=f"未知命令: {cmd}")
    
    # 广播状态更新
    await manager.broadcast_conveyor_update(device_id, conveyor.get_state())
    
    return result


# ---------- 调度管理API ----------
@app.get("/api/scheduler/{device_id}", tags=["调度管理"])
async def get_scheduler_state(device_id: str):
    """获取调度器状态"""
    scheduler = get_scheduler()
    return scheduler.get_state(device_id)


@app.get("/api/scheduler/{device_id}/rules", tags=["调度管理"])
async def get_schedule_rules(device_id: str):
    """获取调度规则列表"""
    scheduler = get_scheduler()
    return scheduler.get_rules(device_id)


@app.put("/api/scheduler/{device_id}/rules/{rule_id}", tags=["调度管理"])
async def update_schedule_rule(device_id: str, rule_id: str, data: dict):
    """
    更新调度规则
    
    Body:
        enabled: bool - 是否启用
        threshold: float - 阈值
        cooldown: float - 冷却时间
    """
    scheduler = get_scheduler()
    success = scheduler.update_rule(device_id, rule_id, **data)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"规则不存在: {rule_id}")
    
    return {"success": True, "rule_id": rule_id}


@app.post("/api/scheduler/{device_id}/plan", tags=["调度管理"])
async def set_production_plan(device_id: str, data: dict):
    """
    设置生产计划
    
    Body:
        target_count: int - 目标产量（0表示无限制）
        auto_stop: bool - 达到目标后是否自动停止
        auto_switch_mode: str - 达到目标后切换到的模式（可选）
    """
    scheduler = get_scheduler()
    
    target_count = data.get("target_count", 0)
    auto_stop = data.get("auto_stop", True)
    auto_switch_mode = data.get("auto_switch_mode")
    
    plan = scheduler.set_production_plan(
        device_id, target_count, auto_stop, auto_switch_mode
    )
    
    return {
        "success": True,
        "plan": plan.to_dict()
    }


@app.delete("/api/scheduler/{device_id}/plan", tags=["调度管理"])
async def clear_production_plan(device_id: str):
    """清除生产计划"""
    scheduler = get_scheduler()
    scheduler.clear_production_plan(device_id)
    return {"success": True}


@app.get("/api/scheduler/{device_id}/progress", tags=["调度管理"])
async def get_plan_progress(device_id: str, db: Session = Depends(get_db)):
    """获取生产计划进度"""
    scheduler = get_scheduler()
    
    # 获取当前产量
    status = db.query(ProductionStatus).filter(
        ProductionStatus.device_id == device_id
    ).first()
    
    current_count = status.production_count if status else 0
    
    return scheduler.get_plan_progress(device_id, current_count)


# ---------- 产品检测API ----------
@app.post("/api/product/detection", tags=["产品检测"])
async def report_product_detection(data: dict):
    """
    上报产品检测结果
    
    Body:
        device_id: 设备ID
        product_type: 产品类型 (product_a/product_b/unknown)
        color: 颜色
        shape: 形状
        confidence: 置信度
    """
    device_id = data.get("device_id", "device_001")
    product_type = data.get("product_type", "unknown")
    color = data.get("color", "")
    shape = data.get("shape", "")
    confidence = data.get("confidence", 0)
    
    # 广播到前端
    await manager.broadcast_to_dashboard({
        "type": "product_detection",
        "data": {
            "device_id": device_id,
            "product_type": product_type,
            "color": color,
            "shape": shape,
            "confidence": confidence
        },
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "success": True,
        "product_type": product_type
    }


# ---------- 检测模式API ----------
@app.get("/api/detection/mode/{device_id}", tags=["检测模式"])
async def get_device_detection_mode(device_id: str):
    """获取设备的检测模式"""
    mode = get_detection_mode(device_id)
    return {"device_id": device_id, "mode": mode}


@app.put("/api/detection/mode/{device_id}", tags=["检测模式"])
async def set_device_detection_mode(device_id: str, data: dict):
    """
    设置设备的检测模式
    
    Body:
        mode: str - 检测模式 (zone=危险区域检测, product=产品检测)
    """
    mode = data.get("mode", "zone")
    if mode not in ["zone", "product"]:
        raise HTTPException(status_code=400, detail="无效的检测模式，必须是 zone 或 product")
    
    set_detection_mode(device_id, mode)
    
    # 广播模式变化到前端
    await manager.broadcast_to_dashboard({
        "type": "detection_mode_change",
        "data": {
            "device_id": device_id,
            "mode": mode
        },
        "timestamp": datetime.now().isoformat()
    })
    
    return {"success": True, "device_id": device_id, "mode": mode}


# ---------- 健康检查 ----------
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
