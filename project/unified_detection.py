"""
统一检测系统 - 整合危险区域检测和产品检测
功能：
1. 默认运行危险区域检测（人员安全监控）
2. 支持切换到产品检测模式（颜色/形状识别）
3. 通过后端API或键盘控制模式切换
4. 共享同一个摄像头，避免资源冲突
5. 人员进入/离开危险区域的状态追踪和统计

适用于：树莓派 / Windows 笔记本
"""

import cv2
import numpy as np
from ultralytics import YOLO
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Tuple, Callable, Optional, Dict, Set
from enum import Enum
import time
import threading
import platform
import subprocess
import base64
import requests
import uuid

# ==================== 系统检测 ====================
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    import winsound

# 尝试导入 picamera2（树莓派CSI摄像头）
PICAMERA2_AVAILABLE = False
if IS_LINUX:
    try:
        from picamera2 import Picamera2
        PICAMERA2_AVAILABLE = True
        print("✓ picamera2 可用")
    except ImportError:
        print("⚠️ picamera2 不可用，将尝试其他方式打开摄像头")

# 尝试导入 DHT11 温湿度传感器
DHT_AVAILABLE = False
if IS_LINUX:
    try:
        import board
        import adafruit_dht
        DHT_AVAILABLE = True
        print("✓ DHT11 传感器库可用")
    except ImportError:
        print("⚠️ DHT11 库不可用，温湿度功能禁用")

# ==================== 配置 ====================
SERVER_URL = "http://localhost:8000"
"树莓派使用"
#SERVER_URL = "http://192.168.137.1:8000"

DEVICE_ID = "device_001"
ENABLE_SERVER_REPORT = True
ENABLE_VIDEO_STREAM = True
VIDEO_STREAM_FPS = 10
VIDEO_QUALITY = 50

# 树莓派优化：降低分辨率提高帧率
CAMERA_WIDTH = 480
CAMERA_HEIGHT = 360


class DetectionMode(Enum):
    """检测模式"""
    ZONE = "zone"           # 危险区域检测
    PRODUCT = "product"     # 产品检测


class PersonState(Enum):
    """人员状态"""
    SAFE = "safe"           # 在安全区
    DANGER = "danger"       # 在危险区
    UNKNOWN = "unknown"     # 未知


@dataclass
class TrackedPerson:
    """追踪的人员信息"""
    track_id: str                    # 追踪ID
    bbox: Tuple[int, int, int, int]  # 边界框
    center: Tuple[int, int]          # 中心点
    state: PersonState               # 当前状态
    last_seen: float                 # 最后一次看到的时间
    entered_danger_time: float = 0   # 进入危险区的时间
    
    def update(self, bbox: Tuple[int, int, int, int], center: Tuple[int, int], state: PersonState):
        """更新人员信息"""
        self.bbox = bbox
        self.center = center
        self.state = state
        self.last_seen = time.time()


@dataclass
class ZoneStatistics:
    """危险区域统计信息"""
    total_entries: int = 0           # 总进入次数
    total_exits: int = 0             # 总离开次数
    current_in_danger: int = 0       # 当前在危险区的人数
    persons_in_danger: Set[str] = field(default_factory=set)  # 当前在危险区的人员ID集合
    
    def person_entered(self, track_id: str):
        """人员进入危险区"""
        if track_id not in self.persons_in_danger:
            self.persons_in_danger.add(track_id)
            self.total_entries += 1
            self.current_in_danger = len(self.persons_in_danger)
            return True
        return False
    
    def person_exited(self, track_id: str):
        """人员离开危险区"""
        if track_id in self.persons_in_danger:
            self.persons_in_danger.discard(track_id)
            self.total_exits += 1
            self.current_in_danger = len(self.persons_in_danger)
            return True
        return False
    
    def remove_person(self, track_id: str):
        """移除人员（离开画面）"""
        if track_id in self.persons_in_danger:
            self.persons_in_danger.discard(track_id)
            self.current_in_danger = len(self.persons_in_danger)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_entries": self.total_entries,
            "total_exits": self.total_exits,
            "current_in_danger": self.current_in_danger
        }


@dataclass
class AlertInfo:
    """警报信息"""
    timestamp: str
    zone_type: str
    person_count: int
    message: str
    bbox: Tuple[int, int, int, int]
    event_type: str = "enter"  # enter=进入, exit=离开


# ==================== 服务器通信 ====================
class ServerClient:
    """服务器通信客户端"""
    
    def __init__(self, server_url: str, device_id: str):
        self.server_url = server_url.rstrip('/')
        self.device_id = device_id
        self._current_mode = DetectionMode.ZONE
        self._mode_lock = threading.Lock()
    
    def get_detection_mode(self) -> DetectionMode:
        """从服务器获取当前检测模式"""
        try:
            response = requests.get(
                f"{self.server_url}/api/detection/mode/{self.device_id}",
                timeout=1
            )
            if response.status_code == 200:
                data = response.json()
                mode_str = data.get("mode", "zone")
                return DetectionMode.PRODUCT if mode_str == "product" else DetectionMode.ZONE
        except Exception:
            pass
        return self._current_mode
    
    def report_detection(self, person_count: int, in_danger_zone: bool, alert_triggered: bool):
        """上报危险区域检测结果"""
        try:
            data = {
                "device_id": self.device_id,
                "person_count": person_count,
                "in_danger_zone": in_danger_zone,
                "alert_triggered": alert_triggered
            }
            requests.post(f"{self.server_url}/api/detection", json=data, timeout=2)
        except Exception:
            pass
    
    def report_zone_event(self, event_type: str, statistics: dict, message: str):
        """
        上报危险区域事件（进入/离开）
        
        Args:
            event_type: 事件类型 (enter/exit)
            statistics: 统计信息
            message: 事件消息
        """
        try:
            data = {
                "device_id": self.device_id,
                "event_type": event_type,
                "statistics": statistics,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            requests.post(f"{self.server_url}/api/zone/event", json=data, timeout=2)
        except Exception:
            pass
    
    def report_product(self, result: Dict):
        """上报产品检测结果"""
        try:
            data = {
                "device_id": self.device_id,
                "product_type": result.get("product_type", "unknown"),
                "color": result.get("color", ""),
                "shape": result.get("shape", ""),
                "confidence": result.get("confidence", 0),
                "timestamp": datetime.now().isoformat()
            }
            requests.post(f"{self.server_url}/api/product/detection", json=data, timeout=2)
        except Exception:
            pass
    
    def send_video_frame(self, frame: np.ndarray, detection_info: dict = None):
        """发送视频帧"""
        try:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), VIDEO_QUALITY]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            data = {
                "device_id": self.device_id,
                "frame": frame_base64,
                "timestamp": datetime.now().isoformat(),
                "detection": detection_info
            }
            requests.post(f"{self.server_url}/api/video/frame", json=data, timeout=1)
        except Exception:
            pass


# ==================== 人员追踪器 ====================
class PersonTracker:
    """
    简单的人员追踪器 - 基于位置匹配
    用于追踪人员的进入/离开危险区域状态
    """
    
    def __init__(self, max_distance: float = 100, timeout: float = 2.0):
        """
        Args:
            max_distance: 最大匹配距离（像素）
            timeout: 人员消失超时时间（秒）
        """
        self.tracked_persons: Dict[str, TrackedPerson] = {}
        self.max_distance = max_distance
        self.timeout = timeout
        self.next_id = 0
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        self.next_id += 1
        return f"person_{self.next_id}"
    
    def _calculate_distance(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        """计算两点距离"""
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def _find_best_match(self, center: Tuple[int, int]) -> Optional[str]:
        """找到最佳匹配的已追踪人员"""
        best_match = None
        best_distance = self.max_distance
        
        for track_id, person in self.tracked_persons.items():
            distance = self._calculate_distance(center, person.center)
            if distance < best_distance:
                best_distance = distance
                best_match = track_id
        
        return best_match
    
    def update(self, detections: List[Tuple[int, int, int, int, float]], 
               get_state_func: Callable[[Tuple[int, int]], PersonState]) -> List[dict]:
        """
        更新追踪状态
        
        Args:
            detections: 检测结果列表 [(x1, y1, x2, y2, conf), ...]
            get_state_func: 获取人员状态的函数（根据中心点判断是否在危险区）
        
        Returns:
            状态变化事件列表 [{"track_id": str, "event": "enter"/"exit", "bbox": tuple}, ...]
        """
        events = []
        current_time = time.time()
        matched_ids = set()
        
        # 处理每个检测结果
        for detection in detections:
            x1, y1, x2, y2, conf = detection
            bbox = (x1, y1, x2, y2)
            center = (int((x1 + x2) / 2), int(y2))  # 使用脚部中心点
            current_state = get_state_func(center)
            
            # 尝试匹配已有人员
            match_id = self._find_best_match(center)
            
            if match_id and match_id not in matched_ids:
                # 匹配到已有人员，检查状态变化
                person = self.tracked_persons[match_id]
                old_state = person.state
                
                # 状态变化检测
                if old_state != current_state:
                    if old_state == PersonState.SAFE and current_state == PersonState.DANGER:
                        # 从安全区进入危险区
                        events.append({
                            "track_id": match_id,
                            "event": "enter",
                            "bbox": bbox,
                            "center": center
                        })
                        person.entered_danger_time = current_time
                    elif old_state == PersonState.DANGER and current_state == PersonState.SAFE:
                        # 从危险区离开到安全区
                        events.append({
                            "track_id": match_id,
                            "event": "exit",
                            "bbox": bbox,
                            "center": center
                        })
                
                # 更新人员信息
                person.update(bbox, center, current_state)
                matched_ids.add(match_id)
            else:
                # 新人员
                new_id = self._generate_id()
                new_person = TrackedPerson(
                    track_id=new_id,
                    bbox=bbox,
                    center=center,
                    state=current_state,
                    last_seen=current_time
                )
                self.tracked_persons[new_id] = new_person
                matched_ids.add(new_id)
                
                # 如果新人员直接出现在危险区，也触发进入事件
                if current_state == PersonState.DANGER:
                    events.append({
                        "track_id": new_id,
                        "event": "enter",
                        "bbox": bbox,
                        "center": center
                    })
                    new_person.entered_danger_time = current_time
        
        # 清理超时的人员
        expired_ids = []
        for track_id, person in self.tracked_persons.items():
            if track_id not in matched_ids:
                if current_time - person.last_seen > self.timeout:
                    expired_ids.append(track_id)
                    # 如果人员在危险区消失，视为离开
                    if person.state == PersonState.DANGER:
                        events.append({
                            "track_id": track_id,
                            "event": "exit_timeout",
                            "bbox": person.bbox,
                            "center": person.center
                        })
        
        for track_id in expired_ids:
            del self.tracked_persons[track_id]
        
        return events
    
    def get_persons_in_danger(self) -> List[TrackedPerson]:
        """获取当前在危险区的人员列表"""
        return [p for p in self.tracked_persons.values() if p.state == PersonState.DANGER]
    
    def reset(self):
        """重置追踪器"""
        self.tracked_persons.clear()
        self.next_id = 0


# ==================== 危险区域检测器 ====================
class ZoneDetector:
    """危险区域检测器 - 基于YOLOv8，支持人员状态追踪"""
    
    def __init__(self, model_path: str = "yolov8n_ncnn_model", frame_skip: int = 3,
                 input_size: Tuple[int, int] = (320, 320), alert_cooldown: float = 3.0):
        print("正在加载YOLOv8模型...")
        self.model = YOLO(model_path)
        # NCNN 模型不需要 fuse()
        if model_path.endswith(".pt"):
            self.model.fuse()
        
        self.danger_zones: List[np.ndarray] = []
        self.safe_zones: List[np.ndarray] = []
        self.alert_callback: Optional[Callable] = None
        self.exit_callback: Optional[Callable] = None  # 离开危险区回调
        self.person_class_id = 0
        
        self.frame_skip = frame_skip
        self.frame_count = 0
        self.input_size = input_size
        self.alert_cooldown = alert_cooldown
        self.last_alert_time = {}
        self.last_detections = []
        self.scale_x = 1.0
        self.scale_y = 1.0
        
        # 人员追踪器
        self.tracker = PersonTracker(max_distance=100, timeout=2.0)
        
        # 统计信息
        self.statistics = ZoneStatistics()
        
        print(f"✓ YOLOv8模型加载完成")
        print(f"✓ 人员追踪器已启用")
    
    def add_danger_zone(self, points: List[Tuple[int, int]]):
        self.danger_zones.append(np.array(points, dtype=np.int32))
    
    def add_safe_zone(self, points: List[Tuple[int, int]]):
        self.safe_zones.append(np.array(points, dtype=np.int32))
    
    def set_alert_callback(self, callback: Callable):
        """设置进入危险区报警回调"""
        self.alert_callback = callback
    
    def set_exit_callback(self, callback: Callable):
        """设置离开危险区通知回调"""
        self.exit_callback = callback
    
    def _point_in_zone(self, point: Tuple[int, int], zone: np.ndarray) -> bool:
        return cv2.pointPolygonTest(zone, point, False) >= 0
    
    def _get_person_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x1, y1, x2, y2 = bbox
        return (int((x1 + x2) / 2), int(y2))
    
    def _get_person_state(self, center: Tuple[int, int]) -> PersonState:
        """根据中心点判断人员状态"""
        for zone in self.danger_zones:
            if self._point_in_zone(center, zone):
                return PersonState.DANGER
        for zone in self.safe_zones:
            if self._point_in_zone(center, zone):
                return PersonState.SAFE
        return PersonState.UNKNOWN
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        return self.statistics.to_dict()
    
    def reset_statistics(self):
        """重置统计信息"""
        self.statistics = ZoneStatistics()
        self.tracker.reset()
        print("✓ 统计信息已重置")
    
    def detect(self, frame: np.ndarray, conf_threshold: float = 0.5) -> Tuple[np.ndarray, dict]:
        """执行危险区域检测（异步模式下每次调用都执行检测）"""
        h_orig, w_orig = frame.shape[:2]
        output = frame.copy()
        
        events = []  # 状态变化事件
        
        # YOLO检测 - 异步模式下每次都执行
        if self.input_size:
            resized = cv2.resize(frame, self.input_size)
            self.scale_x = w_orig / self.input_size[0]
            self.scale_y = h_orig / self.input_size[1]
        else:
            resized = frame
            self.scale_x = self.scale_y = 1.0
        
        results = self.model(resized, conf=conf_threshold, classes=[self.person_class_id],
                           verbose=False, device='cpu')
        
        self.last_detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                conf = float(box.conf[0])
                x1, y1 = int(x1 * self.scale_x), int(y1 * self.scale_y)
                x2, y2 = int(x2 * self.scale_x), int(y2 * self.scale_y)
                self.last_detections.append((x1, y1, x2, y2, conf))
        
        # 更新追踪器并获取状态变化事件
        events = self.tracker.update(self.last_detections, self._get_person_state)
        
        # 处理状态变化事件
        for event in events:
            track_id = event["track_id"]
            event_type = event["event"]
            bbox = event["bbox"]
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if event_type == "enter":
                # 进入危险区
                self.statistics.person_entered(track_id)
                if self.alert_callback:
                    alert = AlertInfo(
                        timestamp=timestamp,
                        zone_type="danger",
                        person_count=self.statistics.current_in_danger,
                        message=f"⚠️ 人员进入危险区域！当前危险区人数: {self.statistics.current_in_danger}",
                        bbox=bbox,
                        event_type="enter"
                    )
                    self.alert_callback(alert)
            
            elif event_type in ["exit", "exit_timeout"]:
                # 离开危险区
                self.statistics.person_exited(track_id)
                if self.exit_callback:
                    alert = AlertInfo(
                        timestamp=timestamp,
                        zone_type="safe",
                        person_count=self.statistics.current_in_danger,
                        message=f"✅ 人员离开危险区域！当前危险区人数: {self.statistics.current_in_danger}",
                        bbox=bbox,
                        event_type="exit"
                    )
                    self.exit_callback(alert)
        
        # 绘制区域
        overlay = output.copy()
        for zone in self.danger_zones:
            cv2.fillPoly(overlay, [zone], (0, 0, 200))
            cv2.polylines(output, [zone], True, (0, 0, 255), 2)
        for zone in self.safe_zones:
            cv2.fillPoly(overlay, [zone], (0, 200, 0))
            cv2.polylines(output, [zone], True, (0, 255, 0), 2)
        cv2.addWeighted(overlay, 0.3, output, 0.7, 0, output)
        
        # 绘制警戒线
        mid_x = w_orig // 2
        cv2.line(output, (mid_x, 0), (mid_x, h_orig), (0, 255, 255), 2)
        cv2.putText(output, "WARNING LINE", (mid_x + 10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # 处理检测结果并绘制
        danger_count = 0
        person_count = len(self.last_detections)
        
        for detection in self.last_detections:
            x1, y1, x2, y2, conf = detection
            center = self._get_person_center((x1, y1, x2, y2))
            in_danger = any(self._point_in_zone(center, zone) for zone in self.danger_zones)
            
            if in_danger:
                danger_count += 1
                color = (0, 0, 255)
                label = "DANGER!"
            else:
                color = (0, 255, 0)
                label = "Person"
            
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            cv2.putText(output, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.circle(output, center, 4, color, -1)
        
        # 显示统计信息
        stats = self.statistics
        y_offset = 30
        
        # 警告信息
        if stats.current_in_danger > 0:
            cv2.putText(output, f"WARNING: {stats.current_in_danger} in DANGER ZONE!", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            y_offset += 30
        
        # 统计信息
        cv2.putText(output, f"Persons: {person_count}", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_offset += 25
        
        cv2.putText(output, f"In Danger: {stats.current_in_danger}", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        y_offset += 25
        
        cv2.putText(output, f"Entries: {stats.total_entries} | Exits: {stats.total_exits}", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 100), 1)
        
        # 模式标识
        cv2.putText(output, "[ZONE MODE]", (w_orig - 150, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        detection_info = {
            "mode": "zone",
            "person_count": person_count,
            "in_danger_zone": stats.current_in_danger > 0,
            "alert_triggered": len([e for e in events if e["event"] == "enter"]) > 0,
            "exit_triggered": len([e for e in events if e["event"] in ["exit", "exit_timeout"]]) > 0,
            "statistics": stats.to_dict(),
            "events": events
        }
        
        return output, detection_info


# ==================== 产品检测器 ====================
class ProductDetector:
    """
    产品检测器 - 基于颜色和形状
    
    优化特性：
    1. ROI检测区域限制，只检测中心区域
    2. 稳定性检测，连续N帧检测到同一产品才确认
    3. 自动计数，产品离开检测区域时自动计数
    4. 跳帧优化，降低CPU占用
    """
    
    # 颜色定义（HSV范围）
    COLOR_RANGES = {
        "blue": {
            "lower": np.array([100, 100, 100]),
            "upper": np.array([130, 255, 255]),
            "name": "蓝色",
            "display_color": (255, 150, 50)
        },
        "cyan": {
            "lower": np.array([75, 100, 100]),
            "upper": np.array([95, 255, 255]),
            "name": "青色",
            "display_color": (200, 200, 50)
        }
    }
    
    # 产品定义规则：颜色 + 形状 → 产品类型
    PRODUCT_RULES = {
        ("blue", "rectangle"): "product_a",    # 蓝色方形 → 产品A
        ("cyan", "circle"): "product_b",       # 青色圆形 → 产品B
    }
    
    SHAPE_CIRCULARITY_THRESHOLD = 0.7
    MIN_CONTOUR_AREA = 1000
    MAX_CONTOUR_AREA = 100000
    
    def __init__(self, frame_skip: int = 3, stability_frames: int = 3, auto_count: bool = True):
        """
        初始化产品检测器
        Args:
            frame_skip: 跳帧数，每隔N帧检测一次
            stability_frames: 稳定性帧数，连续N帧检测到同一产品才确认
            auto_count: 是否启用自动计数
        """
        self.detection_count = {"product_a": 0, "product_b": 0, "unknown": 0}
        self.last_detection_time = 0
        self.detection_cooldown = 1.5  # 同一产品检测冷却时间
        
        # 跳帧控制
        self.frame_skip = frame_skip
        self.frame_count = 0
        
        # 稳定性检测
        self.stability_frames = stability_frames
        self.consecutive_detections = []  # 连续检测结果队列
        self.confirmed_product = None     # 已确认的产品
        
        # 自动计数
        self.auto_count = auto_count
        self.product_in_roi = False       # 产品是否在检测区域内
        self.last_confirmed_product = None  # 上一个确认的产品（用于离开时计数）
        
        # ROI检测区域（相对比例）
        self.roi_margin = 0.15  # 边距比例，0.15表示上下左右各留15%
        
        # 缓存上一次的检测结果（用于跳帧时显示）
        self.last_result = None
        self.last_contours = []
        self.last_color_type = "unknown"
        self.last_bbox = None
        
        print(f"✓ 产品检测器初始化完成")
        print(f"  跳帧: {frame_skip} | 稳定帧数: {stability_frames} | 自动计数: {auto_count}")
    
    def _get_roi(self, frame: np.ndarray) -> Tuple[int, int, int, int]:
        """获取ROI区域坐标"""
        h, w = frame.shape[:2]
        margin_x = int(w * self.roi_margin)
        margin_y = int(h * self.roi_margin)
        return margin_x, margin_y, w - margin_x, h - margin_y
    
    def _is_in_roi(self, bbox: Tuple[int, int, int, int], frame_shape: Tuple[int, int]) -> bool:
        """判断物体中心是否在ROI内"""
        h, w = frame_shape
        x, y, bw, bh = bbox
        center_x = x + bw // 2
        center_y = y + bh // 2
        
        roi_x1, roi_y1, roi_x2, roi_y2 = self._get_roi(np.zeros((h, w, 3), dtype=np.uint8))
        return roi_x1 < center_x < roi_x2 and roi_y1 < center_y < roi_y2
    
    def detect_color(self, frame: np.ndarray) -> Tuple[str, np.ndarray]:
        """
        检测颜色（只在ROI区域内检测）
        Returns:
            (颜色类型, 掩码) - 颜色类型为 "blue"/"cyan"/"unknown"
        """
        h, w = frame.shape[:2]
        roi_x1, roi_y1, roi_x2, roi_y2 = self._get_roi(frame)
        
        # 只处理ROI区域
        roi_frame = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        hsv = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2HSV)
        
        best_match = "unknown"
        best_area = 0
        best_mask = None
        
        for color_name, color_range in self.COLOR_RANGES.items():
            mask = cv2.inRange(hsv, color_range["lower"], color_range["upper"])
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            area = cv2.countNonZero(mask)
            
            if area > best_area and area > self.MIN_CONTOUR_AREA:
                best_area = area
                best_match = color_name
                best_mask = mask
        
        # 将ROI掩码扩展到完整帧大小
        if best_mask is not None:
            full_mask = np.zeros((h, w), dtype=np.uint8)
            full_mask[roi_y1:roi_y2, roi_x1:roi_x2] = best_mask
            return best_match, full_mask
        
        return "unknown", np.zeros((h, w), dtype=np.uint8)
    
    def detect_shape(self, mask: np.ndarray) -> Tuple[str, List[np.ndarray], Optional[Tuple[int, int, int, int]]]:
        """
        检测形状
        Returns:
            (形状类型, 轮廓列表, 边界框) - 形状类型为 "circle"/"rectangle"/"unknown"
        """
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return "unknown", [], None
        
        valid_contours = [c for c in contours
                        if self.MIN_CONTOUR_AREA < cv2.contourArea(c) < self.MAX_CONTOUR_AREA]
        if not valid_contours:
            return "unknown", [], None
        
        largest = max(valid_contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        perimeter = cv2.arcLength(largest, True)
        
        if perimeter == 0:
            return "unknown", valid_contours, None
        
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        shape = "circle" if circularity > self.SHAPE_CIRCULARITY_THRESHOLD else "rectangle"
        
        # 获取边界框
        bbox = cv2.boundingRect(largest)
        
        return shape, valid_contours, bbox
    
    def _determine_product(self, color_type: str, shape_type: str) -> Tuple[str, float]:
        """
        根据颜色和形状判断产品类型
        Returns:
            (产品类型, 置信度)
        """
        if color_type == "unknown" or shape_type == "unknown":
            return "unknown", 0.0
        
        # 查找匹配的产品规则
        product_type = self.PRODUCT_RULES.get((color_type, shape_type))
        
        if product_type:
            return product_type, 0.95
        else:
            return "unknown", 0.3
    
    def _update_stability(self, product_type: str) -> Tuple[str, bool]:
        """
        更新稳定性检测
        Returns:
            (确认的产品类型, 是否新确认)
        """
        self.consecutive_detections.append(product_type)
        
        # 保持队列长度
        if len(self.consecutive_detections) > self.stability_frames:
            self.consecutive_detections.pop(0)
        
        # 检查是否连续检测到同一产品
        if len(self.consecutive_detections) >= self.stability_frames:
            if all(p == product_type and p != "unknown" for p in self.consecutive_detections):
                if self.confirmed_product != product_type:
                    self.confirmed_product = product_type
                    return product_type, True  # 新确认
                return product_type, False  # 已确认
        
        return self.confirmed_product or "unknown", False
    
    def _handle_auto_count(self, product_in_roi: bool, confirmed_product: str):
        """处理自动计数逻辑"""
        if not self.auto_count:
            return
        
        # 产品从ROI内移动到ROI外时计数
        if self.product_in_roi and not product_in_roi:
            if self.last_confirmed_product and self.last_confirmed_product != "unknown":
                current_time = time.time()
                if current_time - self.last_detection_time >= self.detection_cooldown:
                    self.detection_count[self.last_confirmed_product] += 1
                    self.last_detection_time = current_time
                    print(f"\n📦 自动计数: {self.last_confirmed_product} | 总计: {self.detection_count[self.last_confirmed_product]}")
                    # 重置确认状态
                    self.confirmed_product = None
                    self.consecutive_detections.clear()
        
        # 更新状态
        self.product_in_roi = product_in_roi
        if confirmed_product != "unknown":
            self.last_confirmed_product = confirmed_product
    
    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, dict]:
        """
        执行产品检测（带跳帧优化和稳定性检测）
        """
        output = frame.copy()
        h, w = output.shape[:2]
        
        # 绘制ROI区域
        roi_x1, roi_y1, roi_x2, roi_y2 = self._get_roi(frame)
        cv2.rectangle(output, (roi_x1, roi_y1), (roi_x2, roi_y2), (100, 200, 100), 2)
        cv2.putText(output, "Detection ROI", (roi_x1 + 5, roi_y1 - 8), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 100), 1)
        
        # 跳帧控制
        self.frame_count += 1
        should_detect = (self.frame_count % (self.frame_skip + 1) == 0)
        
        product_in_roi = False
        confirmed_product = "unknown"
        is_new_confirmation = False
        
        if should_detect:
            # 执行实际检测
            color_type, mask = self.detect_color(frame)
            shape_type, contours, bbox = self.detect_shape(mask)
            product_type, confidence = self._determine_product(color_type, shape_type)
            
            # 检查是否在ROI内
            if bbox:
                product_in_roi = self._is_in_roi(bbox, (h, w))
            
            # 稳定性检测
            if product_in_roi and product_type != "unknown":
                confirmed_product, is_new_confirmation = self._update_stability(product_type)
            else:
                # 不在ROI内或未检测到，清空稳定性队列
                if not product_in_roi:
                    self.consecutive_detections.clear()
            
            # 处理自动计数
            self._handle_auto_count(product_in_roi, confirmed_product)
            
            # 缓存结果
            self.last_color_type = color_type
            self.last_contours = contours
            self.last_bbox = bbox
            self.last_result = {
                "mode": "product",
                "detected": confirmed_product != "unknown",
                "product_type": confirmed_product,
                "color": self.COLOR_RANGES.get(color_type, {}).get("name", "未知"),
                "shape": "圆形" if shape_type == "circle" else ("方形" if shape_type == "rectangle" else "未知"),
                "confidence": confidence if confirmed_product != "unknown" else 0.0,
                "in_roi": product_in_roi,
                "is_new": is_new_confirmation,
                "size": {"width": bbox[2], "height": bbox[3]} if bbox else None
            }
        
        # 使用缓存的结果绘制
        result = self.last_result or {
            "mode": "product",
            "detected": False,
            "product_type": "unknown",
            "color": "未知",
            "shape": "未知",
            "confidence": 0.0,
            "in_roi": False,
            "is_new": False,
            "size": None
        }
        
        # 如果是跳帧，强制is_new为False，避免重复上报
        if not should_detect and result.get("is_new"):
            result = result.copy()
            result["is_new"] = False
        
        # 绘制轮廓和标注
        if self.last_contours and self.last_bbox:
            color_info = self.COLOR_RANGES.get(self.last_color_type, {})
            display_color = color_info.get("display_color", (128, 128, 128))
            
            # 如果已确认产品，用更亮的颜色
            if result["detected"]:
                display_color = tuple(min(255, c + 50) for c in display_color)
            
            cv2.drawContours(output, self.last_contours, -1, display_color, 2)
            
            x, y, bw, bh = self.last_bbox
            cv2.rectangle(output, (x, y), (x+bw, y+bh), display_color, 2)
            
            # 产品标签
            if result["detected"]:
                product_label = "Product A ✓" if result["product_type"] == "product_a" else "Product B ✓"
                cv2.putText(output, product_label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, display_color, 2)
            else:
                cv2.putText(output, "Detecting...", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
            
            # 详细信息
            info_y = y + bh + 18
            cv2.putText(output, f"{result['color']} {result['shape']}", (x, info_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, display_color, 1)
            
            if result["size"]:
                info_y += 16
                cv2.putText(output, f"Size: {result['size']['width']}x{result['size']['height']}px", (x, info_y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
        
        # 统计信息
        cv2.putText(output, f"Product A: {self.detection_count['product_a']}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_RANGES["blue"]["display_color"], 2)
        cv2.putText(output, f"Product B: {self.detection_count['product_b']}", (10, 55),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_RANGES["cyan"]["display_color"], 2)
        
        # 稳定性指示器
        stability_progress = len(self.consecutive_detections) / self.stability_frames
        bar_width = 100
        bar_x = 10
        bar_y = 75
        cv2.rectangle(output, (bar_x, bar_y), (bar_x + bar_width, bar_y + 8), (50, 50, 50), -1)
        cv2.rectangle(output, (bar_x, bar_y), (bar_x + int(bar_width * stability_progress), bar_y + 8), 
                     (0, 200, 0) if stability_progress >= 1 else (200, 200, 0), -1)
        cv2.putText(output, "Stability", (bar_x + bar_width + 5, bar_y + 8), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
        
        # 模式标识
        mode_text = "[PRODUCT MODE]"
        if self.auto_count:
            mode_text += " [AUTO]"
        cv2.putText(output, mode_text, (w - 220, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 150, 50), 2)
        
        return output, result
    
    def capture(self, frame: np.ndarray) -> Optional[dict]:
        """手动捕获检测（用于手动计数）"""
        current_time = time.time()
        if current_time - self.last_detection_time < self.detection_cooldown:
            return None
        
        _, result = self.detect(frame)
        if result["detected"] and result["product_type"] != "unknown":
            self.last_detection_time = current_time
            self.detection_count[result["product_type"]] += 1
            print(f"\n📦 手动捕获: {result['product_type']} | {result['color']} | {result['shape']}")
            return result
        return None
    
    def reset_count(self):
        """重置计数"""
        self.detection_count = {"product_a": 0, "product_b": 0, "unknown": 0}
        self.confirmed_product = None
        self.consecutive_detections.clear()
        print("✓ 产品计数已重置")



# ==================== DHT11 温湿度传感器 ====================
class DHT11Sensor:
    """DHT11 温湿度传感器"""
    
    def __init__(self, pin=4):
        """
        初始化 DHT11 传感器
        Args:
            pin: GPIO 针脚号（BCM编号），默认 GPIO4
        """
        self.dht_device = None
        self.last_temperature = None
        self.last_humidity = None
        self.initialized = False
        
        if DHT_AVAILABLE:
            try:
                # 根据 pin 号选择对应的 board 针脚
                pin_map = {4: board.D4, 17: board.D17, 27: board.D27, 22: board.D22}
                board_pin = pin_map.get(pin, board.D4)
                self.dht_device = adafruit_dht.DHT11(board_pin)
                self.initialized = True
                print(f"✓ DHT11 传感器初始化成功 | GPIO{pin}")
            except Exception as e:
                print(f"⚠️ DHT11 初始化失败: {e}")
        else:
            print("⚠️ DHT11 库不可用")
    
    def read(self) -> Tuple[Optional[float], Optional[float]]:
        """
        读取温湿度
        Returns:
            (temperature, humidity) 或 (None, None) 如果读取失败
        """
        if not self.initialized:
            return None, None
        
        try:
            temperature = self.dht_device.temperature
            humidity = self.dht_device.humidity
            
            if temperature is not None and humidity is not None:
                self.last_temperature = temperature
                self.last_humidity = humidity
                return temperature, humidity
        except RuntimeError:
            # DHT11 偶尔读取失败是正常的
            pass
        except Exception as e:
            print(f"DHT11 读取错误: {e}")
        
        # 返回上次成功读取的值
        return self.last_temperature, self.last_humidity
    
    def cleanup(self):
        """清理资源"""
        if self.dht_device:
            try:
                self.dht_device.exit()
            except:
                pass


# ==================== GPIO控制器 ====================
class GPIOController:
    """
    GPIO控制器 - 管理三个LED灯
    
    LED状态逻辑：
    - 红灯(GPIO22): 环境异常（温度/湿度超标）
    - 蓝灯(GPIO17): 有人在危险区域
    - 绿灯(GPIO27): 系统正常运行
    """
    
    def __init__(self, led_red_pin: int = 22, led_blue_pin: int = 17, led_green_pin: int = 27):
        self.led_red_pin = led_red_pin      # 红灯 - 环境异常
        self.led_blue_pin = led_blue_pin    # 蓝灯 - 危险区域有人
        self.led_green_pin = led_green_pin  # 绿灯 - 正常
        self.gpio_initialized = False
        
        # LED 状态
        self.led_states = {"red": False, "blue": False, "green": False}
        
        if IS_LINUX:
            try:
                import RPi.GPIO as GPIO
                self.GPIO = GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                
                # 初始化三个 LED
                GPIO.setup(self.led_red_pin, GPIO.OUT)
                GPIO.output(self.led_red_pin, GPIO.LOW)
                
                GPIO.setup(self.led_blue_pin, GPIO.OUT)
                GPIO.output(self.led_blue_pin, GPIO.LOW)
                
                GPIO.setup(self.led_green_pin, GPIO.OUT)
                GPIO.output(self.led_green_pin, GPIO.LOW)
                
                self.gpio_initialized = True
                print(f"✓ GPIO初始化成功")
                print(f"  红灯(环境异常): GPIO{led_red_pin}")
                print(f"  蓝灯(危险区域): GPIO{led_blue_pin}")
                print(f"  绿灯(正常): GPIO{led_green_pin}")
            except ImportError:
                print("⚠️ RPi.GPIO未安装，GPIO功能禁用")
            except Exception as e:
                print(f"⚠️ GPIO初始化失败: {e}")
    
    def _get_pin(self, color: str) -> int:
        """获取颜色对应的GPIO针脚"""
        pin_map = {
            "red": self.led_red_pin,
            "blue": self.led_blue_pin,
            "green": self.led_green_pin
        }
        return pin_map.get(color, self.led_green_pin)
    
    def turn_on_led(self, color: str):
        """打开指定颜色的 LED"""
        if not self.gpio_initialized:
            return
        if color in self.led_states and not self.led_states[color]:
            pin = self._get_pin(color)
            self.GPIO.output(pin, self.GPIO.HIGH)
            self.led_states[color] = True
    
    def turn_off_led(self, color: str):
        """关闭指定颜色的 LED"""
        if not self.gpio_initialized:
            return
        if color in self.led_states and self.led_states[color]:
            pin = self._get_pin(color)
            self.GPIO.output(pin, self.GPIO.LOW)
            self.led_states[color] = False
    
    def set_led_state(self, red: bool = False, blue: bool = False, green: bool = False):
        """
        一次性设置所有LED状态
        Args:
            red: 红灯状态（环境异常）
            blue: 蓝灯状态（危险区域有人）
            green: 绿灯状态（正常）
        """
        if not self.gpio_initialized:
            return
        
        # 红灯
        if red and not self.led_states["red"]:
            self.GPIO.output(self.led_red_pin, self.GPIO.HIGH)
            self.led_states["red"] = True
        elif not red and self.led_states["red"]:
            self.GPIO.output(self.led_red_pin, self.GPIO.LOW)
            self.led_states["red"] = False
        
        # 蓝灯
        if blue and not self.led_states["blue"]:
            self.GPIO.output(self.led_blue_pin, self.GPIO.HIGH)
            self.led_states["blue"] = True
        elif not blue and self.led_states["blue"]:
            self.GPIO.output(self.led_blue_pin, self.GPIO.LOW)
            self.led_states["blue"] = False
        
        # 绿灯
        if green and not self.led_states["green"]:
            self.GPIO.output(self.led_green_pin, self.GPIO.HIGH)
            self.led_states["green"] = True
        elif not green and self.led_states["green"]:
            self.GPIO.output(self.led_green_pin, self.GPIO.LOW)
            self.led_states["green"] = False
    
    def buzzer_beep(self, duration: float = 0.5):
        """蜂鸣器响（USB蜂鸣器通过系统声音）"""
        if IS_LINUX:
            try:
                import subprocess
                subprocess.run(['aplay', '-q', '/usr/share/sounds/alsa/Front_Center.wav'], 
                             timeout=2, check=False)
            except:
                print('\a')
    
    def cleanup(self):
        """清理GPIO资源"""
        if self.gpio_initialized:
            # 关闭所有LED
            self.GPIO.output(self.led_red_pin, self.GPIO.LOW)
            self.GPIO.output(self.led_blue_pin, self.GPIO.LOW)
            self.GPIO.output(self.led_green_pin, self.GPIO.LOW)
            self.GPIO.cleanup()
            print("✓ GPIO资源已清理")


# ==================== 统一检测系统 ====================
class UnifiedDetectionSystem:
    """
    统一检测系统 - 整合危险区域检测和产品检测
    
    特点：
    1. 共享同一个摄像头
    2. 支持模式切换（键盘/后端API）
    3. 默认运行危险区域检测
    4. 按需切换到产品检测
    5. 人员进入/离开危险区域的状态追踪和统计
    6. 异步检测：主线程显示画面，检测线程独立运行（树莓派优化）
    """
    
    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id
        self.cap = None
        
        # 当前模式
        self.current_mode = DetectionMode.ZONE
        self.mode_lock = threading.Lock()
        
        # 检测器
        self.zone_detector = None
        self.product_detector = None
        
        # 服务器客户端
        self.server = None
        if ENABLE_SERVER_REPORT or ENABLE_VIDEO_STREAM:
            self.server = ServerClient(SERVER_URL, DEVICE_ID)
        
        # GPIO控制器（红: GPIO22, 蓝: GPIO17, 绿: GPIO27）
        self.gpio = GPIOController(led_red_pin=22, led_blue_pin=17, led_green_pin=27)
        
        # DHT11 温湿度传感器（GPIO4）
        self.dht_sensor = DHT11Sensor(pin=4)
        
        # 传感器数据上报间隔
        self.last_sensor_report_time = 0
        self.sensor_report_interval = 5.0  # 每5秒上报一次
        
        # ========== 环境阈值设置 ==========
        self.temp_max = 35.0      # 温度上限 (°C)
        self.temp_min = 10.0      # 温度下限 (°C)
        self.humidity_max = 80.0  # 湿度上限 (%)
        self.humidity_min = 20.0  # 湿度下限 (%)
        self.pressure_max = 110.0 # 压力上限 (kPa) - 模拟值
        self.pressure_min = 90.0  # 压力下限 (kPa) - 模拟值
        
        # 环境状态
        self.env_abnormal = False  # 环境是否异常
        self.danger_zone_occupied = False  # 危险区域是否有人
        
        # 模拟压力值（因为没有压力传感器）
        self.simulated_pressure = 101.3  # 标准大气压
        
        # 视频流控制
        self.last_stream_time = 0
        self.stream_interval = 1.0 / VIDEO_STREAM_FPS
        
        # 运行状态
        self.running = False
        
        # 模式检查间隔
        self.last_mode_check = 0
        self.mode_check_interval = 1.0  # 每秒检查一次
        
        # ========== 异步检测相关 ==========
        # 用于线程间共享的帧和检测结果
        self._frame_lock = threading.Lock()
        self._result_lock = threading.Lock()
        self._latest_frame = None           # 最新的摄像头帧
        self._latest_result = None          # 最新的检测结果
        self._latest_processed_frame = None # 最新的处理后帧（带标注）
        self._detection_thread = None       # 检测线程
        self._detection_running = False     # 检测线程运行标志
    
    def init_detectors(self):
        """初始化检测器"""
        print("\n" + "="*60)
        print("🚀 统一检测系统初始化中...")
        print("="*60)
        
        # 初始化危险区域检测器
        # 尝试使用NCNN模型，如果不可用则回退到PyTorch模型
        import os
        if os.path.exists("yolov8n_ncnn_model"):
            model_path = "yolov8n_ncnn_model"
            print("✓ 使用 NCNN 格式模型（ARM优化）")
        else:
            model_path = "yolov8n.pt"
            print("⚠️ NCNN模型不可用，使用 PyTorch 模型")
        
        self.zone_detector = ZoneDetector(
            model_path=model_path,
            frame_skip=1,
            input_size=(320, 320),
            alert_cooldown=3.0
        )
        
        # 配置危险区域（屏幕右半部分）
        self.zone_detector.add_danger_zone([
            (CAMERA_WIDTH // 2, 0),
            (CAMERA_WIDTH, 0),
            (CAMERA_WIDTH, CAMERA_HEIGHT),
            (CAMERA_WIDTH // 2, CAMERA_HEIGHT)
        ])
        
        # 配置安全区域（屏幕左半部分）
        self.zone_detector.add_safe_zone([
            (0, 0),
            (CAMERA_WIDTH // 2, 0),
            (CAMERA_WIDTH // 2, CAMERA_HEIGHT),
            (0, CAMERA_HEIGHT)
        ])
        
        # 设置进入危险区报警回调
        self.zone_detector.set_alert_callback(self._on_zone_enter)
        
        # 设置离开危险区通知回调
        self.zone_detector.set_exit_callback(self._on_zone_exit)
        
        # 初始化产品检测器（跳帧优化，稳定性检测，自动计数）
        self.product_detector = ProductDetector(
            frame_skip=5,           # 每6帧检测一次
            stability_frames=8,     # 连续8帧确认
            auto_count=True         # 启用自动计数
        )
        
        print("✓ 所有检测器初始化完成")
        print("✓ 人员状态追踪已启用（进入/离开危险区域）")
    
    def _on_zone_enter(self, alert: AlertInfo):
        """人员进入危险区域回调"""
        print(f"\n🚨 {alert.timestamp} - {alert.message}")
        print(f"   📊 统计: 进入{self.zone_detector.statistics.total_entries}次 | "
              f"离开{self.zone_detector.statistics.total_exits}次 | "
              f"当前{self.zone_detector.statistics.current_in_danger}人")
        
        # 播放报警声（进入危险区 - 高频警报）
        def _alarm():
            if IS_WINDOWS:
                winsound.Beep(1000, 500)  # 高频报警
            elif IS_LINUX:
                self.gpio.buzzer_beep(0.5)
        threading.Thread(target=_alarm, daemon=True).start()
        
        # 更新LED状态（蓝灯亮表示危险区域有人）
        self._update_led_status()
        
        # 上报到服务器
        if self.server:
            def _report():
                self.server.report_zone_event(
                    event_type="enter",
                    statistics=self.zone_detector.get_statistics(),
                    message=alert.message
                )
            threading.Thread(target=_report, daemon=True).start()
    
    def _on_zone_exit(self, alert: AlertInfo):
        """人员离开危险区域回调"""
        print(f"\n✅ {alert.timestamp} - {alert.message}")
        print(f"   📊 统计: 进入{self.zone_detector.statistics.total_entries}次 | "
              f"离开{self.zone_detector.statistics.total_exits}次 | "
              f"当前{self.zone_detector.statistics.current_in_danger}人")
        
        # 播放提示音（离开危险区 - 低频提示）
        def _notify():
            if IS_WINDOWS:
                winsound.Beep(500, 200)
            elif IS_LINUX:
                self.gpio.buzzer_beep(0.2)
        threading.Thread(target=_notify, daemon=True).start()
        
        # 更新LED状态（如果危险区域没人了，蓝灯灭）
        self._update_led_status()
        
        # 上报到服务器
        if self.server:
            def _report():
                self.server.report_zone_event(
                    event_type="exit",
                    statistics=self.zone_detector.get_statistics(),
                    message=alert.message
                )
            threading.Thread(target=_report, daemon=True).start()
    
    def set_mode(self, mode: DetectionMode):
        """设置检测模式"""
        with self.mode_lock:
            if self.current_mode != mode:
                self.current_mode = mode
                mode_name = "危险区域检测" if mode == DetectionMode.ZONE else "产品检测"
                print(f"\n🔄 切换到: {mode_name}")
    
    def get_mode(self) -> DetectionMode:
        """获取当前模式"""
        with self.mode_lock:
            return self.current_mode
    
    def _check_mode_from_server(self):
        """从服务器检查模式"""
        current_time = time.time()
        if current_time - self.last_mode_check >= self.mode_check_interval:
            self.last_mode_check = current_time
            if self.server:
                new_mode = self.server.get_detection_mode()
                self.set_mode(new_mode)
    
    def _update_thresholds_from_server(self):
        """从服务器更新环境阈值"""
        if not hasattr(self, 'last_threshold_check'):
            self.last_threshold_check = 0
            self.threshold_check_interval = 5  # 每10秒检查一次（加快响应）
        
        current_time = time.time()
        if current_time - self.last_threshold_check >= self.threshold_check_interval:
            self.last_threshold_check = current_time
            if self.server:
                try:
                    response = requests.get(
                        f"{self.server.server_url}/api/thresholds/{DEVICE_ID}",
                        timeout=2
                    )
                    if response.status_code == 200:
                        thresholds = response.json()
                        old_values = (self.temp_min, self.temp_max, self.humidity_min, self.humidity_max)
                        
                        self.temp_min = float(thresholds.get('tempMin', self.temp_min))
                        self.temp_max = float(thresholds.get('tempMax', self.temp_max))
                        self.humidity_min = float(thresholds.get('humidityMin', self.humidity_min))
                        self.humidity_max = float(thresholds.get('humidityMax', self.humidity_max))
                        self.pressure_min = float(thresholds.get('pressureMin', self.pressure_min))
                        self.pressure_max = float(thresholds.get('pressureMax', self.pressure_max))
                        
                        new_values = (self.temp_min, self.temp_max, self.humidity_min, self.humidity_max)
                        if old_values != new_values:
                            print(f"🔧 阈值已更新: 温度{self.temp_min}-{self.temp_max}°C, 湿度{self.humidity_min}-{self.humidity_max}%")
                            # 阈值更新后立即重新检查环境状态
                            self._force_env_check = True
                except Exception as e:
                    pass  # 静默失败，使用默认阈值
    
    def _check_env_abnormal(self, temperature: float, humidity: float, pressure: float) -> bool:
        """
        检查环境是否异常
        Returns:
            True: 环境异常（任一指标超标）
            False: 环境正常
        """
        abnormal = False
        reasons = []
        
        # 检查温度
        if temperature < self.temp_min:
            abnormal = True
            reasons.append(f"温度过低({temperature:.1f}°C < {self.temp_min}°C)")
        elif temperature > self.temp_max:
            abnormal = True
            reasons.append(f"温度过高({temperature:.1f}°C > {self.temp_max}°C)")
        
        # 检查湿度
        if humidity < self.humidity_min:
            abnormal = True
            reasons.append(f"湿度过低({humidity:.1f}% < {self.humidity_min}%)")
        elif humidity > self.humidity_max:
            abnormal = True
            reasons.append(f"湿度过高({humidity:.1f}% > {self.humidity_max}%)")
        
        # 检查压力
        if pressure < self.pressure_min:
            abnormal = True
            reasons.append(f"压力过低({pressure:.1f}kPa < {self.pressure_min}kPa)")
        elif pressure > self.pressure_max:
            abnormal = True
            reasons.append(f"压力过高({pressure:.1f}kPa > {self.pressure_max}kPa)")
        
        if abnormal and reasons:
            print(f"⚠️ 环境异常: {', '.join(reasons)}")
        
        return abnormal
    
    def _update_led_status(self):
        """
        根据当前状态更新LED灯
        
        逻辑：
        - 红灯: 环境异常（温度/湿度/压力超标）
        - 蓝灯: 危险区域有人
        - 绿灯: 一切正常（环境正常 且 危险区域无人）
        """
        # 检查危险区域是否有人
        if self.zone_detector:
            self.danger_zone_occupied = self.zone_detector.statistics.current_in_danger > 0
        
        # 计算LED状态
        red_on = self.env_abnormal
        blue_on = self.danger_zone_occupied
        green_on = (not self.env_abnormal) and (not self.danger_zone_occupied)
        
        # 设置LED
        self.gpio.set_led_state(red=red_on, blue=blue_on, green=green_on)
    
    def _report_sensor_data(self):
        """上报温湿度传感器数据并检查环境状态"""
        current_time = time.time()
        if current_time - self.last_sensor_report_time < self.sensor_report_interval:
            return
        
        self.last_sensor_report_time = current_time
        
        # 读取温湿度
        temperature, humidity = self.dht_sensor.read()
        
        # 生成模拟压力值（基于温度微小波动）
        import random
        self.simulated_pressure = 101.3 + random.uniform(-2, 2)
        pressure = self.simulated_pressure
        
        if temperature is not None and humidity is not None:
            print(f"🌡️ 温度: {temperature:.1f}°C | 💧 湿度: {humidity:.1f}% | 📊 压力: {pressure:.1f}kPa | 阈值: {self.temp_min}-{self.temp_max}°C")
            
            # 检查环境是否异常
            old_env_abnormal = self.env_abnormal
            self.env_abnormal = self._check_env_abnormal(temperature, humidity, pressure)
            
            # 检查是否需要强制更新（阈值变化后）
            force_check = getattr(self, '_force_env_check', False)
            if force_check:
                self._force_env_check = False
            
            # 如果环境状态变化或强制检查，更新LED
            if old_env_abnormal != self.env_abnormal or force_check:
                if self.env_abnormal:
                    print("🔴 环境异常，红灯亮起")
                    self.gpio.buzzer_beep(0.3)  # 短促警报
                else:
                    print("🟢 环境恢复正常")
                self._update_led_status()
            
            # 上报到服务器
            if self.server:
                def _report():
                    try:
                        # 上报温度
                        requests.post(
                            f"{self.server.server_url}/api/sensor",
                            json={
                                "device_id": DEVICE_ID,
                                "sensor_type": "temperature",
                                "value": temperature,
                                "unit": "°C"
                            },
                            timeout=2
                        )
                        # 上报湿度
                        requests.post(
                            f"{self.server.server_url}/api/sensor",
                            json={
                                "device_id": DEVICE_ID,
                                "sensor_type": "humidity",
                                "value": humidity,
                                "unit": "%"
                            },
                            timeout=2
                        )
                        # 上报压力（模拟值）
                        requests.post(
                            f"{self.server.server_url}/api/sensor",
                            json={
                                "device_id": DEVICE_ID,
                                "sensor_type": "pressure",
                                "value": pressure,
                                "unit": "kPa"
                            },
                            timeout=2
                        )
                    except Exception:
                        pass
                threading.Thread(target=_report, daemon=True).start()
    
    def _stream_frame(self, frame: np.ndarray, detection_info: dict):
        """推送视频帧"""
        current_time = time.time()
        if current_time - self.last_stream_time >= self.stream_interval:
            self.last_stream_time = current_time
            if self.server:
                def _send():
                    self.server.send_video_frame(frame, detection_info)
                threading.Thread(target=_send, daemon=True).start()
    
    def _report_detection(self, detection_info: dict):
        """上报检测结果"""
        if not self.server:
            return
        
        mode = detection_info.get("mode", "zone")
        
        if mode == "zone" and detection_info.get("alert_triggered"):
            def _report():
                self.server.report_detection(
                    detection_info.get("person_count", 0),
                    detection_info.get("in_danger_zone", False),
                    detection_info.get("alert_triggered", False)
                )
            threading.Thread(target=_report, daemon=True).start()
        
        elif mode == "product" and detection_info.get("is_new"):
            def _report():
                self.server.report_product(detection_info)
            threading.Thread(target=_report, daemon=True).start()
    
    def _detection_worker(self):
        """
        异步检测工作线程
        独立运行YOLO检测，不阻塞主线程的画面显示
        """
        print("🔄 异步检测线程已启动")
        
        while self._detection_running:
            # 获取最新帧
            with self._frame_lock:
                if self._latest_frame is None:
                    time.sleep(0.01)
                    continue
                frame = self._latest_frame.copy()
            
            # 执行检测（这是耗时操作）
            current_mode = self.get_mode()
            
            try:
                if current_mode == DetectionMode.ZONE:
                    processed_frame, detection_info = self.zone_detector.detect(frame)
                else:
                    processed_frame, detection_info = self.product_detector.detect(frame)
                
                # 保存检测结果
                with self._result_lock:
                    self._latest_result = detection_info
                    self._latest_processed_frame = processed_frame
                
                # 上报检测结果
                self._report_detection(detection_info)
                
            except Exception as e:
                print(f"检测线程错误: {e}")
                time.sleep(0.1)
        
        print("🔄 异步检测线程已停止")
    
    def _draw_overlay_on_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        在原始帧上绘制检测结果叠加层
        使用最新的检测结果，但不阻塞等待新检测
        """
        h, w = frame.shape[:2]
        output = frame.copy()
        
        # 获取最新检测结果
        with self._result_lock:
            detection_info = self._latest_result
            processed_frame = self._latest_processed_frame
        
        current_mode = self.get_mode()
        
        if current_mode == DetectionMode.ZONE:
            # 绘制危险区域和安全区域
            overlay = output.copy()
            for zone in self.zone_detector.danger_zones:
                cv2.fillPoly(overlay, [zone], (0, 0, 200))
                cv2.polylines(output, [zone], True, (0, 0, 255), 2)
            for zone in self.zone_detector.safe_zones:
                cv2.fillPoly(overlay, [zone], (0, 200, 0))
                cv2.polylines(output, [zone], True, (0, 255, 0), 2)
            cv2.addWeighted(overlay, 0.3, output, 0.7, 0, output)
            
            # 绘制警戒线
            mid_x = w // 2
            cv2.line(output, (mid_x, 0), (mid_x, h), (0, 255, 255), 2)
            cv2.putText(output, "WARNING LINE", (mid_x + 10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # 绘制检测框（使用缓存的检测结果）
            for detection in self.zone_detector.last_detections:
                x1, y1, x2, y2, conf = detection
                center = self.zone_detector._get_person_center((x1, y1, x2, y2))
                in_danger = any(self.zone_detector._point_in_zone(center, zone) 
                               for zone in self.zone_detector.danger_zones)
                
                if in_danger:
                    color = (0, 0, 255)
                    label = "DANGER!"
                else:
                    color = (0, 255, 0)
                    label = "Person"
                
                cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
                cv2.putText(output, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                cv2.circle(output, center, 4, color, -1)
            
            # 显示统计信息
            stats = self.zone_detector.statistics
            y_offset = 30
            
            if stats.current_in_danger > 0:
                cv2.putText(output, f"WARNING: {stats.current_in_danger} in DANGER ZONE!", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                y_offset += 30
            
            cv2.putText(output, f"Persons: {len(self.zone_detector.last_detections)}", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 25
            
            cv2.putText(output, f"In Danger: {stats.current_in_danger}", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            y_offset += 25
            
            cv2.putText(output, f"Entries: {stats.total_entries} | Exits: {stats.total_exits}", (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 100), 1)
            
            cv2.putText(output, "[ZONE MODE - ASYNC]", (w - 200, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        else:
            # 产品检测模式 - 使用处理后的帧（如果有）
            if processed_frame is not None and detection_info and detection_info.get("mode") == "product":
                return processed_frame
            
            # 绘制检测区域
            cv2.rectangle(output, (50, 50), (w-50, h-50), (100, 100, 100), 2)
            cv2.putText(output, "Detection Area", (55, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
            
            # 统计信息
            cv2.putText(output, f"Product A: {self.product_detector.detection_count['product_a']}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.product_detector.COLOR_RANGES["blue"]["display_color"], 2)
            cv2.putText(output, f"Product B: {self.product_detector.detection_count['product_b']}", (10, 55),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.product_detector.COLOR_RANGES["cyan"]["display_color"], 2)
            
            cv2.putText(output, "[PRODUCT MODE - ASYNC]", (w - 220, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 150, 50), 2)
        
        return output
    
    def run(self, headless: bool = False):
        """运行检测系统"""
        # 初始化检测器
        self.init_detectors()
        
        # 打开摄像头 - 支持树莓派CSI摄像头
        self.picam2 = None  # picamera2 实例
        self.use_picamera2 = False
        
        if IS_LINUX and PICAMERA2_AVAILABLE:
            # 优先使用 picamera2（树莓派CSI摄像头最佳方案）
            try:
                print("尝试使用 picamera2 打开摄像头...")
                self.picam2 = Picamera2()
                config = self.picam2.create_preview_configuration(
                    main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"}
                )
                self.picam2.configure(config)
                self.picam2.start()
                self.use_picamera2 = True
                print("✓ 使用 picamera2 打开摄像头成功")
            except Exception as e:
                print(f"picamera2 打开失败: {e}")
                self.picam2 = None
        
        if not self.use_picamera2:
            if IS_LINUX:
                # 树莓派CSI摄像头 - 尝试其他方式
                camera_opened = False
                
                # 方法1: 使用 /dev/video0
                print("尝试打开摄像头...")
                self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
                if self.cap.isOpened():
                    camera_opened = True
                    print("✓ 使用 V4L2 打开摄像头成功")
                
                # 方法2: 直接打开
                if not camera_opened:
                    print("尝试直接打开摄像头...")
                    self.cap = cv2.VideoCapture(self.camera_id)
                    if self.cap.isOpened():
                        camera_opened = True
                        print("✓ 直接打开摄像头成功")
                
                if camera_opened:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                    self.cap.set(cv2.CAP_PROP_FPS, 30)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            else:
                # Windows/其他系统使用默认方式
                self.cap = cv2.VideoCapture(self.camera_id)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not self.use_picamera2 and (self.cap is None or not self.cap.isOpened()):
            print("错误：无法打开摄像头")
            print("提示：如果使用树莓派CSI摄像头，请尝试：")
            print("  1. 运行 'rpicam-hello' 确认摄像头正常")
            print("  2. 确保已安装 picamera2: sudo apt install python3-picamera2")
            return
        
        
        print("\n" + "="*60)
        print("🎬 统一检测系统已启动")
        print(f"📹 摄像头: {self.camera_id} | 分辨率: {CAMERA_WIDTH}x{CAMERA_HEIGHT}")
        print("-"*60)
        print("操作说明:")
        print("  '1' - 切换到危险区域检测模式")
        print("  '2' - 切换到产品检测模式")
        print("  'c' - 手动捕获产品（产品模式下）")
        print("  'r' - 重置计数（产品计数/危险区统计）")
        print("  's' - 显示当前统计信息")
        print("  'q' - 退出程序")
        print("-"*60)
        print("🔔 危险区域检测说明:")
        print("  - 人员进入危险区：报警一次 + 统计进入次数")
        print("  - 人员离开危险区：通知一次 + 统计离开次数")
        print("  - 实时显示当前停留在危险区的人数")
        print("="*60 + "\n")
        
        self.running = True
        window_name = "Unified Detection System"
        
        if not headless:
            cv2.namedWindow(window_name)
        
        # ========== 启动异步检测线程 ==========
        self._detection_running = True
        self._detection_thread = threading.Thread(target=self._detection_worker, daemon=True)
        self._detection_thread.start()
        print("✓ 异步检测模式已启用（画面流畅，检测独立运行）")
        
        # 启动时初始化LED状态（绿灯亮表示系统正常）
        self.gpio.set_led_state(red=False, blue=False, green=True)
        print("✓ LED状态已初始化（绿灯亮 = 系统正常）")
        
        fps_start_time = time.time()
        fps_frame_count = 0
        fps = 0
        
        try:
            while self.running:
                # 读取帧 - 支持 picamera2 和 OpenCV
                if self.use_picamera2:
                    frame = self.picam2.capture_array()
                    # picamera2 返回 RGB，需要转换为 BGR（OpenCV格式）
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    ret = True
                else:
                    ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    print("错误：无法读取帧")
                    break
                
                # 更新最新帧供检测线程使用
                with self._frame_lock:
                    self._latest_frame = frame.copy()
                
                # 检查服务器模式（低频率）
                self._check_mode_from_server()
                
                # 更新环境阈值（每30秒一次）
                self._update_thresholds_from_server()
                
                # 上报温湿度传感器数据（每5秒一次）
                self._report_sensor_data()
                
                # 在原始帧上绘制检测结果叠加层（不阻塞）
                display_frame = self._draw_overlay_on_frame(frame)
                
                # 推送视频流
                if ENABLE_VIDEO_STREAM:
                    with self._result_lock:
                        detection_info = self._latest_result
                    if detection_info:
                        self._stream_frame(display_frame, detection_info)
                
                # 计算FPS
                fps_frame_count += 1
                if fps_frame_count >= 10:
                    fps = fps_frame_count / (time.time() - fps_start_time)
                    fps_start_time = time.time()
                    fps_frame_count = 0
                
                cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, CAMERA_HEIGHT - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # 显示操作提示
                cv2.putText(display_frame, "1:Zone 2:Product c:Capture r:Reset q:Quit",
                           (10, CAMERA_HEIGHT - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                
                if not headless:
                    cv2.imshow(window_name, display_frame)
                    key = cv2.waitKey(1) & 0xFF
                    
                    if key == ord('q'):
                        print("\n正在退出...")
                        break
                    elif key == ord('1'):
                        self.set_mode(DetectionMode.ZONE)
                    elif key == ord('2'):
                        self.set_mode(DetectionMode.PRODUCT)
                    elif key == ord('c') and self.get_mode() == DetectionMode.PRODUCT:
                        result = self.product_detector.capture(frame)
                        if result and self.server:
                            self.server.report_product(result)
                    elif key == ord('r'):
                        # 重置计数
                        if self.get_mode() == DetectionMode.PRODUCT:
                            self.product_detector.reset_count()
                        else:
                            self.zone_detector.reset_statistics()
                    elif key == ord('s'):
                        # 显示统计信息
                        self._print_statistics()
                else:
                    time.sleep(0.01)
                    
        except KeyboardInterrupt:
            print("\n\n收到中断信号，正在退出...")
        finally:
            self.running = False
            
            # 停止检测线程
            self._detection_running = False
            if self._detection_thread and self._detection_thread.is_alive():
                self._detection_thread.join(timeout=2.0)
                print("✓ 检测线程已停止")
            
            # 释放摄像头资源
            if self.use_picamera2 and self.picam2:
                self.picam2.stop()
                print("✓ picamera2 已停止")
            elif self.cap:
                self.cap.release()
            if not headless:
                cv2.destroyAllWindows()
            
            # 清理传感器和GPIO
            self.dht_sensor.cleanup()
            self.gpio.cleanup()
            print("✓ 程序已安全退出")
            self._print_statistics()
    
    def _print_statistics(self):
        """打印统计信息"""
        print("\n" + "="*50)
        print("📊 统计信息汇总")
        print("="*50)
        
        # 危险区域统计
        zone_stats = self.zone_detector.get_statistics()
        print("\n🚨 危险区域检测统计:")
        print(f"  总进入次数: {zone_stats['total_entries']}")
        print(f"  总离开次数: {zone_stats['total_exits']}")
        print(f"  当前危险区人数: {zone_stats['current_in_danger']}")
        
        # 产品检测统计
        print(f"\n📦 产品检测统计:")
        print(f"  产品A: {self.product_detector.detection_count['product_a']}")
        print(f"  产品B: {self.product_detector.detection_count['product_b']}")
        print("="*50)


# ==================== 主程序入口 ====================
if __name__ == "__main__":
    system = UnifiedDetectionSystem(camera_id=0)
    system.run(headless=False)
