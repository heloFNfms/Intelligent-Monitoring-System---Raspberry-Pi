"""
数据库连接和模型定义
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
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
    alert_type = Column(String(20), comment="报警类型: intrusion/temperature/pressure")
    timestamp = Column(DateTime, default=datetime.now, comment="报警时间")
    message = Column(String(255), comment="报警信息")
    level = Column(String(10), default="warning", comment="级别: info/warning/danger")
    resolved = Column(Boolean, default=False, comment="是否已处理")


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
    from datetime import timedelta
    
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
    }
    return stats
