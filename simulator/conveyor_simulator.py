"""
传送带模拟器 - 模拟传送带物品生成和移动
与后端传送带管理器配合使用
"""
import time
import random
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class SimulatedItem:
    """模拟的传送带物品"""
    id: int
    position: float
    item_type: str
    color: str
    shape: str
    created_at: float
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position": self.position,
            "type": self.item_type,
            "color": self.color,
            "shape": self.shape,
            "created_at": self.created_at
        }


class ConveyorSimulator:
    """
    传送带模拟器
    
    模拟传送带的运行状态、物品生成和移动
    用于开发测试，部署时由真实设备替代
    """
    
    PRODUCT_TYPES = {
        "product_a": {"color": "#3a91c7", "shape": "box"},
        "product_b": {"color": "#2db7b5", "shape": "cylinder"},
    }
    
    def __init__(self):
        self.is_running = False
        self.speed = 1.0
        self.product_mode = "product_a"
        
        self.items: List[SimulatedItem] = []
        self.item_counter = 0
        self.completed_count = 0
        
        self.auto_generate = True
        self.generate_interval = 2.5
        self.last_generate_time = 0
        self.max_items = 8
    
    def set_running(self, running: bool):
        """设置运行状态"""
        self.is_running = running
        if running:
            self.last_generate_time = time.time()
    
    def set_mode(self, mode: str):
        """设置产品模式"""
        if mode in self.PRODUCT_TYPES:
            self.product_mode = mode
    
    def sync_with_status(self, status: str, mode: str):
        """与生产状态同步"""
        if status == "running":
            self.set_running(True)
        elif status == "stopped":
            self.set_running(False)
            self.items.clear()
            self.completed_count = 0
        elif status == "paused":
            self.set_running(False)
        
        self.set_mode(mode)
    
    def generate_item(self) -> Optional[SimulatedItem]:
        """生成新物品"""
        if len(self.items) >= self.max_items:
            return None
        
        if any(item.position < 15 for item in self.items):
            return None
        
        self.item_counter += 1
        product = self.PRODUCT_TYPES[self.product_mode]
        
        item = SimulatedItem(
            id=self.item_counter,
            position=0,
            item_type=self.product_mode,
            color=product["color"],
            shape=product["shape"],
            created_at=time.time()
        )
        self.items.append(item)
        return item
    
    def update(self, delta_time: float) -> int:
        """
        更新传送带状态
        
        Returns:
            完成的物品数量
        """
        if not self.is_running:
            return 0
        
        current_time = time.time()
        completed = 0
        
        # 自动生成物品
        if self.auto_generate:
            time_since_last = current_time - self.last_generate_time
            adjusted_interval = self.generate_interval / self.speed
            
            if time_since_last >= adjusted_interval:
                if self.generate_item():
                    self.last_generate_time = current_time
        
        # 更新物品位置
        move_distance = 12 * self.speed * delta_time
        
        items_to_remove = []
        for item in self.items:
            item.position += move_distance
            
            if item.position >= 100:
                items_to_remove.append(item)
                self.completed_count += 1
                completed += 1
        
        for item in items_to_remove:
            self.items.remove(item)
        
        return completed
    
    def get_state(self) -> dict:
        """获取完整状态"""
        return {
            "is_running": self.is_running,
            "speed": self.speed,
            "product_mode": self.product_mode,
            "items": [item.to_dict() for item in self.items],
            "completed_count": self.completed_count,
            "auto_generate": self.auto_generate
        }


if __name__ == "__main__":
    # 测试
    conveyor = ConveyorSimulator()
    conveyor.set_running(True)
    
    print("传送带模拟器测试")
    print("-" * 40)
    
    last_time = time.time()
    for i in range(20):
        current_time = time.time()
        delta = current_time - last_time
        last_time = current_time
        
        completed = conveyor.update(delta)
        state = conveyor.get_state()
        
        print(f"物品数: {len(state['items'])}, 完成: {state['completed_count']}")
        time.sleep(0.5)
