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

# ==================== 配置 ====================
#SERVER_URL = "http://localhost:8000"
"树莓派使用"
SERVER_URL = "http://192.168.137.1:8000"

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
    """产品检测器 - 基于颜色和形状"""
    
    COLOR_RANGES = {
        "product_a": {
            "lower": np.array([100, 100, 100]),
            "upper": np.array([130, 255, 255]),
            "name": "蓝色",
            "display_color": (255, 150, 50)
        },
        "product_b": {
            "lower": np.array([75, 100, 100]),
            "upper": np.array([95, 255, 255]),
            "name": "青色",
            "display_color": (200, 200, 50)
        }
    }
    
    SHAPE_CIRCULARITY_THRESHOLD = 0.7
    MIN_CONTOUR_AREA = 1000
    MAX_CONTOUR_AREA = 100000
    
    def __init__(self):
        self.detection_count = {"product_a": 0, "product_b": 0, "unknown": 0}
        self.last_detection_time = 0
        self.detection_cooldown = 1.0
        print("✓ 产品检测器初始化完成")
    
    def detect_color(self, frame: np.ndarray) -> Tuple[str, np.ndarray]:
        """检测颜色"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        best_match = "unknown"
        best_area = 0
        best_mask = None
        
        for product_type, color_range in self.COLOR_RANGES.items():
            mask = cv2.inRange(hsv, color_range["lower"], color_range["upper"])
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            area = cv2.countNonZero(mask)
            
            if area > best_area and area > self.MIN_CONTOUR_AREA:
                best_area = area
                best_match = product_type
                best_mask = mask
        
        return best_match, best_mask if best_mask is not None else np.zeros_like(frame[:,:,0])
    
    def detect_shape(self, mask: np.ndarray) -> Tuple[str, List[np.ndarray]]:
        """检测形状"""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return "unknown", []
        
        valid_contours = [c for c in contours
                        if self.MIN_CONTOUR_AREA < cv2.contourArea(c) < self.MAX_CONTOUR_AREA]
        if not valid_contours:
            return "unknown", []
        
        largest = max(valid_contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        perimeter = cv2.arcLength(largest, True)
        
        if perimeter == 0:
            return "unknown", valid_contours
        
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        shape = "circle" if circularity > self.SHAPE_CIRCULARITY_THRESHOLD else "rectangle"
        return shape, valid_contours
    
    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, dict]:
        """执行产品检测"""
        output = frame.copy()
        h, w = output.shape[:2]
        
        # 颜色检测
        color_type, mask = self.detect_color(frame)
        
        # 形状检测
        shape_type, contours = self.detect_shape(mask)
        
        # 综合判断
        result = {
            "mode": "product",
            "detected": False,
            "product_type": "unknown",
            "color": "unknown",
            "shape": "unknown",
            "confidence": 0.0
        }
        
        if color_type != "unknown" and shape_type != "unknown":
            if color_type == "product_a" and shape_type == "rectangle":
                product_type, confidence = "product_a", 0.9
            elif color_type == "product_b" and shape_type == "circle":
                product_type, confidence = "product_b", 0.9
            elif color_type in ["product_a", "product_b"]:
                product_type, confidence = color_type, 0.7
            else:
                product_type, confidence = "unknown", 0.3
            
            result.update({
                "detected": True,
                "product_type": product_type,
                "color": self.COLOR_RANGES.get(color_type, {}).get("name", "未知"),
                "shape": "圆形" if shape_type == "circle" else "方形",
                "confidence": confidence
            })
            
            # 绘制轮廓
            if contours:
                color = self.COLOR_RANGES.get(color_type, {}).get("display_color", (128, 128, 128))
                cv2.drawContours(output, contours, -1, color, 3)
                
                largest = max(contours, key=cv2.contourArea)
                x, y, bw, bh = cv2.boundingRect(largest)
                cv2.rectangle(output, (x, y), (x+bw, y+bh), color, 2)
                
                label = f"Product {'A' if product_type == 'product_a' else 'B'}"
                cv2.putText(output, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                cv2.putText(output, f"Conf: {confidence:.0%}", (x, y+bh+20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # 绘制检测区域
        cv2.rectangle(output, (50, 50), (w-50, h-50), (100, 100, 100), 2)
        cv2.putText(output, "Detection Area", (55, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        
        # 统计信息
        cv2.putText(output, f"Product A: {self.detection_count['product_a']}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_RANGES["product_a"]["display_color"], 2)
        cv2.putText(output, f"Product B: {self.detection_count['product_b']}", (10, 55),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_RANGES["product_b"]["display_color"], 2)
        
        # 模式标识
        cv2.putText(output, "[PRODUCT MODE]", (w - 180, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 150, 50), 2)
        
        return output, result
    
    def capture(self, frame: np.ndarray) -> Optional[dict]:
        """手动捕获检测"""
        current_time = time.time()
        if current_time - self.last_detection_time < self.detection_cooldown:
            return None
        
        _, result = self.detect(frame)
        if result["detected"] and result["product_type"] != "unknown":
            self.last_detection_time = current_time
            self.detection_count[result["product_type"]] += 1
            print(f"\n📦 检测到产品: {result['product_type']} | {result['color']} | {result['shape']}")
            return result
        return None
    
    def reset_count(self):
        """重置计数"""
        self.detection_count = {"product_a": 0, "product_b": 0, "unknown": 0}
        print("✓ 产品计数已重置")



# ==================== GPIO控制器 ====================
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
                print(f"✓ GPIO初始化成功 | LED: {led_pin} | 蜂鸣器: {buzzer_pin}")
            except ImportError:
                print("⚠️ RPi.GPIO未安装，GPIO功能禁用")
            except Exception as e:
                print(f"⚠️ GPIO初始化失败: {e}")
    
    def turn_on_led(self):
        if self.gpio_initialized and not self.led_state:
            self.GPIO.output(self.led_pin, self.GPIO.HIGH)
            self.led_state = True
    
    def turn_off_led(self):
        if self.gpio_initialized and self.led_state:
            self.GPIO.output(self.led_pin, self.GPIO.LOW)
            self.led_state = False
    
    def buzzer_beep(self, duration: float = 0.5):
        if self.gpio_initialized:
            self.GPIO.output(self.buzzer_pin, self.GPIO.HIGH)
            time.sleep(duration)
            self.GPIO.output(self.buzzer_pin, self.GPIO.LOW)
    
    def cleanup(self):
        if self.gpio_initialized:
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
        
        # GPIO控制器
        self.gpio = GPIOController()
        
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
        
        # 初始化产品检测器
        self.product_detector = ProductDetector()
        
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
        
        # LED报警（红灯闪烁）
        def _led():
            self.gpio.turn_on_led()
            time.sleep(3.0)
            self.gpio.turn_off_led()
        threading.Thread(target=_led, daemon=True).start()
        
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
                winsound.Beep(500, 200)  # 低频提示音
            elif IS_LINUX:
                self.gpio.buzzer_beep(0.2)
        threading.Thread(target=_notify, daemon=True).start()
        
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
        
        elif mode == "product" and detection_info.get("detected"):
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
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.product_detector.COLOR_RANGES["product_a"]["display_color"], 2)
            cv2.putText(output, f"Product B: {self.product_detector.detection_count['product_b']}", (10, 55),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.product_detector.COLOR_RANGES["product_b"]["display_color"], 2)
            
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
