"""
DHT11 温湿度传感器测试脚本
接线：
  - VCC → 3.3V (针脚1)
  - DATA → GPIO4 (针脚7)
  - GND → GND (针脚6)
"""

import time
import board
import adafruit_dht

# 初始化 DHT11，连接到 GPIO4
dht_device = adafruit_dht.DHT11(board.D4)

print("DHT11 温湿度传感器测试")
print("=" * 40)
print("按 Ctrl+C 退出")
print()

try:
    while True:
        try:
            # 读取温度和湿度
            temperature = dht_device.temperature
            humidity = dht_device.humidity
            
            if temperature is not None and humidity is not None:
                print(f"温度: {temperature:.1f}°C  |  湿度: {humidity:.1f}%")
            else:
                print("读取失败，重试中...")
                
        except RuntimeError as e:
            # DHT11 读取偶尔会失败，这是正常的
            print(f"读取错误: {e}")
        
        time.sleep(2)  # DHT11 最快 2 秒读取一次

except KeyboardInterrupt:
    print("\n测试结束")
finally:
    dht_device.exit()
