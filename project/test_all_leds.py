"""
三个LED灯同时亮测试
接线：
  - 红色LED: GPIO22 (针脚15)
  - 蓝色LED: GPIO17 (针脚11)
  - 绿色LED: GPIO27 (针脚13)
"""

import RPi.GPIO as GPIO
import time

LED_RED = 22
LED_BLUE = 17
LED_GREEN = 27

# 初始化
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED_RED, GPIO.OUT)
GPIO.setup(LED_BLUE, GPIO.OUT)
GPIO.setup(LED_GREEN, GPIO.OUT)

print("三个LED同时亮...")
GPIO.output(LED_RED, GPIO.HIGH)
GPIO.output(LED_BLUE, GPIO.HIGH)
GPIO.output(LED_GREEN, GPIO.HIGH)

try:
    input("按回车键关闭灯...")
except KeyboardInterrupt:
    pass

GPIO.output(LED_RED, GPIO.LOW)
GPIO.output(LED_BLUE, GPIO.LOW)
GPIO.output(LED_GREEN, GPIO.LOW)
GPIO.cleanup()
print("已关闭")
