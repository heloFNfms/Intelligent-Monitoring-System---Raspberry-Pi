"""
WebSocket连接管理器 - 管理所有WebSocket连接并广播消息
"""
from fastapi import WebSocket
from typing import List, Dict
import json
from datetime import datetime


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 前端大屏连接
        self.dashboard_connections: List[WebSocket] = []
        # 设备连接（树莓派等）
        self.device_connections: Dict[str, WebSocket] = {}
    
    async def connect_dashboard(self, websocket: WebSocket):
        """前端大屏连接"""
        await websocket.accept()
        self.dashboard_connections.append(websocket)
        print(f"✓ 大屏客户端已连接，当前连接数: {len(self.dashboard_connections)}")
    
    async def connect_device(self, websocket: WebSocket, device_id: str):
        """设备连接"""
        await websocket.accept()
        self.device_connections[device_id] = websocket
        print(f"✓ 设备 {device_id} 已连接")
    
    def disconnect_dashboard(self, websocket: WebSocket):
        """断开大屏连接"""
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)
        print(f"大屏客户端已断开，当前连接数: {len(self.dashboard_connections)}")
    
    def disconnect_device(self, device_id: str):
        """断开设备连接"""
        if device_id in self.device_connections:
            del self.device_connections[device_id]
        print(f"设备 {device_id} 已断开")
    
    async def broadcast_to_dashboard(self, message: dict):
        """向所有大屏客户端广播消息"""
        if not self.dashboard_connections:
            return
        
        # 确保时间戳是字符串格式
        if 'timestamp' in message and isinstance(message['timestamp'], datetime):
            message['timestamp'] = message['timestamp'].isoformat()
        
        message_json = json.dumps(message, ensure_ascii=False, default=str)
        
        disconnected = []
        for connection in self.dashboard_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            self.disconnect_dashboard(conn)
    
    async def send_to_device(self, device_id: str, message: dict):
        """向指定设备发送消息"""
        if device_id not in self.device_connections:
            print(f"设备 {device_id} 未连接")
            return False
        
        try:
            message_json = json.dumps(message, ensure_ascii=False, default=str)
            await self.device_connections[device_id].send_text(message_json)
            return True
        except Exception as e:
            print(f"发送消息到设备 {device_id} 失败: {e}")
            self.disconnect_device(device_id)
            return False
    
    async def broadcast_sensor_update(self, device_id: str, sensor_type: str, value: float, unit: str):
        """广播传感器数据更新"""
        await self.broadcast_to_dashboard({
            "type": "sensor_update",
            "data": {
                "device_id": device_id,
                "sensor_type": sensor_type,
                "value": value,
                "unit": unit
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_detection(self, device_id: str, person_count: int, in_danger: bool, alert: bool):
        """广播检测结果"""
        await self.broadcast_to_dashboard({
            "type": "detection",
            "data": {
                "device_id": device_id,
                "person_count": person_count,
                "in_danger_zone": in_danger,
                "alert_triggered": alert
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_alert(self, device_id: str, alert_type: str, message: str, level: str):
        """广播报警信息"""
        await self.broadcast_to_dashboard({
            "type": "alert",
            "data": {
                "device_id": device_id,
                "alert_type": alert_type,
                "message": message,
                "level": level
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_status_change(self, device_id: str, status: str, mode: str, count: int):
        """广播生产状态变化"""
        await self.broadcast_to_dashboard({
            "type": "status_change",
            "data": {
                "device_id": device_id,
                "status": status,
                "mode": mode,
                "production_count": count
            },
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_led_status(self, device_id: str, led_type: str, state: bool):
        """
        广播LED状态变化
        
        Args:
            device_id: 设备ID
            led_type: LED类型 (alert/product_a/product_b/running)
            state: 状态 (True=亮, False=灭)
        """
        await self.broadcast_to_dashboard({
            "type": "led_status",
            "data": {
                "device_id": device_id,
                "led_type": led_type,
                "state": state
            },
            "timestamp": datetime.now().isoformat()
        })


# 全局连接管理器实例
manager = ConnectionManager()
