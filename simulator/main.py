"""
模拟器主程序 - 模拟树莓派设备运行（仅传感器数据）
危险区域检测使用真实摄像头，请运行 project/zone_detection.py

使用方法:
    python main.py

这个模拟器模拟传感器数据：
1. 定时采集传感器数据并上报（温度、湿度、压力）
2. 定时检查服务器下发的控制指令
3. 根据运行状态更新生产计数

注意：危险区域检测已移至 project/zone_detection.py，使用真实摄像头
"""
import asyncio
import signal
import sys
from datetime import datetime

from config import (
    SERVER_URL, DEVICE_ID,
    SENSOR_INTERVAL, STATUS_CHECK_INTERVAL,
    PRODUCTION_INCREMENT
)
from sensor_simulator import SensorSimulator
from device_client import DeviceClient

import random


class DeviceSimulator:
    """
    设备模拟器 - 仅模拟传感器数据
    
    包含：
    - 传感器数据采集和上报（温度、湿度、压力）
    - 接收控制指令
    - 生产计数更新
    
    注意：危险区域检测使用真实摄像头，请运行 project/zone_detection.py
    """
    
    def __init__(self):
        # 初始化各模块（不再包含检测模拟器）
        self.sensor = SensorSimulator()
        self.client = DeviceClient(SERVER_URL, DEVICE_ID)
        
        # 设备状态
        self.status = "stopped"  # running/stopped/paused
        self.mode = "product_a"
        self.production_count = 0
        
        # 运行控制
        self.running = False
    
    async def start(self):
        """启动模拟器"""
        self.running = True
        
        print("=" * 60)
        print("🤖 传感器数据模拟器")
        print("=" * 60)
        print(f"📡 服务器地址: {SERVER_URL}")
        print(f"🔧 设备ID: {DEVICE_ID}")
        print(f"⏱️  传感器上报间隔: {SENSOR_INTERVAL}秒")
        print()
        print("📌 注意：危险区域检测请运行 project/zone_detection.py")
        print("=" * 60)
        print("按 Ctrl+C 停止模拟器")
        print()
        
        # 启动各个任务（不再包含检测循环）
        tasks = [
            asyncio.create_task(self._sensor_loop()),
            asyncio.create_task(self._status_loop()),
            asyncio.create_task(self._production_loop()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self.client.close()
            print("\n✓ 模拟器已停止")
    
    def stop(self):
        """停止模拟器"""
        self.running = False
    
    async def _sensor_loop(self):
        """传感器数据采集和上报循环"""
        while self.running:
            try:
                # 读取所有传感器
                data = self.sensor.read_all()
                
                # 上报各传感器数据
                for sensor_type, reading in data.items():
                    success = await self.client.report_sensor(
                        sensor_type, 
                        reading["value"], 
                        reading["unit"]
                    )
                    
                    if success:
                        print(f"📊 {sensor_type}: {reading['value']}{reading['unit']}")
                
            except Exception as e:
                print(f"❌ 传感器上报错误: {e}")
            
            await asyncio.sleep(SENSOR_INTERVAL)
    
    async def _status_loop(self):
        """状态检查循环 - 接收控制指令"""
        while self.running:
            try:
                # 从服务器获取最新状态
                server_status = await self.client.get_status()
                
                if server_status:
                    old_status = self.status
                    self.status = server_status.get("status", "stopped")
                    self.mode = server_status.get("mode", "product_a")
                    
                    # 更新传感器模拟器的运行状态
                    self.sensor.set_running(self.status == "running")
                    
                    # 状态变化时打印
                    if old_status != self.status:
                        print(f"📢 状态变更: {old_status} -> {self.status}")
                
            except Exception as e:
                pass  # 静默处理状态检查错误
            
            await asyncio.sleep(STATUS_CHECK_INTERVAL)
    
    async def _production_loop(self):
        """生产计数更新循环"""
        while self.running:
            try:
                if self.status == "running":
                    # 模拟生产：随机增加产品数量
                    increment = random.randint(*PRODUCTION_INCREMENT)
                    self.production_count += increment
                    
                    # 上报生产计数
                    success = await self.client.update_production_count(
                        self.production_count
                    )
                    
                    if success:
                        print(f"�icing 生产: +{increment} 总计={self.production_count}")
                
            except Exception as e:
                print(f"❌ 生产计数更新错误: {e}")
            
            await asyncio.sleep(STATUS_CHECK_INTERVAL)


async def main():
    """主函数"""
    simulator = DeviceSimulator()
    
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n\n收到停止信号...")
        simulator.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    await simulator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
