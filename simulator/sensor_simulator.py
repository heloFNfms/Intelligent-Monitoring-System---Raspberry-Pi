"""
传感器模拟器 - 模拟温度、压力、湿度传感器
完全模拟树莓派传感器数据采集和上报
"""
import math
import random
from datetime import datetime
from typing import Dict, Any

from config import (
    BASE_TEMPERATURE, BASE_PRESSURE, BASE_HUMIDITY,
    TEMP_WAVE_AMPLITUDE, TEMP_NOISE_RANGE, TEMP_RUNNING_BONUS
)


class SensorSimulator:
    """传感器模拟器 - 模拟各类传感器数据"""
    
    def __init__(self):
        self.is_running = False  # 设备运行状态
        self._start_time = datetime.now()
    
    def set_running(self, running: bool):
        """设置设备运行状态（影响传感器读数）"""
        self.is_running = running
    
    def read_temperature(self) -> Dict[str, Any]:
        """
        读取温度传感器
        模拟真实传感器的波动特性
        
        Returns:
            {"value": float, "unit": str}
        """
        # 时间因子：模拟周期性波动
        elapsed = (datetime.now() - self._start_time).total_seconds()
        time_factor = elapsed / 60  # 每分钟一个周期
        
        # 正弦波动 + 随机噪声
        wave = TEMP_WAVE_AMPLITUDE * math.sin(time_factor)
        noise = random.uniform(-TEMP_NOISE_RANGE, TEMP_NOISE_RANGE)
        
        # 运行状态影响温度
        running_bonus = TEMP_RUNNING_BONUS if self.is_running else 0
        
        temperature = BASE_TEMPERATURE + wave + noise + running_bonus
        
        return {
            "value": round(temperature, 1),
            "unit": "°C"
        }
    
    def read_pressure(self) -> Dict[str, Any]:
        """
        读取压力传感器
        
        Returns:
            {"value": float, "unit": str}
        """
        noise = random.uniform(-5, 5)
        running_bonus = 20 if self.is_running else 0
        
        pressure = BASE_PRESSURE + noise + running_bonus
        
        return {
            "value": round(pressure, 1),
            "unit": "kPa"
        }
    
    def read_humidity(self) -> Dict[str, Any]:
        """
        读取湿度传感器
        
        Returns:
            {"value": float, "unit": str}
        """
        # 湿度相对稳定，小范围波动
        humidity = BASE_HUMIDITY + random.uniform(-10, 10)
        
        return {
            "value": round(humidity, 1),
            "unit": "%"
        }
    
    def read_all(self) -> Dict[str, Dict[str, Any]]:
        """
        读取所有传感器数据
        
        Returns:
            {
                "temperature": {"value": float, "unit": str},
                "pressure": {"value": float, "unit": str},
                "humidity": {"value": float, "unit": str}
            }
        """
        return {
            "temperature": self.read_temperature(),
            "pressure": self.read_pressure(),
            "humidity": self.read_humidity()
        }


# 测试
if __name__ == "__main__":
    sensor = SensorSimulator()
    
    print("传感器模拟器测试")
    print("-" * 40)
    
    # 停止状态
    sensor.set_running(False)
    data = sensor.read_all()
    print(f"停止状态: {data}")
    
    # 运行状态
    sensor.set_running(True)
    data = sensor.read_all()
    print(f"运行状态: {data}")
