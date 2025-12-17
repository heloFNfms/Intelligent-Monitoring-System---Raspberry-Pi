"""
硬件测试脚本 - 测试 LED、DHT11、蜂鸣器
接线：
  - DHT11: VCC→针脚1(3.3V), DATA→针脚7(GPIO4), GND→针脚6
  - 红色LED: 长脚→针脚15(GPIO22), 短脚→针脚20(GND) - 环境异常
  - 蓝色LED: 长脚→针脚11(GPIO17), 短脚→针脚9(GND) - 危险区域有人
  - 绿色LED: 长脚→针脚13(GPIO27), 短脚→针脚14(GND) - 正常
  - USB蜂鸣器: 插USB口
"""

import time
import RPi.GPIO as GPIO

# GPIO 设置
LED_RED = 22    # 红色LED - 环境异常
LED_BLUE = 17   # 蓝色LED - 危险区域有人
LED_GREEN = 27  # 绿色LED - 正常

def setup_gpio():
    """初始化 GPIO"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LED_RED, GPIO.OUT)
    GPIO.setup(LED_BLUE, GPIO.OUT)
    GPIO.setup(LED_GREEN, GPIO.OUT)
    GPIO.output(LED_RED, GPIO.LOW)
    GPIO.output(LED_BLUE, GPIO.LOW)
    GPIO.output(LED_GREEN, GPIO.LOW)
    print("✓ GPIO 初始化完成")

def test_led():
    """测试 LED"""
    print("\n" + "="*40)
    print("测试 LED 灯")
    print("="*40)
    
    print("→ 红色LED 亮（环境异常）...")
    GPIO.output(LED_RED, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(LED_RED, GPIO.LOW)
    print("→ 红色LED 灭")
    
    time.sleep(0.5)
    
    print("→ 蓝色LED 亮（危险区域有人）...")
    GPIO.output(LED_BLUE, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(LED_BLUE, GPIO.LOW)
    print("→ 蓝色LED 灭")
    
    time.sleep(0.5)
    
    print("→ 绿色LED 亮（正常）...")
    GPIO.output(LED_GREEN, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(LED_GREEN, GPIO.LOW)
    print("→ 绿色LED 灭")
    
    time.sleep(0.5)
    
    print("→ 三个LED 同时亮...")
    GPIO.output(LED_RED, GPIO.HIGH)
    GPIO.output(LED_BLUE, GPIO.HIGH)
    GPIO.output(LED_GREEN, GPIO.HIGH)
    time.sleep(1)
    GPIO.output(LED_RED, GPIO.LOW)
    GPIO.output(LED_BLUE, GPIO.LOW)
    GPIO.output(LED_GREEN, GPIO.LOW)
    print("→ 三个LED 同时灭")
    
    print("✓ LED 测试完成")

def test_dht11():
    """测试 DHT11 温湿度传感器"""
    print("\n" + "="*40)
    print("测试 DHT11 温湿度传感器")
    print("="*40)
    
    try:
        import board
        import adafruit_dht
        
        dht = adafruit_dht.DHT11(board.D4)
        
        print("读取温湿度数据（3次）...")
        for i in range(3):
            try:
                temp = dht.temperature
                humidity = dht.humidity
                if temp is not None and humidity is not None:
                    print(f"  [{i+1}] 温度: {temp:.1f}°C | 湿度: {humidity:.1f}%")
                else:
                    print(f"  [{i+1}] 读取失败，重试...")
            except RuntimeError as e:
                print(f"  [{i+1}] 错误: {e}")
            time.sleep(2)
        
        dht.exit()
        print("✓ DHT11 测试完成")
        
    except ImportError:
        print("❌ DHT11 库未安装，请运行: pip install adafruit-circuitpython-dht")

def test_buzzer():
    """测试 USB 蜂鸣器"""
    print("\n" + "="*40)
    print("测试 USB 蜂鸣器")
    print("="*40)
    
    import subprocess
    
    print("→ 播放系统声音...")
    try:
        # 尝试播放系统声音
        result = subprocess.run(
            ['aplay', '/usr/share/sounds/alsa/Front_Center.wav'],
            timeout=5,
            capture_output=True
        )
        if result.returncode == 0:
            print("✓ 蜂鸣器测试完成（如果听到声音）")
        else:
            print("⚠️ 播放失败，尝试其他方式...")
            print('\a')  # 终端蜂鸣
    except FileNotFoundError:
        print("⚠️ 声音文件不存在，尝试终端蜂鸣...")
        print('\a')
    except Exception as e:
        print(f"⚠️ 蜂鸣器测试失败: {e}")

def main():
    print("\n" + "="*50)
    print("🔧 树莓派硬件测试")
    print("="*50)
    
    try:
        setup_gpio()
        test_led()
        test_dht11()
        test_buzzer()
        
        print("\n" + "="*50)
        print("✅ 所有测试完成！")
        print("="*50)
        
    except KeyboardInterrupt:
        print("\n测试中断")
    finally:
        GPIO.cleanup()
        print("✓ GPIO 已清理")

if __name__ == "__main__":
    main()
