"""
设备客户端 - 与后端服务器通信
这个文件和树莓派上使用的完全一样
"""
import aiohttp
from typing import Optional, Dict, Any


class DeviceClient:
    """
    设备客户端 - 用于与后端服务器通信
    
    这个类在模拟器和真实树莓派上使用相同的代码
    只需要修改 server_url 即可切换环境
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
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """关闭连接"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # ==================== 检测数据上报 ====================
    
    async def report_detection(self, person_count: int, in_danger_zone: bool,
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
        
        return await self._post("/api/detection", data)
    
    # ==================== 传感器数据上报 ====================
    
    async def report_sensor(self, sensor_type: str, value: float, unit: str) -> bool:
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
        
        return await self._post("/api/sensor", data)
    
    async def report_temperature(self, value: float) -> bool:
        """上报温度"""
        return await self.report_sensor("temperature", value, "°C")
    
    async def report_pressure(self, value: float) -> bool:
        """上报压力"""
        return await self.report_sensor("pressure", value, "kPa")
    
    async def report_humidity(self, value: float) -> bool:
        """上报湿度"""
        return await self.report_sensor("humidity", value, "%")
    
    # ==================== 状态管理 ====================
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
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
        return await self._get(f"/api/status/{self.device_id}")
    
    async def update_production_count(self, count: int) -> bool:
        """更新生产计数"""
        data = {"production_count": count}
        return await self._put(f"/api/status/{self.device_id}", data)
    
    # ==================== HTTP请求封装 ====================
    
    async def _post(self, endpoint: str, data: dict) -> bool:
        """POST请求"""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.server_url}{endpoint}",
                json=data,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"POST {endpoint} 失败: {e}")
            return False
    
    async def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """GET请求"""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.server_url}{endpoint}",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            print(f"GET {endpoint} 失败: {e}")
            return None
    
    async def _put(self, endpoint: str, data: dict) -> bool:
        """PUT请求"""
        try:
            session = await self._get_session()
            async with session.put(
                f"{self.server_url}{endpoint}",
                json=data,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"PUT {endpoint} 失败: {e}")
            return False
