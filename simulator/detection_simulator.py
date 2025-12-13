"""
检测模拟器 - 模拟摄像头人员检测
完全模拟树莓派YOLOv8检测结果
"""
import random
from typing import Dict, Any, Tuple

from config import DANGER_ZONE_PROBABILITY


class DetectionSimulator:
    """检测模拟器 - 模拟YOLOv8人员检测"""
    
    def __init__(self):
        self._last_detection = None
        self._consecutive_danger = 0  # 连续危险次数
    
    def detect(self) -> Dict[str, Any]:
        """
        模拟一次检测
        
        Returns:
            {
                "person_count": int,
                "in_danger_zone": bool,
                "alert_triggered": bool,
                "bboxes": list  # 边界框列表（模拟）
            }
        """
        # 随机生成检测到的人数 (0-3人)
        person_count = random.choices(
            [0, 1, 2, 3],
            weights=[0.3, 0.4, 0.2, 0.1]  # 大部分时间0-1人
        )[0]
        
        # 判断是否在危险区域
        in_danger_zone = False
        alert_triggered = False
        
        if person_count > 0:
            # 有人时，按概率判断是否在危险区域
            in_danger_zone = random.random() < DANGER_ZONE_PROBABILITY
            
            # 如果在危险区域，触发报警
            if in_danger_zone:
                alert_triggered = True
                self._consecutive_danger += 1
            else:
                self._consecutive_danger = 0
        else:
            self._consecutive_danger = 0
        
        # 生成模拟的边界框
        bboxes = self._generate_bboxes(person_count, in_danger_zone)
        
        result = {
            "person_count": person_count,
            "in_danger_zone": in_danger_zone,
            "alert_triggered": alert_triggered,
            "bboxes": bboxes
        }
        
        self._last_detection = result
        return result
    
    def _generate_bboxes(self, count: int, in_danger: bool) -> list:
        """生成模拟的边界框"""
        bboxes = []
        
        # 假设画面尺寸 640x480，危险区域在右半部分
        for i in range(count):
            if in_danger and i == 0:
                # 第一个人在危险区域（右半部分）
                x1 = random.randint(320, 500)
            else:
                # 其他人在安全区域（左半部分）
                x1 = random.randint(50, 280)
            
            y1 = random.randint(100, 300)
            width = random.randint(60, 100)
            height = random.randint(150, 200)
            
            bboxes.append({
                "x1": x1,
                "y1": y1,
                "x2": x1 + width,
                "y2": y1 + height,
                "confidence": round(random.uniform(0.7, 0.95), 2)
            })
        
        return bboxes
    
    def get_last_detection(self) -> Dict[str, Any]:
        """获取上次检测结果"""
        return self._last_detection


# 测试
if __name__ == "__main__":
    detector = DetectionSimulator()
    
    print("检测模拟器测试")
    print("-" * 40)
    
    for i in range(10):
        result = detector.detect()
        status = "⚠️ 危险!" if result["in_danger_zone"] else "✓ 安全"
        print(f"检测 {i+1}: 人数={result['person_count']} {status}")
