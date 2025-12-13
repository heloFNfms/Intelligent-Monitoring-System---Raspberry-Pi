"""
传送带模拟服务 - 独立的WebSocket服务
控制传送带运动和物品生成
"""
import asyncio
import json
import random
import time
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="传送带模拟服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConveyorSimulator:
    """传送带模拟器"""
    
    def __init__(self):
        # 传送带状态
        self.is_running = False
        self.speed = 1.0  # 速度倍率 0.5-2.0
        self.direction = 1  # 1=正向, -1=反向
        
        # 物品管理
        self.items: list = []  # 传送带上的物品
        self.item_counter = 0  # 物品ID计数器
        self.completed_count = 0  # 完成的物品数量
        
        # 物品生成配置
        self.auto_generate = True  # 自动生成物品
        self.generate_interval = 2.0  # 生成间隔（秒）
        self.last_generate_time = 0
        
        # 产品类型配置
        self.product_mode = "product_a"
        self.product_types = {
            "product_a": {"color": "#3a91c7", "shape": "box", "name": "产品A"},
            "product_b": {"color": "#2db7b5", "shape": "cylinder", "name": "产品B"},
        }
        
        # WebSocket连接
        self.connections: Set[WebSocket] = set()
    
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
        if mode in self.product_types:
            self.product_mode = mode
    
    def generate_item(self) -> dict:
        """生成新物品"""
        self.item_counter += 1
        product = self.product_types[self.product_mode]
        
        item = {
            "id": self.item_counter,
            "position": 0,  # 0-100 表示在传送带上的位置百分比
            "type": self.product_mode,
            "color": product["color"],
            "shape": product["shape"],
            "name": product["name"],
            "created_at": time.time()
        }
        self.items.append(item)
        return item
    
    def update(self, delta_time: float) -> dict:
        """
        更新传送带状态
        返回状态变化信息
        """
        events = {
            "items_added": [],
            "items_removed": [],
            "items_updated": []
        }
        
        if not self.is_running:
            return events
        
        # 自动生成物品
        current_time = time.time()
        if self.auto_generate:
            if current_time - self.last_generate_time >= self.generate_interval / self.speed:
                # 检查入口是否有空间
                if not any(item["position"] < 10 for item in self.items):
                    new_item = self.generate_item()
                    events["items_added"].append(new_item)
                    self.last_generate_time = current_time
        
        # 更新物品位置
        move_distance = 15 * self.speed * delta_time * self.direction
        
        items_to_remove = []
        for item in self.items:
            item["position"] += move_distance
            events["items_updated"].append(item)
            
            # 物品到达终点
            if item["position"] >= 100:
                items_to_remove.append(item)
                self.completed_count += 1
        
        # 移除完成的物品
        for item in items_to_remove:
            self.items.remove(item)
            events["items_removed"].append(item)
        
        return events
    
    def get_state(self) -> dict:
        """获取完整状态"""
        return {
            "is_running": self.is_running,
            "speed": self.speed,
            "direction": self.direction,
            "product_mode": self.product_mode,
            "items": self.items.copy(),
            "completed_count": self.completed_count,
            "auto_generate": self.auto_generate
        }
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        dead_connections = set()
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except:
                dead_connections.add(ws)
        
        self.connections -= dead_connections


# 全局模拟器实例
simulator = ConveyorSimulator()


@app.websocket("/ws/conveyor")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    await websocket.accept()
    simulator.connections.add(websocket)
    
    # 发送初始状态
    await websocket.send_json({
        "type": "init",
        "data": simulator.get_state()
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            await handle_command(data, websocket)
    except WebSocketDisconnect:
        simulator.connections.discard(websocket)


async def handle_command(data: dict, websocket: WebSocket):
    """处理控制命令"""
    cmd = data.get("command")
    params = data.get("params", {})
    
    response = {"type": "response", "command": cmd, "success": True}
    
    if cmd == "start":
        simulator.start()
        response["message"] = "传送带已启动"
    
    elif cmd == "stop":
        simulator.stop()
        response["message"] = "传送带已停止"
    
    elif cmd == "pause":
        simulator.pause()
        response["message"] = "传送带已暂停"
    
    elif cmd == "set_speed":
        speed = params.get("speed", 1.0)
        simulator.set_speed(speed)
        response["message"] = f"速度已设置为 {simulator.speed}"
    
    elif cmd == "set_mode":
        mode = params.get("mode", "product_a")
        simulator.set_mode(mode)
        response["message"] = f"已切换到 {mode}"
    
    elif cmd == "add_item":
        if len(simulator.items) < 10:  # 限制最大物品数
            item = simulator.generate_item()
            response["item"] = item
            response["message"] = "已添加物品"
        else:
            response["success"] = False
            response["message"] = "传送带已满"
    
    elif cmd == "clear_items":
        simulator.items.clear()
        response["message"] = "已清空物品"
    
    elif cmd == "toggle_auto":
        simulator.auto_generate = not simulator.auto_generate
        response["message"] = f"自动生成: {'开启' if simulator.auto_generate else '关闭'}"
    
    elif cmd == "get_state":
        response["data"] = simulator.get_state()
    
    else:
        response["success"] = False
        response["message"] = f"未知命令: {cmd}"
    
    await websocket.send_json(response)
    
    # 广播状态更新
    await simulator.broadcast({
        "type": "state_update",
        "data": simulator.get_state()
    })


async def simulation_loop():
    """模拟循环 - 定时更新传送带状态"""
    last_time = time.time()
    
    while True:
        current_time = time.time()
        delta_time = current_time - last_time
        last_time = current_time
        
        # 更新模拟器
        events = simulator.update(delta_time)
        
        # 如果有变化，广播更新
        if simulator.is_running or events["items_added"] or events["items_removed"]:
            await simulator.broadcast({
                "type": "tick",
                "data": {
                    "items": simulator.items,
                    "completed_count": simulator.completed_count,
                    "is_running": simulator.is_running
                },
                "events": events
            })
        
        await asyncio.sleep(0.05)  # 20 FPS


@app.on_event("startup")
async def startup():
    """启动时开始模拟循环"""
    asyncio.create_task(simulation_loop())
    print("�icing 传送带模拟服务已启动")
    print("📡 WebSocket: ws://localhost:8001/ws/conveyor")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "conveyor-simulator"}


@app.get("/state")
async def get_state():
    """HTTP接口获取状态"""
    return simulator.get_state()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
