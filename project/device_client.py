"""
树莓派设备客户端 - 与后端服务器通信
这个文件在树莓派和模拟器上使用相同的接口

使用方法:
    from device_client import DeviceClient
    
    client = DeviceClient("http://服务器IP:8000", "device_001")
    client.report_detection(person_count=1, in_danger_zone=True, alert_triggered=True)
    client.report_sensor("temperature", 65.5, "°C")
"""
import requests
import json
from typing import Optional, Dict, Any
import threading


class DeviceClient:
    """
    设备客户端 - 用于与后端服务器通信
    
    支持同步调用（适合树莓派）
    """
    
    def __init__(self, server_url: str, device_id: str):
        """
        初始化设备客户端
        
        Args:
            server_url: 后端服务器地址 (如 http://192.168.1.100:8000)
            device_id: 设备唯一标识
        """
        self.server_url = server_url.rstrip('/')
        self.device_id = device_id
        self.session = requests.Session()
        self.timeout = 5  # 请求超时时间
        
        print(f"✓ 设备客户端初始化")
        print(f"  服务器: {server_url}")
        print(f"  设备ID: {device_id}")
    
    # ==================== 检测数据上报 ====================
    
    def report_detection(self, person_count: int, in_danger_zone: bool,
                        alert_triggered: bool, details: str = None) -> bool:
        """
        上报检测结果
        
        Args:
            person_count: 检测到的人数
            in_danger_zone: 是否在危险区域
            alert_triggered: 是否触发报警
            details: 详细信息（JSON字符串）
        
        Returns:
            是否上报成功
        """
        data = {
            "device_id": self.device_id,
            "person_count": person_count,
            "in_danger_zone": in_danger_zone,
            "alert_triggered": alert_triggered,
            "details": details
        }
        
        return self._post("/api/detection", data)
    
    # ==================== 传感器数据上报 ====================
    
    def report_sensor(self, sensor_type: str, value: float, unit: str = "") -> bool:
        """
        上报传感器数据
        
        Args:
            sensor_type: 传感器类型 (temperature/pressure/humidity)
            value: 传感器值
            unit: 单位
        
        Returns:
            是否上报成功
        """
        data = {
            "device_id": self.device_id,
            "sensor_type": sensor_type,
            "value": value,
            "unit": unit
        }
        
        return self._post("/api/sensor", data)
    
    def report_temperature(self, value: float) -> bool:
        """上报温度"""
        return self.report_sensor("temperature", value, "°C")
    
    def report_pressure(self, value: float) -> bool:
        """上报压力"""
        return self.report_sensor("pressure", value, "kPa")
    
    def report_humidity(self, value: float) -> bool:
        """上报湿度"""
        return self.report_sensor("humidity", value, "%")
    
    # ==================== 状态管理 ====================
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        获取当前生产状态
        
        Returns:
            {
                "device_id": str,
                "status": str,  # running/stopped/paused
                "mode": str,    # product_a/product_b
                "production_count": int
            }
        """
        return self._get(f"/api/status/{self.device_id}")
    
    def update_production_count(self, count: int) -> bool:
        """更新生产计数"""
        data = {"production_count": count}
        return self._put(f"/api/status/{self.device_id}", data)
    
    # ==================== 异步上报（不阻塞主线程） ====================
    
    def report_detection_async(self, person_count: int, in_danger_zone: bool,
                               alert_triggered: bool, details: str = None):
        """异步上报检测结果（不阻塞）"""
        thread = threading.Thread(
            target=self.report_detection,
            args=(person_count, in_danger_zone, alert_triggered, details)
        )
        thread.daemon = True
        thread.start()
    
    def report_sensor_async(self, sensor_type: str, value: float, unit: str = ""):
        """异步上报传感器数据（不阻塞）"""
        thread = threading.Thread(
            target=self.report_sensor,
            args=(sensor_type, value, unit)
        )
        thread.daemon = True
        thread.start()
    
    # ==================== HTTP请求封装 ====================
    
    def _post(self, endpoint: str, data: dict) -> bool:
        """POST请求"""
        try:
            response = self.session.post(
                f"{self.server_url}{endpoint}",
                json=data,
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            print(f"POST {endpoint} 失败: {e}")
            return False
    
    def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """GET请求"""
        try:
            response = self.session.get(
                f"{self.server_url}{endpoint}",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"GET {endpoint} 失败: {e}")
            return None
    
    def _put(self, endpoint: str, data: dict) -> bool:
        """PUT请求"""
        try:
            response = self.session.put(
                f"{self.server_url}{endpoint}",
                json=data,
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            print(f"PUT {endpoint} 失败: {e}")
            return False


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 创建客户端（修改为你的服务器地址）
    client = DeviceClient(
        server_url="http://localhost:8000",
        device_id="device_001"
    )
    
    # 测试上报检测结果
    print("\n测试上报检测结果...")
    success = client.report_detection(
        person_count=1,
        in_danger_zone=True,
        alert_triggered=True
    )
    print(f"检测上报: {'成功' if success else '失败'}")
    
    # 测试上报传感器数据
    print("\n测试上报传感器数据...")
    client.report_temperature(65.5)
    client.report_pressure(101.3)
    client.report_humidity(55.0)
    
    # 测试获取状态
    print("\n测试获取状态...")
    status = client.get_status()
    print(f"当前状态: {status}")
