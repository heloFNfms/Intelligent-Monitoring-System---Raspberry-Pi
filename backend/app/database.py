"""
数据库连接和模型定义
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from .config import settings

# 创建数据库引擎
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 检测记录表 - 存储摄像头检测结果
class DetectionRecord(Base):
    __tablename__ = "detection_records"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True, comment="设备ID")
    timestamp = Column(DateTime, default=datetime.now, comment="检测时间")
    person_count = Column(Integer, default=0, comment="检测到的人数")
    in_danger_zone = Column(Boolean, default=False, comment="是否在危险区域")
    alert_triggered = Column(Boolean, default=False, comment="是否触发报警")
    image_path = Column(String(255), nullable=True, comment="截图路径")
    details = Column(Text, nullable=True, comment="详细信息JSON")


# 传感器数据表 - 存储温度、压力等传感器数据
class SensorData(Base):
    __tablename__ = "sensor_data"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True, comment="设备ID")
    sensor_type = Column(String(20), comment="传感器类型: temperature/pressure/humidity")
    timestamp = Column(DateTime, default=datetime.now, comment="采集时间")
    value = Column(Float, comment="传感器值")
    unit = Column(String(10), comment="单位")


# 生产状态表 - 存储当前生产线状态
class ProductionStatus(Base):
    __tablename__ = "production_status"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, index=True, comment="设备ID")
    status = Column(String(20), default="stopped", comment="状态: running/stopped/paused")
    mode = Column(String(20), default="product_a", comment="生产模式: product_a/product_b")
    production_count = Column(Integer, default=0, comment="累计生产数量")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# 报警记录表
class AlertRecord(Base):
    __tablename__ = "alert_records"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True, comment="设备ID")
    alert_type = Column(String(20), comment="报警类型: intrusion/temperature/pressure/zone_enter/zone_exit")
    timestamp = Column(DateTime, default=datetime.now, comment="报警时间")
    message = Column(String(255), comment="报警信息")
    level = Column(String(10), default="warning", comment="级别: info/warning/danger")
    resolved = Column(Boolean, default=False, comment="是否已处理")


# 危险区域统计表 - 存储危险区域进入/离开统计
class ZoneStatistics(Base):
    __tablename__ = "zone_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, index=True, comment="设备ID")
    total_entries = Column(Integer, default=0, comment="总进入次数")
    total_exits = Column(Integer, default=0, comment="总离开次数")
    current_in_danger = Column(Integer, default=0, comment="当前危险区人数")
    last_entry_time = Column(DateTime, nullable=True, comment="最后进入时间")
    last_exit_time = Column(DateTime, nullable=True, comment="最后离开时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


# 危险区域事件记录表 - 存储每次进入/离开事件的详细记录
class ZoneEventRecord(Base):
    __tablename__ = "zone_event_records"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True, comment="设备ID")
    event_type = Column(String(10), comment="事件类型: enter/exit")
    timestamp = Column(DateTime, default=datetime.now, index=True, comment="事件时间")
    person_count = Column(Integer, default=1, comment="涉及人数")
    current_in_danger = Column(Integer, default=0, comment="事件后危险区人数")
    message = Column(String(255), nullable=True, comment="事件消息")


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
    print("✓ 数据库表初始化完成")


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 数据清理功能 ====================
def cleanup_old_data(db, days_to_keep: int = 7):
    """
    清理过期数据，保留最近N天的数据
    
    Args:
        db: 数据库会话
        days_to_keep: 保留天数，默认7天
    
    Returns:
        清理的记录数
    """
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    deleted_count = 0
    
    # 清理传感器数据（数据量最大）
    result = db.query(SensorData).filter(SensorData.timestamp < cutoff_date).delete()
    deleted_count += result
    
    # 清理检测记录
    result = db.query(DetectionRecord).filter(DetectionRecord.timestamp < cutoff_date).delete()
    deleted_count += result
    
    # 清理已处理的报警记录（保留未处理的）
    result = db.query(AlertRecord).filter(
        AlertRecord.timestamp < cutoff_date,
        AlertRecord.resolved == True
    ).delete()
    deleted_count += result
    
    db.commit()
    return deleted_count


def get_data_statistics(db):
    """
    获取数据库统计信息
    
    Returns:
        各表的记录数和数据库大小
    """
    stats = {
        "sensor_data_count": db.query(SensorData).count(),
        "detection_count": db.query(DetectionRecord).count(),
        "alert_count": db.query(AlertRecord).count(),
        "zone_event_count": db.query(ZoneEventRecord).count(),
    }
    return stats


# ==================== 危险区域统计操作 ====================
def get_or_create_zone_statistics(db, device_id: str) -> ZoneStatistics:
    """获取或创建危险区域统计记录"""
    stats = db.query(ZoneStatistics).filter(
        ZoneStatistics.device_id == device_id
    ).first()
    
    if not stats:
        stats = ZoneStatistics(
            device_id=device_id,
            total_entries=0,
            total_exits=0,
            current_in_danger=0
        )
        db.add(stats)
        db.commit()
        db.refresh(stats)
    
    return stats


def update_zone_statistics(db, device_id: str, event_type: str, 
                          current_in_danger: int, message: str = None):
    """
    更新危险区域统计并记录事件
    
    Args:
        db: 数据库会话
        device_id: 设备ID
        event_type: 事件类型 (enter/exit)
        current_in_danger: 当前危险区人数
        message: 事件消息
    
    Returns:
        更新后的统计信息字典
    """
    stats = get_or_create_zone_statistics(db, device_id)
    
    if event_type == "enter":
        stats.total_entries += 1
        stats.last_entry_time = datetime.now()
    elif event_type == "exit":
        stats.total_exits += 1
        stats.last_exit_time = datetime.now()
    
    stats.current_in_danger = current_in_danger
    
    # 记录事件
    event = ZoneEventRecord(
        device_id=device_id,
        event_type=event_type,
        person_count=1,
        current_in_danger=current_in_danger,
        message=message
    )
    db.add(event)
    db.commit()
    db.refresh(stats)
    
    return {
        "total_entries": stats.total_entries,
        "total_exits": stats.total_exits,
        "current_in_danger": stats.current_in_danger,
        "last_entry_time": stats.last_entry_time.isoformat() if stats.last_entry_time else None,
        "last_exit_time": stats.last_exit_time.isoformat() if stats.last_exit_time else None
    }


def reset_zone_statistics(db, device_id: str, clear_events: bool = False):
    """
    重置危险区域统计
    
    Args:
        db: 数据库会话
        device_id: 设备ID
        clear_events: 是否同时清除事件记录
    
    Returns:
        重置后的统计信息
    """
    stats = get_or_create_zone_statistics(db, device_id)
    
    stats.total_entries = 0
    stats.total_exits = 0
    stats.current_in_danger = 0
    stats.last_entry_time = None
    stats.last_exit_time = None
    
    if clear_events:
        db.query(ZoneEventRecord).filter(
            ZoneEventRecord.device_id == device_id
        ).delete()
    
    db.commit()
    db.refresh(stats)
    
    return {
        "total_entries": 0,
        "total_exits": 0,
        "current_in_danger": 0,
        "last_entry_time": None,
        "last_exit_time": None
    }


def get_zone_event_history(db, device_id: str, limit: int = 100, 
                           hours: int = None) -> list:
    """
    获取危险区域事件历史
    
    Args:
        db: 数据库会话
        device_id: 设备ID
        limit: 返回记录数限制
        hours: 只返回最近N小时的记录
    
    Returns:
        事件记录列表
    """
    query = db.query(ZoneEventRecord).filter(
        ZoneEventRecord.device_id == device_id
    )
    
    if hours:
        since = datetime.now() - timedelta(hours=hours)
        query = query.filter(ZoneEventRecord.timestamp >= since)
    
    events = query.order_by(ZoneEventRecord.timestamp.desc()).limit(limit).all()
    
    return [{
        "id": e.id,
        "event_type": e.event_type,
        "timestamp": e.timestamp.isoformat(),
        "person_count": e.person_count,
        "current_in_danger": e.current_in_danger,
        "message": e.message
    } for e in events]
