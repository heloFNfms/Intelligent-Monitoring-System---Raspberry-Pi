# 传送带模拟服务

独立的传送带可视化模拟服务，通过 WebSocket 与前端实时通信。

## 启动服务

```bash
cd conveyor
pip install -r requirements.txt
python server.py
```

服务将在 `http://localhost:8001` 启动，WebSocket 端点为 `ws://localhost:8001/ws/conveyor`

## 功能

- 传送带运动模拟（启动/停止/暂停）
- 物品自动生成与传输
- 速度调节（0.5x - 2.0x）
- 产品模式切换（产品A/产品B）
- 实时状态同步

## WebSocket 命令

| 命令 | 参数 | 说明 |
|------|------|------|
| `start` | - | 启动传送带 |
| `stop` | - | 停止传送带 |
| `pause` | - | 暂停传送带 |
| `set_speed` | `{ speed: 0.5-2.0 }` | 设置速度 |
| `set_mode` | `{ mode: "product_a" \| "product_b" }` | 切换产品模式 |
| `add_item` | - | 手动添加物品 |
| `clear_items` | - | 清空所有物品 |
| `toggle_auto` | - | 切换自动生成 |
| `get_state` | - | 获取当前状态 |

## 与主系统集成

前端会自动连接传送带服务，并与主控制面板同步：
- 点击「启动」→ 传送带开始运行
- 点击「停止」→ 传送带停止
- 切换产品模式 → 传送带物品颜色/形状变化
