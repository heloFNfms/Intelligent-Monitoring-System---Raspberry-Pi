"""
传送带模拟管理器 - 管理传送带状态和物品
整合到主后端服务中
"""
import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ConveyorItem:
    """传送带上的物品"""
    id: int
    position: float  # 0-100 位置百分比
    item_type: str   # product_a / product_b
    color: str
    shape: str       # box / cylinder
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


class ConveyorManager:
    """
    传送带管理器
    
    管理传送带的运行状态、物品生成和移动
    与生产状态同步
    """
    
    # 产品类型配置
    PRODUCT_TYPES = {
        "product_a": {"color": "#3a91c7", "shape": "box", "name": "产品A"},
        "product_b": {"color": "#2db7b5", "shape": "cylinder", "name": "产品B"},
    }
    
    def __init__(self):
        # 传送带状态
        self.is_running: bool = False
        self.speed: float = 1.0  # 速度倍率 0.5-2.0
        self.product_mode: str = "product_a"
        
        # 物品管理
        self.items: List[ConveyorItem] = []
        self.item_counter: int = 0
        self.completed_count: int = 0
        
        # 自动生成配置
        self.auto_generate: bool = True
        self.generate_interval: float = 2.5  # 生成间隔（秒）
        self.last_generate_time: float = 0
        self.max_items: int = 8  # 最大物品数
        
        # 运行控制
        self._running_task: Optional[asyncio.Task] = None
        self._broadcast_callback = None
    
    def set_broadcast_callback(self, callback):
        """设置广播回调函数"""
        self._broadcast_callback = callback
    
    def start(self):
        """启动传送带"""
        self.is_running = True
        self.last_generate_time = time.time()
    
    def stop(self):
        """停止传送带"""
        self.is_running = False
    
    def pause(self):
        """暂停传送带"""
        self.is_running = False
    
    def set_speed(self, speed: float):
        """设置速度 (0.5-2.0)"""
        self.speed = max(0.5, min(2.0, speed))
    
    def set_mode(self, mode: str):
        """设置产品模式"""
        if mode in self.PRODUCT_TYPES:
            self.product_mode = mode
    
    def sync_with_production(self, status: str, mode: str):
        """
        与生产状态同步
        
        Args:
            status: running/stopped/paused
            mode: product_a/product_b
        """
        if status == "running":
            self.start()
        elif status == "stopped":
            self.stop()
            self.items.clear()  # 停止时清空传送带上的物品
            # 注意：不重置 completed_count，因为它与数据库中的生产计数同步
        elif status == "paused":
            self.pause()
        
        self.set_mode(mode)
    
    def generate_item(self) -> Optional[ConveyorItem]:
        """生成新物品"""
        if len(self.items) >= self.max_items:
            return None
        
        # 检查入口是否有空间（前15%位置不能有物品）
        if any(item.position < 15 for item in self.items):
            return None
        
        self.item_counter += 1
        product = self.PRODUCT_TYPES[self.product_mode]
        
        item = ConveyorItem(
            id=self.item_counter,
            position=0,
            item_type=self.product_mode,
            color=product["color"],
            shape=product["shape"],
            created_at=time.time()
        )
        self.items.append(item)
        return item
    
    def update(self, delta_time: float) -> dict:
        """
        更新传送带状态
        
        Args:
            delta_time: 时间增量（秒）
        
        Returns:
            事件字典 {items_added, items_removed, items_updated}
        """
        events = {
            "items_added": [],
            "items_removed": [],
            "completed": False
        }
        
        if not self.is_running:
            return events
        
        current_time = time.time()
        
        # 自动生成物品
        if self.auto_generate:
            time_since_last = current_time - self.last_generate_time
            adjusted_interval = self.generate_interval / self.speed
            
            if time_since_last >= adjusted_interval:
                new_item = self.generate_item()
                if new_item:
                    events["items_added"].append(new_item.to_dict())
                    self.last_generate_time = current_time
        
        # 更新物品位置
        move_distance = 12 * self.speed * delta_time  # 每秒移动12%
        
        items_to_remove = []
        for item in self.items:
            item.position += move_distance
            
            # 物品到达终点
            if item.position >= 100:
                items_to_remove.append(item)
                self.completed_count += 1
                events["completed"] = True
        
        # 移除完成的物品
        for item in items_to_remove:
            self.items.remove(item)
            events["items_removed"].append(item.to_dict())
        
        return events
    
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
    
    def add_item_manual(self) -> Optional[dict]:
        """手动添加物品"""
        item = self.generate_item()
        return item.to_dict() if item else None
    
    def clear_items(self):
        """清空所有物品"""
        self.items.clear()
    
    def reset(self):
        """重置传送带"""
        self.items.clear()
        self.completed_count = 0
        self.item_counter = 0
        self.is_running = False


# 全局传送带管理器实例（按设备ID管理）
conveyor_managers: Dict[str, ConveyorManager] = {}


def get_conveyor_manager(device_id: str) -> ConveyorManager:
    """获取或创建设备的传送带管理器"""
    if device_id not in conveyor_managers:
        conveyor_managers[device_id] = ConveyorManager()
    return conveyor_managers[device_id]
