"""
模拟器主程序 - 模拟树莓派设备运行
仅负责传感器数据模拟

使用方法:
    python main.py

这个模拟器模拟：
1. 传感器数据采集和上报（温度、湿度、压力）
2. 接收服务器下发的控制指令
3. 同步生产状态

注意：
- 传送带和生产计数由后端统一管理，避免重复计算
- 危险区域检测使用真实摄像头，请运行 project/zone_detection.py
"""
import asyncio
import signal
import time
import random

from config import (
    SERVER_URL, DEVICE_ID,
    SENSOR_INTERVAL, STATUS_CHECK_INTERVAL,
    PRODUCTION_INCREMENT
)
from sensor_simulator import SensorSimulator
from device_client import DeviceClient


class DeviceSimulator:
    """
    设备模拟器 - 仅模拟传感器数据
    
    包含：
    - 传感器数据采集和上报（温度、湿度、压力）
    - 接收控制指令
    - 同步生产状态
    
    注意：传送带和生产计数由后端管理
    """
    
    def __init__(self):
        # 初始化各模块
        self.sensor = SensorSimulator()
        self.client = DeviceClient(SERVER_URL, DEVICE_ID)
        
        # 设备状态
        self.status = "stopped"
        self.mode = "product_a"
        self.production_count = 0
        
        # 运行控制
        self.running = False
    
    async def start(self):
        """启动模拟器"""
        self.running = True
        
        print("=" * 60)
        print("🤖 智能生产线模拟器")
        print("=" * 60)
        print(f"📡 服务器地址: {SERVER_URL}")
        print(f"🔧 设备ID: {DEVICE_ID}")
        print(f"⏱️  传感器上报间隔: {SENSOR_INTERVAL}秒")
        print()
        print("📌 功能：传感器数据模拟（传送带由后端管理）")
        print("📌 危险区域检测请运行 project/zone_detection.py")
        print("=" * 60)
        print("按 Ctrl+C 停止模拟器")
        print()
        
        # 启动各个任务
        # 注意：传送带和生产计数由后端管理，simulator只负责传感器数据
        tasks = [
            asyncio.create_task(self._sensor_loop()),
            asyncio.create_task(self._status_loop()),
            asyncio.create_task(self._sync_production_count()),
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
                data = self.sensor.read_all()
                
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
                server_status = await self.client.get_status()
                
                if server_status:
                    old_status = self.status
                    self.status = server_status.get("status", "stopped")
                    self.mode = server_status.get("mode", "product_a")
                    
                    # 更新传感器状态（传送带由后端管理）
                    self.sensor.set_running(self.status == "running")
                    
                    if old_status != self.status:
                        print(f"📢 状态变更: {old_status} -> {self.status}")
                
            except Exception as e:
                pass
            
            await asyncio.sleep(STATUS_CHECK_INTERVAL)
    
    async def _sync_production_count(self):
        """同步生产计数（从服务器获取，避免重复计算）"""
        while self.running:
            try:
                server_status = await self.client.get_status()
                if server_status:
                    self.production_count = server_status.get("production_count", 0)
            except Exception as e:
                pass
            
            await asyncio.sleep(STATUS_CHECK_INTERVAL * 2)


async def main():
    """主函数"""
    simulator = DeviceSimulator()
    
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
