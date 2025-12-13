"""
YOLOv8 区域检测系统 - 树莓派/Windows 跨平台版
功能：
1. 检测人员是否进入危险区域（屏幕右半部分），越线即报警
2. 通过HTTP API上报检测结果到后端
3. 通过WebSocket推送视频流到前端

优化：降低分辨率、跳帧检测、使用YOLOv8n、减少绘制开销
特性：无需交互，启动后自动运行，预设危险区域为屏幕右半部分
"""

import cv2
import numpy as np
from ultralytics import YOLO
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Callable, Optional
import time
import threading
import platform
import subprocess
import base64
import json
import asyncio
import aiohttp

# 检测操作系统
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    import winsound

# ==================== 服务器配置 ====================
SERVER_URL = "http://localhost:8000"  # 后端服务器地址
DEVICE_ID = "device_001"              # 设备ID
ENABLE_SERVER_REPORT = True           # 是否启用数据上报
ENABLE_VIDEO_STREAM = True            # 是否启用视频流推送
VIDEO_STREAM_FPS = 10                 # 视频流帧率（降低以减少带宽）
VIDEO_QUALITY = 50                    # JPEG压缩质量（1-100）


@dataclass
class AlertInfo:
    """警报信息"""
    timestamp: str
    zone_type: str
    person_count: int
    message: str
    bbox: Tuple[int, int, int, int]


class ServerClient:
    """服务器通信客户端"""
    
    def __init__(self, server_url: str, device_id: str):
        self.server_url = server_url.rstrip('/')
        self.device_id = device_id
        self._session = None
        self._ws = None
        self._ws_connected = False
        self._loop = None
    
    def _get_loop(self):
        """获取或创建事件循环"""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def report_detection_sync(self, person_count: int, in_danger_zone: bool, alert_triggered: bool):
        """同步方式上报检测结果（在单独线程中调用）"""
        import requests
        try:
            data = {
                "device_id": self.device_id,
                "person_count": person_count,
                "in_danger_zone": in_danger_zone,
                "alert_triggered": alert_triggered
            }
            response = requests.post(
                f"{self.server_url}/api/detection",
                json=data,
                timeout=2
            )
            return response.status_code == 200
        except Exception as e:
            return False
    
    def send_video_frame_sync(self, frame: np.ndarray, detection_info: dict = None):
        """同步方式发送视频帧（通过HTTP）"""
        import requests
        try:
            # 压缩图像为JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), VIDEO_QUALITY]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            data = {
                "device_id": self.device_id,
                "frame": frame_base64,
                "timestamp": datetime.now().isoformat(),
                "detection": detection_info
            }
            
            response = requests.post(
                f"{self.server_url}/api/video/frame",
                json=data,
                timeout=1
            )
            return response.status_code == 200
        except Exception:
            return False


# 全局服务器客户端
server_client = None


class ZoneDetector:
    """区域检测器 - 树莓派优化版"""
    
    def __init__(self, 
                 model_path: str = "yolov8n.pt",
                 frame_skip: int = 2,
                 input_size: Tuple[int, int] = (416, 416),
                 alert_cooldown: float = 2.0):
        print("正在加载模型...")
        self.model = YOLO(model_path)
        self.model.fuse()

        self.danger_zones: List[np.ndarray] = []
        self.safe_zones: List[np.ndarray] = []
        self.alert_callback: Optional[Callable[[AlertInfo], None]] = None
        self.person_class_id = 0
        
        self.frame_skip = frame_skip
        self.frame_count = 0
        self.input_size = input_size
        self.alert_cooldown = alert_cooldown
        self.last_alert_time = {}
        
        self.last_detections = []
        self.scale_x = 1.0
        self.scale_y = 1.0
        
        # 视频流相关
        self.last_stream_time = 0
        self.stream_interval = 1.0 / VIDEO_STREAM_FPS
        
        print(f"模型加载完成 | 跳帧: {frame_skip} | 输入尺寸: {input_size}")
        
    def add_danger_zone(self, points: List[Tuple[int, int]]):
        self.danger_zones.append(np.array(points, dtype=np.int32))
        print(f"✓ 危险区域已添加: {points}")
        
    def add_safe_zone(self, points: List[Tuple[int, int]]):
        self.safe_zones.append(np.array(points, dtype=np.int32))
        print(f"✓ 安全区域已添加: {points}")
        
    def clear_zones(self):
        self.danger_zones.clear()
        self.safe_zones.clear()
        
    def set_alert_callback(self, callback: Callable[[AlertInfo], None]):
        self.alert_callback = callback
        
    def _point_in_zone(self, point: Tuple[int, int], zone: np.ndarray) -> bool:
        return cv2.pointPolygonTest(zone, point, False) >= 0
    
    def _get_person_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x1, y1, x2, y2 = bbox
        return (int((x1 + x2) / 2), int(y2))
    
    def _should_send_alert(self, zone_id: str) -> bool:
        current_time = time.time()
        if zone_id not in self.last_alert_time:
            self.last_alert_time[zone_id] = current_time
            return True
        
        if current_time - self.last_alert_time[zone_id] > self.alert_cooldown:
            self.last_alert_time[zone_id] = current_time
            return True
        return False
    
    def _check_zones(self, center: Tuple[int, int], bbox: Tuple[int, int, int, int]) -> List[AlertInfo]:
        alerts = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for i, zone in enumerate(self.danger_zones):
            if self._point_in_zone(center, zone):
                zone_id = f"danger_{i}"
                if self._should_send_alert(zone_id):
                    alert = AlertInfo(
                        timestamp=timestamp,
                        zone_type="danger",
                        person_count=1,
                        message=f"⚠️ 警告：检测到人员进入危险区域 {i+1}！",
                        bbox=bbox
                    )
                    alerts.append(alert)
                
        for i, zone in enumerate(self.safe_zones):
            if self._point_in_zone(center, zone):
                alert = AlertInfo(
                    timestamp=timestamp,
                    zone_type="safe",
                    person_count=1,
                    message=f"✓ 人员在安全区域 {i+1}",
                    bbox=bbox
                )
                alerts.append(alert)
                
        return alerts


    def detect_frame(self, frame: np.ndarray, conf_threshold: float = 0.5) -> Tuple[np.ndarray, List[AlertInfo], dict]:
        """
        检测单帧图像
        
        Returns:
            处理后的图像、警报列表、检测信息字典
        """
        all_alerts = []
        h_orig, w_orig = frame.shape[:2]
        
        self.frame_count += 1
        should_detect = (self.frame_count % self.frame_skip == 0)
        
        if should_detect:
            if self.input_size:
                resized = cv2.resize(frame, self.input_size)
                self.scale_x = w_orig / self.input_size[0]
                self.scale_y = h_orig / self.input_size[1]
            else:
                resized = frame
                self.scale_x = 1.0
                self.scale_y = 1.0
            
            results = self.model(resized, conf=conf_threshold, classes=[self.person_class_id], 
                               verbose=False, device='cpu')
            
            self.last_detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    conf = float(box.conf[0])
                    
                    x1 = int(x1 * self.scale_x)
                    y1 = int(y1 * self.scale_y)
                    x2 = int(x2 * self.scale_x)
                    y2 = int(y2 * self.scale_y)
                    
                    self.last_detections.append((x1, y1, x2, y2, conf))
        
        danger_count = 0
        person_count = len(self.last_detections)
        in_danger_zone = False
        
        # 绘制区域
        if len(self.danger_zones) > 0 or len(self.safe_zones) > 0:
            overlay = frame.copy()
            
            for zone in self.danger_zones:
                cv2.fillPoly(overlay, [zone], (0, 0, 200))
                cv2.polylines(frame, [zone], True, (0, 0, 255), 2)
                
            for zone in self.safe_zones:
                cv2.fillPoly(overlay, [zone], (0, 200, 0))
                cv2.polylines(frame, [zone], True, (0, 255, 0), 2)
                
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        
        # 绘制中线警戒线
        mid_x = w_orig // 2
        cv2.line(frame, (mid_x, 0), (mid_x, h_orig), (0, 255, 255), 2)
        cv2.putText(frame, "WARNING LINE", (mid_x + 10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # 处理检测结果
        for detection in self.last_detections:
            x1, y1, x2, y2, conf = detection
            bbox = (x1, y1, x2, y2)
            center = self._get_person_center(bbox)
            
            if should_detect:
                alerts = self._check_zones(center, bbox)
                all_alerts.extend(alerts)
            
            in_danger = any(self._point_in_zone(center, zone) for zone in self.danger_zones)
            
            if in_danger:
                danger_count += 1
                in_danger_zone = True
                color = (0, 0, 255)
                label = "DANGER!"
            else:
                color = (0, 255, 0)
                label = "Person"
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.circle(frame, center, 4, color, -1)
        
        # 显示警告信息
        if danger_count > 0:
            warning_text = f"WARNING: {danger_count} in DANGER ZONE!"
            cv2.putText(frame, warning_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # 显示人数统计
        cv2.putText(frame, f"Persons: {person_count}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
        # 触发回调
        if should_detect:
            for alert in all_alerts:
                if alert.zone_type == "danger" and self.alert_callback:
                    self.alert_callback(alert)
        
        # 检测信息
        detection_info = {
            "person_count": person_count,
            "in_danger_zone": in_danger_zone,
            "alert_triggered": danger_count > 0 and should_detect,
            "danger_count": danger_count
        }
                
        return frame, all_alerts, detection_info

    def run_camera(self, 
                   camera_id: int = 0, 
                   window_name: str = "Zone Detection",
                   display_fps: bool = True,
                   camera_width: int = 640,
                   camera_height: int = 480,
                   headless: bool = False):
        """运行摄像头检测"""
        global server_client
        
        cap = cv2.VideoCapture(camera_id)
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not cap.isOpened():
            print("错误：无法打开摄像头")
            return
            
        print("="*60)
        print("🚀 区域检测系统已启动")
        print(f"📹 摄像头: {camera_id} | 分辨率: {camera_width}x{camera_height}")
        print(f"⚠️  危险区域数量: {len(self.danger_zones)}")
        print(f"✅ 安全区域数量: {len(self.safe_zones)}")
        if ENABLE_SERVER_REPORT:
            print(f"📡 数据上报: {SERVER_URL}")
        if ENABLE_VIDEO_STREAM:
            print(f"📺 视频流: 已启用 ({VIDEO_STREAM_FPS} FPS)")
        print("按 'q' 键退出程序")
        print("="*60)
        
        fps_start_time = time.time()
        fps_frame_count = 0
        fps = 0
        
        if not headless:
            cv2.namedWindow(window_name)
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("错误：无法读取帧")
                    break
                
                # 检测
                processed_frame, alerts, detection_info = self.detect_frame(frame)
                
                # 上报检测结果到服务器
                if ENABLE_SERVER_REPORT and detection_info["alert_triggered"]:
                    self._report_to_server(detection_info)
                
                # 推送视频流
                if ENABLE_VIDEO_STREAM:
                    self._stream_video_frame(processed_frame, detection_info)
                
                # 计算FPS
                if display_fps:
                    fps_frame_count += 1
                    if fps_frame_count >= 10:
                        fps = fps_frame_count / (time.time() - fps_start_time)
                        fps_start_time = time.time()
                        fps_frame_count = 0
                    
                    cv2.putText(processed_frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                if not headless:
                    cv2.imshow(window_name, processed_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        print("\n正在退出...")
                        break
                else:
                    time.sleep(0.01)
                    
        except KeyboardInterrupt:
            print("\n\n收到中断信号，正在退出...")
        finally:
            cap.release()
            if not headless:
                cv2.destroyAllWindows()
            print("✓ 程序已安全退出")
    
    def _report_to_server(self, detection_info: dict):
        """上报检测结果到服务器（异步）"""
        global server_client
        if server_client:
            def _report():
                server_client.report_detection_sync(
                    person_count=detection_info["person_count"],
                    in_danger_zone=detection_info["in_danger_zone"],
                    alert_triggered=detection_info["alert_triggered"]
                )
            thread = threading.Thread(target=_report)
            thread.daemon = True
            thread.start()
    
    def _stream_video_frame(self, frame: np.ndarray, detection_info: dict):
        """推送视频帧（限制帧率）"""
        global server_client
        current_time = time.time()
        
        if current_time - self.last_stream_time >= self.stream_interval:
            self.last_stream_time = current_time
            
            if server_client:
                def _stream():
                    server_client.send_video_frame_sync(frame, detection_info)
                thread = threading.Thread(target=_stream)
                thread.daemon = True
                thread.start()



# GPIO控制类（树莓派LED和蜂鸣器控制）
class GPIOController:
    """GPIO控制器 - 管理LED和蜂鸣器"""
    
    def __init__(self, led_pin: int = 16, buzzer_pin: int = 18):
        self.led_pin = led_pin
        self.buzzer_pin = buzzer_pin
        self.gpio_initialized = False
        self.led_state = False
        
        if IS_LINUX:
            try:
                import RPi.GPIO as GPIO
                self.GPIO = GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                
                GPIO.setup(self.led_pin, GPIO.OUT)
                GPIO.output(self.led_pin, GPIO.LOW)
                
                GPIO.setup(self.buzzer_pin, GPIO.OUT)
                GPIO.output(self.buzzer_pin, GPIO.LOW)
                
                self.gpio_initialized = True
                print(f"✓ GPIO初始化成功 | LED引脚: {led_pin} | 蜂鸣器引脚: {buzzer_pin}")
                
            except ImportError:
                print("⚠️ RPi.GPIO未安装，LED和蜂鸣器功能将被禁用")
            except Exception as e:
                print(f"⚠️ GPIO初始化失败: {e}")
    
    def turn_on_led(self):
        if self.gpio_initialized and not self.led_state:
            try:
                self.GPIO.output(self.led_pin, self.GPIO.HIGH)
                self.led_state = True
                print("🔴 LED已点亮")
            except Exception as e:
                print(f"LED点亮失败: {e}")
    
    def turn_off_led(self):
        if self.gpio_initialized and self.led_state:
            try:
                self.GPIO.output(self.led_pin, self.GPIO.LOW)
                self.led_state = False
                print("⚫ LED已熄灭")
            except Exception as e:
                print(f"LED熄灭失败: {e}")
    
    def buzzer_beep(self, duration: float = 0.5):
        if self.gpio_initialized:
            try:
                self.GPIO.output(self.buzzer_pin, self.GPIO.HIGH)
                time.sleep(duration)
                self.GPIO.output(self.buzzer_pin, self.GPIO.LOW)
            except Exception as e:
                print(f"蜂鸣器响声失败: {e}")
    
    def cleanup(self):
        if self.gpio_initialized:
            try:
                self.GPIO.cleanup()
                print("✓ GPIO资源已清理")
            except Exception as e:
                print(f"GPIO清理失败: {e}")


# 全局GPIO控制器实例
gpio_controller = None


def play_alarm_sound():
    """播放报警声音（跨平台支持）"""
    global gpio_controller
    
    try:
        if IS_WINDOWS:
            winsound.Beep(1000, 500)
        elif IS_LINUX:
            try:
                subprocess.run(['aplay', '-q', '/usr/share/sounds/alsa/Front_Center.wav'], 
                             timeout=2, check=False)
            except FileNotFoundError:
                pass
            
            if gpio_controller:
                gpio_controller.buzzer_beep(0.5)
            
            print('\a')
    except Exception as e:
        print(f"报警声音播放失败: {e}")


def control_led_alarm():
    """控制LED报警灯"""
    global gpio_controller
    
    if gpio_controller:
        gpio_controller.turn_on_led()
        
        def auto_turn_off():
            time.sleep(3.0)
            gpio_controller.turn_off_led()
        
        led_thread = threading.Thread(target=auto_turn_off)
        led_thread.start()


def alert_handler(alert: AlertInfo):
    """默认警报处理函数 - 越线报警"""
    if alert.zone_type == "danger":
        print(f"\n{'='*50}")
        print(f"🚨 {alert.timestamp} - {alert.message}")
        print(f"⚠️  警告：有人越过警戒线！")
        print(f"📍 位置: {alert.bbox}")
        print(f"{'='*50}\n")
        
        # 播放报警声
        alarm_thread = threading.Thread(target=play_alarm_sound)
        alarm_thread.start()
        
        # 控制LED
        led_thread = threading.Thread(target=control_led_alarm)
        led_thread.start()


# 使用示例
if __name__ == "__main__":
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    
    # 初始化服务器客户端
    if ENABLE_SERVER_REPORT or ENABLE_VIDEO_STREAM:
        server_client = ServerClient(SERVER_URL, DEVICE_ID)
        print(f"✓ 服务器客户端已初始化: {SERVER_URL}")
    
    # 初始化GPIO控制器
    gpio_controller = GPIOController(led_pin=16, buzzer_pin=18)
    
    # 创建检测器
    detector = ZoneDetector(
        model_path="yolov8n.pt",
        frame_skip=3,
        input_size=(320, 320),
        alert_cooldown=3.0
    )
    
    # 设置警报回调
    detector.set_alert_callback(alert_handler)
    
    # 配置危险区域（屏幕右半部分）
    detector.add_danger_zone([
        (CAMERA_WIDTH // 2, 0),
        (CAMERA_WIDTH, 0),
        (CAMERA_WIDTH, CAMERA_HEIGHT),
        (CAMERA_WIDTH // 2, CAMERA_HEIGHT)
    ])
    
    # 配置安全区域（屏幕左半部分）
    detector.add_safe_zone([
        (0, 0),
        (CAMERA_WIDTH // 2, 0),
        (CAMERA_WIDTH // 2, CAMERA_HEIGHT),
        (0, CAMERA_HEIGHT)
    ])
    
    print("\n" + "="*60)
    print("⚠️  危险区域：屏幕右半部分")
    print("✅ 安全区域：屏幕左半部分")
    print("📍 警戒线：屏幕中央垂直线")
    print("🚨 越过警戒线进入右侧区域将触发报警！")
    print("="*60 + "\n")
    
    try:
        detector.run_camera(
            camera_id=0,
            camera_width=CAMERA_WIDTH,
            camera_height=CAMERA_HEIGHT,
            display_fps=True,
            headless=False
        )
    finally:
        if gpio_controller:
            gpio_controller.cleanup()
