"""
产品检测系统 - 检测传送带上物品的颜色和形状
功能：
1. 打开摄像头识别物品
2. 根据颜色判断产品类型（蓝色=产品A，青色=产品B）
3. 根据形状判断产品类型（方形=产品A，圆形=产品B）
4. 上报检测结果到后端

适用于：树莓派摄像头 / 笔记本摄像头
"""

import cv2
import numpy as np
from datetime import datetime
from typing import Tuple, Optional, Dict, List
import time
import threading
import platform
import base64
import requests

# 检测操作系统
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# ==================== 服务器配置 ====================
SERVER_URL = "http://localhost:8000"
DEVICE_ID = "device_001"
ENABLE_SERVER_REPORT = True
ENABLE_VIDEO_STREAM = True
VIDEO_STREAM_FPS = 10
VIDEO_QUALITY = 60


class ProductDetector:
    """
    产品检测器 - 基于颜色和形状识别产品类型
    
    产品A: 蓝色 + 方形
    产品B: 青色 + 圆形
    """
    
    # 颜色范围定义 (HSV)
    COLOR_RANGES = {
        "product_a": {  # 蓝色
            "lower": np.array([100, 100, 100]),
            "upper": np.array([130, 255, 255]),
            "name": "蓝色",
            "display_color": (255, 150, 50)  # BGR
        },
        "product_b": {  # 青色
            "lower": np.array([75, 100, 100]),
            "upper": np.array([95, 255, 255]),
            "name": "青色",
            "display_color": (200, 200, 50)  # BGR
        },
        "red": {  # 红色（可用于不合格品）
            "lower": np.array([0, 100, 100]),
            "upper": np.array([10, 255, 255]),
            "name": "红色",
            "display_color": (50, 50, 255)
        }
    }
    
    # 形状判断参数
    SHAPE_CIRCULARITY_THRESHOLD = 0.7  # 圆形度阈值
    MIN_CONTOUR_AREA = 1000  # 最小轮廓面积
    MAX_CONTOUR_AREA = 100000  # 最大轮廓面积
    
    def __init__(self):
        self.detection_count = {
            "product_a": 0,
            "product_b": 0,
            "unknown": 0
        }
        self.last_detection_time = 0
        self.detection_cooldown = 1.0  # 检测冷却时间（秒）
        self.last_stream_time = 0
        self.stream_interval = 1.0 / VIDEO_STREAM_FPS
        
        print("✓ 产品检测器初始化完成")
        print(f"  产品A: 蓝色方形")
        print(f"  产品B: 青色圆形")
    
    def detect_color(self, frame: np.ndarray, roi: Tuple[int, int, int, int] = None) -> Tuple[str, np.ndarray]:
        """
        检测图像中的主要颜色
        
        Args:
            frame: BGR图像
            roi: 感兴趣区域 (x, y, w, h)，None表示全图
        
        Returns:
            (产品类型, 掩码图像)
        """
        if roi:
            x, y, w, h = roi
            region = frame[y:y+h, x:x+w]
        else:
            region = frame
        
        # 转换到HSV色彩空间
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        
        best_match = "unknown"
        best_area = 0
        best_mask = None
        
        for product_type, color_range in self.COLOR_RANGES.items():
            if product_type not in ["product_a", "product_b"]:
                continue
                
            # 创建颜色掩码
            mask = cv2.inRange(hsv, color_range["lower"], color_range["upper"])
            
            # 形态学操作去噪
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            # 计算颜色区域面积
            area = cv2.countNonZero(mask)
            
            if area > best_area and area > self.MIN_CONTOUR_AREA:
                best_area = area
                best_match = product_type
                best_mask = mask
        
        return best_match, best_mask if best_mask is not None else np.zeros_like(frame[:,:,0])
    
    def detect_shape(self, mask: np.ndarray) -> Tuple[str, List[np.ndarray]]:
        """
        检测掩码中的形状
        
        Args:
            mask: 二值掩码图像
        
        Returns:
            (形状类型, 轮廓列表)
        """
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return "unknown", []
        
        # 找最大轮廓
        valid_contours = [c for c in contours 
                         if self.MIN_CONTOUR_AREA < cv2.contourArea(c) < self.MAX_CONTOUR_AREA]
        
        if not valid_contours:
            return "unknown", []
        
        largest_contour = max(valid_contours, key=cv2.contourArea)
        
        # 计算圆形度
        area = cv2.contourArea(largest_contour)
        perimeter = cv2.arcLength(largest_contour, True)
        
        if perimeter == 0:
            return "unknown", valid_contours
        
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        
        # 判断形状
        if circularity > self.SHAPE_CIRCULARITY_THRESHOLD:
            return "circle", valid_contours  # 圆形 -> 产品B
        else:
            return "rectangle", valid_contours  # 方形 -> 产品A
    
    def detect_product(self, frame: np.ndarray) -> Dict:
        """
        综合检测产品类型
        
        Args:
            frame: BGR图像
        
        Returns:
            检测结果字典
        """
        result = {
            "detected": False,
            "product_type": "unknown",
            "color": "unknown",
            "shape": "unknown",
            "confidence": 0.0,
            "contours": [],
            "bbox": None
        }
        
        # 1. 颜色检测
        color_type, mask = self.detect_color(frame)
        
        if color_type == "unknown":
            return result
        
        # 2. 形状检测
        shape_type, contours = self.detect_shape(mask)
        
        if shape_type == "unknown":
            return result
        
        # 3. 综合判断
        # 产品A: 蓝色 + 方形
        # 产品B: 青色 + 圆形
        if color_type == "product_a" and shape_type == "rectangle":
            product_type = "product_a"
            confidence = 0.9
        elif color_type == "product_b" and shape_type == "circle":
            product_type = "product_b"
            confidence = 0.9
        elif color_type == "product_a":
            product_type = "product_a"
            confidence = 0.7
        elif color_type == "product_b":
            product_type = "product_b"
            confidence = 0.7
        else:
            product_type = "unknown"
            confidence = 0.3
        
        # 计算边界框
        if contours:
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            result["bbox"] = (x, y, w, h)
        
        result.update({
            "detected": True,
            "product_type": product_type,
            "color": self.COLOR_RANGES.get(color_type, {}).get("name", "未知"),
            "shape": "圆形" if shape_type == "circle" else "方形",
            "confidence": confidence,
            "contours": contours
        })
        
        return result
    
    def draw_detection(self, frame: np.ndarray, result: Dict) -> np.ndarray:
        """
        在图像上绘制检测结果
        """
        output = frame.copy()
        h, w = output.shape[:2]
        
        # 绘制检测区域框
        cv2.rectangle(output, (50, 50), (w-50, h-50), (100, 100, 100), 2)
        cv2.putText(output, "Detection Area", (55, 45), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        
        if result["detected"]:
            # 绘制轮廓
            for contour in result["contours"]:
                if result["product_type"] == "product_a":
                    color = self.COLOR_RANGES["product_a"]["display_color"]
                elif result["product_type"] == "product_b":
                    color = self.COLOR_RANGES["product_b"]["display_color"]
                else:
                    color = (128, 128, 128)
                
                cv2.drawContours(output, [contour], -1, color, 3)
            
            # 绘制边界框和标签
            if result["bbox"]:
                x, y, bw, bh = result["bbox"]
                cv2.rectangle(output, (x, y), (x+bw, y+bh), color, 2)
                
                # 产品类型标签
                label = f"{result['product_type'].upper()}"
                if result["product_type"] == "product_a":
                    label = "Product A (Blue/Square)"
                elif result["product_type"] == "product_b":
                    label = "Product B (Cyan/Circle)"
                
                cv2.putText(output, label, (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
                # 置信度
                conf_text = f"Conf: {result['confidence']:.0%}"
                cv2.putText(output, conf_text, (x, y+bh+20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # 绘制统计信息
        stats_y = 30
        cv2.putText(output, f"Product A: {self.detection_count['product_a']}", 
                   (10, stats_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                   self.COLOR_RANGES["product_a"]["display_color"], 2)
        cv2.putText(output, f"Product B: {self.detection_count['product_b']}", 
                   (10, stats_y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                   self.COLOR_RANGES["product_b"]["display_color"], 2)
        
        # 操作提示
        cv2.putText(output, "Press 'c' to capture | 'r' to reset | 'q' to quit",
                   (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        return output
    
    def capture_and_detect(self, frame: np.ndarray) -> Dict:
        """
        捕获并检测产品（带冷却时间）
        """
        current_time = time.time()
        
        if current_time - self.last_detection_time < self.detection_cooldown:
            return None
        
        result = self.detect_product(frame)
        
        if result["detected"] and result["product_type"] != "unknown":
            self.last_detection_time = current_time
            self.detection_count[result["product_type"]] += 1
            
            print(f"\n{'='*50}")
            print(f"📦 检测到产品!")
            print(f"   类型: {result['product_type']}")
            print(f"   颜色: {result['color']}")
            print(f"   形状: {result['shape']}")
            print(f"   置信度: {result['confidence']:.0%}")
            print(f"{'='*50}\n")
            
            return result
        
        return None


class ProductDetectionServer:
    """产品检测服务器通信"""
    
    def __init__(self, server_url: str, device_id: str):
        self.server_url = server_url.rstrip('/')
        self.device_id = device_id
    
    def report_product_detection(self, result: Dict) -> bool:
        """上报产品检测结果"""
        try:
            data = {
                "device_id": self.device_id,
                "product_type": result["product_type"],
                "color": result["color"],
                "shape": result["shape"],
                "confidence": result["confidence"],
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.server_url}/api/product/detection",
                json=data,
                timeout=2
            )
            return response.status_code == 200
        except Exception as e:
            print(f"上报失败: {e}")
            return False
    
    def send_video_frame(self, frame: np.ndarray, detection_info: Dict = None) -> bool:
        """发送视频帧"""
        try:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), VIDEO_QUALITY]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            data = {
                "device_id": self.device_id,
                "frame": frame_base64,
                "timestamp": datetime.now().isoformat(),
                "detection_type": "product",
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


def run_product_detection(camera_id: int = 0, 
                          camera_width: int = 640, 
                          camera_height: int = 480,
                          headless: bool = False):
    """
    运行产品检测
    
    Args:
        camera_id: 摄像头ID
        camera_width: 摄像头宽度
        camera_height: 摄像头高度
        headless: 是否无头模式（无GUI）
    """
    # 初始化检测器
    detector = ProductDetector()
    
    # 初始化服务器客户端
    server = None
    if ENABLE_SERVER_REPORT:
        server = ProductDetectionServer(SERVER_URL, DEVICE_ID)
        print(f"✓ 服务器客户端已初始化: {SERVER_URL}")
    
    # 打开摄像头
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    if not cap.isOpened():
        print("错误：无法打开摄像头")
        return
    
    print("\n" + "="*60)
    print("🔍 产品检测系统已启动")
    print(f"📹 摄像头: {camera_id} | 分辨率: {camera_width}x{camera_height}")
    print("📦 产品A: 蓝色方形")
    print("📦 产品B: 青色圆形")
    print("-"*60)
    print("操作说明:")
    print("  'c' - 手动捕获检测")
    print("  'r' - 重置计数")
    print("  'q' - 退出程序")
    print("="*60 + "\n")
    
    window_name = "Product Detection"
    if not headless:
        cv2.namedWindow(window_name)
    
    last_stream_time = 0
    stream_interval = 1.0 / VIDEO_STREAM_FPS
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("错误：无法读取帧")
                break
            
            # 实时检测（用于显示）
            result = detector.detect_product(frame)
            
            # 绘制检测结果
            display_frame = detector.draw_detection(frame, result)
            
            # 推送视频流
            current_time = time.time()
            if ENABLE_VIDEO_STREAM and server and current_time - last_stream_time >= stream_interval:
                last_stream_time = current_time
                detection_info = {
                    "product_type": result.get("product_type", "unknown"),
                    "detected": result.get("detected", False)
                } if result["detected"] else None
                
                def _stream():
                    server.send_video_frame(display_frame, detection_info)
                thread = threading.Thread(target=_stream)
                thread.daemon = True
                thread.start()
            
            if not headless:
                cv2.imshow(window_name, display_frame)
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    print("\n正在退出...")
                    break
                elif key == ord('c'):
                    # 手动捕获检测
                    capture_result = detector.capture_and_detect(frame)
                    if capture_result and server:
                        def _report():
                            server.report_product_detection(capture_result)
                        thread = threading.Thread(target=_report)
                        thread.daemon = True
                        thread.start()
                elif key == ord('r'):
                    # 重置计数
                    detector.detection_count = {"product_a": 0, "product_b": 0, "unknown": 0}
                    print("✓ 计数已重置")
            else:
                time.sleep(0.01)
                
    except KeyboardInterrupt:
        print("\n\n收到中断信号，正在退出...")
    finally:
        cap.release()
        if not headless:
            cv2.destroyAllWindows()
        print("✓ 程序已安全退出")
        print(f"\n检测统计:")
        print(f"  产品A: {detector.detection_count['product_a']}")
        print(f"  产品B: {detector.detection_count['product_b']}")


if __name__ == "__main__":
    run_product_detection(
        camera_id=0,
        camera_width=640,
        camera_height=480,
        headless=False
    )
