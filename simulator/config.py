"""
模拟器配置 - 模拟树莓派设备
"""

# 后端服务器地址（和真实树莓派使用相同配置）
SERVER_URL = "http://localhost:8000"

# 设备ID（模拟的设备标识）
DEVICE_ID = "device_001"

# 数据上报间隔（秒）
SENSOR_INTERVAL = 3      # 传感器数据上报间隔
DETECTION_INTERVAL = 5   # 检测数据上报间隔
STATUS_CHECK_INTERVAL = 2  # 状态检查间隔

# 模拟参数
DANGER_ZONE_PROBABILITY = 0.1  # 10%概率模拟危险区域入侵
PRODUCTION_INCREMENT = (1, 3)   # 每次生产增量范围

# 传感器基准值
BASE_TEMPERATURE = 45.0   # 基础温度
BASE_PRESSURE = 101.3     # 基础压力 kPa
BASE_HUMIDITY = 55.0      # 基础湿度 %

# 温度波动参数
TEMP_WAVE_AMPLITUDE = 10  # 温度波动幅度
TEMP_NOISE_RANGE = 2      # 温度随机噪声范围
TEMP_RUNNING_BONUS = 20   # 运行时温度增加
