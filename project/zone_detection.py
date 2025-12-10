"""
YOLOv8 区域检测系统 - 树莓派/Windows 跨平台版
功能：检测人员是否进入危险区域（屏幕右半部分），越线即报警
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

# 检测操作系统
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    import winsound


@dataclass
class AlertInfo:
    """警报信息"""
    timestamp: str
    zone_type: str
    person_count: int
    message: str
    bbox: Tuple[int, int, int, int]


class ZoneDetector:
    """区域检测器 - 树莓派优化版"""
    
    def __init__(self, 
                 model_path: str = "yolov8n.pt",
                 frame_skip: int = 2,
                 input_size: Tuple[int, int] = (416, 416),
                 alert_cooldown: float = 2.0):
        """
        初始化检测器
        
        Args:
            model_path: YOLOv8模型路径（建议使用yolov8n.pt）
            frame_skip: 跳帧数，每N帧检测一次（降低CPU负载）
            input_size: 输入图像尺寸，越小越快（默认416x416）
            alert_cooldown: 警报冷却时间（秒），避免重复警报
        """
        print("正在加载模型...")
        self.model = YOLO(model_path)
        self.model.fuse()  # 融合模型层以提升速度

        self.danger_zones: List[np.ndarray] = []
        self.safe_zones: List[np.ndarray] = []
        self.alert_callback: Optional[Callable[[AlertInfo], None]] = None
        self.person_class_id = 0
        
        # 性能优化参数
        self.frame_skip = frame_skip
        self.frame_count = 0
        self.input_size = input_size
        self.alert_cooldown = alert_cooldown
        self.last_alert_time = {}
        
        # 缓存变量
        self.last_detections = []
        self.scale_x = 1.0
        self.scale_y = 1.0
        
        print(f"模型加载完成 | 跳帧: {frame_skip} | 输入尺寸: {input_size}")
        
    def add_danger_zone(self, points: List[Tuple[int, int]]):
        """添加危险区域"""
        self.danger_zones.append(np.array(points, dtype=np.int32))
        print(f"✓ 危险区域已添加: {points}")
        
    def add_safe_zone(self, points: List[Tuple[int, int]]):
        """添加安全区域"""
        self.safe_zones.append(np.array(points, dtype=np.int32))
        print(f"✓ 安全区域已添加: {points}")
        
    def clear_zones(self):
        """清除所有区域"""
        self.danger_zones.clear()
        self.safe_zones.clear()
        
    def set_alert_callback(self, callback: Callable[[AlertInfo], None]):
        """设置警报回调函数"""
        self.alert_callback = callback
        
    def _point_in_zone(self, point: Tuple[int, int], zone: np.ndarray) -> bool:
        """检查点是否在区域内"""
        return cv2.pointPolygonTest(zone, point, False) >= 0
    
    def _get_person_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """获取人员边界框的底部中心点"""
        x1, y1, x2, y2 = bbox
        return (int((x1 + x2) / 2), int(y2))
    
    def _should_send_alert(self, zone_id: str) -> bool:
        """检查是否应该发送警报（考虑冷却时间）"""
        current_time = time.time()
        if zone_id not in self.last_alert_time:
            self.last_alert_time[zone_id] = current_time
            return True
        
        if current_time - self.last_alert_time[zone_id] > self.alert_cooldown:
            self.last_alert_time[zone_id] = current_time
            return True
        return False
    
    def _check_zones(self, center: Tuple[int, int], bbox: Tuple[int, int, int, int]) -> List[AlertInfo]:
        """检查人员位置并生成警报"""
        alerts = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 检查危险区域
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
                
        # 检查安全区域（不触发警报）
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


    def detect_frame(self, frame: np.ndarray, conf_threshold: float = 0.5) -> Tuple[np.ndarray, List[AlertInfo]]:
        """
        检测单帧图像
        
        Args:
            frame: 输入图像
            conf_threshold: 置信度阈值
            
        Returns:
            处理后的图像和警报列表
        """
        all_alerts = []
        h_orig, w_orig = frame.shape[:2]
        
        # 跳帧优化：只在指定帧执行检测
        self.frame_count += 1
        should_detect = (self.frame_count % self.frame_skip == 0)
        
        if should_detect:
            # 降低分辨率以加速推理
            if self.input_size:
                resized = cv2.resize(frame, self.input_size)
                self.scale_x = w_orig / self.input_size[0]
                self.scale_y = h_orig / self.input_size[1]
            else:
                resized = frame
                self.scale_x = 1.0
                self.scale_y = 1.0
            
            # YOLOv8检测（使用较小的输入尺寸）
            results = self.model(resized, conf=conf_threshold, classes=[self.person_class_id], 
                               verbose=False, device='cpu')  # 明确使用CPU
            
            # 保存检测结果供下一帧使用
            self.last_detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    conf = float(box.conf[0])
                    
                    # 缩放回原始尺寸
                    x1 = int(x1 * self.scale_x)
                    y1 = int(y1 * self.scale_y)
                    x2 = int(x2 * self.scale_x)
                    y2 = int(y2 * self.scale_y)
                    
                    self.last_detections.append((x1, y1, x2, y2, conf))
        
        # 使用缓存的检测结果绘制（每帧都绘制以保持流畅）
        danger_count = 0
        
        # 绘制区域（优化：预先创建mask）
        if len(self.danger_zones) > 0 or len(self.safe_zones) > 0:
            overlay = frame.copy()
            
            for zone in self.danger_zones:
                cv2.fillPoly(overlay, [zone], (0, 0, 200))
                cv2.polylines(frame, [zone], True, (0, 0, 255), 2)
                
            for zone in self.safe_zones:
                cv2.fillPoly(overlay, [zone], (0, 200, 0))
                cv2.polylines(frame, [zone], True, (0, 255, 0), 2)
                
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        
        # 处理检测结果
        for detection in self.last_detections:
            x1, y1, x2, y2, conf = detection
            bbox = (x1, y1, x2, y2)
            center = self._get_person_center(bbox)
            
            # 检查区域（只在检测帧进行）
            if should_detect:
                alerts = self._check_zones(center, bbox)
                all_alerts.extend(alerts)
            
            # 判断是否在危险区域
            in_danger = any(self._point_in_zone(center, zone) for zone in self.danger_zones)
            
            if in_danger:
                danger_count += 1
                color = (0, 0, 255)
                label = "DANGER!"
            else:
                color = (0, 255, 0)
                label = "Person"
            
            # 绘制边界框（简化版）
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.circle(frame, center, 4, color, -1)
        
        # 显示警告信息
        if danger_count > 0:
            warning_text = f"WARNING: {danger_count} in DANGER!"
            cv2.putText(frame, warning_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
        # 触发回调
        if should_detect:
            for alert in all_alerts:
                if alert.zone_type == "danger" and self.alert_callback:
                    self.alert_callback(alert)
                
        return frame, all_alerts


    def run_camera(self, 
                   camera_id: int = 0, 
                   window_name: str = "Zone Detection",
                   display_fps: bool = True,
                   camera_width: int = 640,
                   camera_height: int = 480,
                   headless: bool = False):
        """
        运行摄像头检测（自动运行模式）
        
        Args:
            camera_id: 摄像头ID
            window_name: 窗口名称
            display_fps: 是否显示FPS
            camera_width: 摄像头分辨率宽度
            camera_height: 摄像头分辨率高度
            headless: 无头模式（不显示窗口，适合后台运行）
        """
        cap = cv2.VideoCapture(camera_id)
        
        # 设置摄像头分辨率（降低以提升性能）
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
        cap.set(cv2.CAP_PROP_FPS, 30)  # 设置帧率
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 减少缓冲延迟
        
        if not cap.isOpened():
            print("错误：无法打开摄像头")
            return
            
        print("="*60)
        print("🚀 区域检测系统已启动")
        print(f"📹 摄像头: {camera_id} | 分辨率: {camera_width}x{camera_height}")
        print(f"⚠️  危险区域数量: {len(self.danger_zones)}")
        print(f"✅ 安全区域数量: {len(self.safe_zones)}")
        print("按 'q' 键退出程序")
        print("="*60)
        
        # FPS计算
        fps_start_time = time.time()
        fps_frame_count = 0
        fps = 0
        
        # 如果不是无头模式，创建窗口
        if not headless:
            cv2.namedWindow(window_name)
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("错误：无法读取帧")
                    break
                
                # 检测并绘制
                processed_frame, alerts = self.detect_frame(frame)
                
                # 计算并显示FPS
                if display_fps:
                    fps_frame_count += 1
                    if fps_frame_count >= 10:
                        fps = fps_frame_count / (time.time() - fps_start_time)
                        fps_start_time = time.time()
                        fps_frame_count = 0
                    
                    cv2.putText(processed_frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # 显示画面（如果不是无头模式）
                if not headless:
                    cv2.imshow(window_name, processed_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        print("\n正在退出...")
                        break
                else:
                    # 无头模式下，添加短暂延迟避免CPU占用过高
                    time.sleep(0.01)
                    
        except KeyboardInterrupt:
            print("\n\n收到中断信号，正在退出...")
        finally:
            cap.release()
            if not headless:
                cv2.destroyAllWindows()
            print("✓ 程序已安全退出")


def play_alarm_sound():
    """播放报警声音（跨平台支持）"""
    try:
        if IS_WINDOWS:
            # Windows系统使用winsound播放报警声
            winsound.Beep(1000, 500)  # 频率1000Hz，持续500毫秒
        elif IS_LINUX:
            # 树莓派/Linux系统使用多种方式尝试报警
            # 方式1：使用aplay播放系统声音
            try:
                subprocess.run(['aplay', '-q', '/usr/share/sounds/alsa/Front_Center.wav'], 
                             timeout=2, check=False)
            except FileNotFoundError:
                pass
            
            # 方式2：使用蜂鸣器（如果有GPIO蜂鸣器）
            # 可以取消注释以下代码启用GPIO蜂鸣器
            # try:
            #     import RPi.GPIO as GPIO
            #     BUZZER_PIN = 18
            #     GPIO.setmode(GPIO.BCM)
            #     GPIO.setup(BUZZER_PIN, GPIO.OUT)
            #     GPIO.output(BUZZER_PIN, GPIO.HIGH)
            #     time.sleep(0.5)
            #     GPIO.output(BUZZER_PIN, GPIO.LOW)
            # except ImportError:
            #     pass
            
            # 方式3：使用终端蜂鸣
            print('\a')  # 终端蜂鸣
    except Exception as e:
        print(f"报警声音播放失败: {e}")



def alert_handler(alert: AlertInfo):
    """默认警报处理函数 - 越线报警"""
    if alert.zone_type == "danger":
        print(f"\n{'='*50}")
        print(f"🚨 {alert.timestamp} - {alert.message}")
        print(f"⚠️  警告：有人越过警戒线！")
        print(f"📍 位置: {alert.bbox}")
        print(f"{'='*50}\n")
        
        # 在单独线程中播放报警声，避免阻塞主程序
        alarm_thread = threading.Thread(target=play_alarm_sound)
        alarm_thread.start()


# 使用示例
if __name__ == "__main__":
    # 摄像头分辨率设置
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    
    # 创建检测器（树莓派优化参数）
    detector = ZoneDetector(
        model_path="yolov8n.pt",      # 使用最轻量的nano模型
        frame_skip=3,                  # 每3帧检测一次（可根据性能调整）
        input_size=(320, 320),         # 较小的输入尺寸（可选：416x416）
        alert_cooldown=3.0             # 警报冷却3秒
    )
    
    # 设置警报回调（越线报警）
    detector.set_alert_callback(alert_handler)
    
    # ==================== 配置危险区域 ====================
    # 危险区域设置为屏幕右半部分
    # 当有人从左边越过中线进入右半部分时触发报警
    
    # 屏幕右半部分作为危险区域
    # 警戒线位于屏幕中央（x = CAMERA_WIDTH / 2）
    detector.add_danger_zone([
        (CAMERA_WIDTH // 2, 0),                    # 中线顶部
        (CAMERA_WIDTH, 0),                         # 右上角
        (CAMERA_WIDTH, CAMERA_HEIGHT),             # 右下角
        (CAMERA_WIDTH // 2, CAMERA_HEIGHT)         # 中线底部
    ])
    
    # 左半部分为安全区域（可选，用于显示）
    detector.add_safe_zone([
        (0, 0),                                    # 左上角
        (CAMERA_WIDTH // 2, 0),                    # 中线顶部
        (CAMERA_WIDTH // 2, CAMERA_HEIGHT),        # 中线底部
        (0, CAMERA_HEIGHT)                         # 左下角
    ])
    
    print("\n" + "="*60)
    print("⚠️  危险区域：屏幕右半部分")
    print("✅ 安全区域：屏幕左半部分")
    print("📍 警戒线：屏幕中央垂直线")
    print("🚨 越过警戒线进入右侧区域将触发报警！")
    print("="*60 + "\n")
    
    # ==================== 运行检测 ====================
    # 普通模式（显示窗口）
    detector.run_camera(
        camera_id=0,                   # 摄像头ID，通常是0
        camera_width=CAMERA_WIDTH,     # 摄像头宽度
        camera_height=CAMERA_HEIGHT,   # 摄像头高度
        display_fps=True,              # 显示FPS
        headless=False                 # False=显示窗口，True=后台运行
    )
    
    # 无头模式（适合树莓派无显示器运行）
    # detector.run_camera(
    #     camera_id=0,
    #     camera_width=CAMERA_WIDTH,
    #     camera_height=CAMERA_HEIGHT,
    #     display_fps=False,
    #     headless=True
    # )
