# 智能生产线监控与调度系统

基于多源数据的智能生产线监控与调度系统，用于模拟小型生产线或设备集群的监控与调度。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (Vue3)                            │
│  - 实时监控大屏（温度曲线、生产状态、报警）                    │
│  - 传送带可视化动画                                          │
│  - 远程控制面板                                              │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket + HTTP API
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 后端服务 (FastAPI + MySQL)                   │
│  - 数据聚合与存储                                            │
│  - WebSocket 实时广播                                        │
│  - 控制指令下发                                              │
│  - 传送带状态管理                                            │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP API
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              设备层 (树莓派 / 模拟器)                         │
│                                                             │
│  【开发阶段】simulator/ → 模拟传感器 + 传送带数据              │
│  【部署阶段】树莓派 → 真实传感器 + 摄像头检测                   │
└─────────────────────────────────────────────────────────────┘
```

## 功能模块

### 1. 生产线模块（树莓派端 / 模拟器）
- ✅ 目标检测：YOLOv8检测人员进入危险区域
- ✅ 产品检测：基于颜色和形状识别产品类型（产品A/产品B）
- ✅ 传感器数据采集：温度、压力、湿度
- ✅ 传送带模拟：物品生成、移动、完成计数
- ✅ 报警控制：LED灯、蜂鸣器

### 2. 中心控制与数据服务模块（后端）
- ✅ 数据聚合：接收并存储设备数据
- ✅ 控制指令：下发启动/停止/切换模式指令
- ✅ 传送带管理：状态同步、物品追踪
- ✅ 自动调度：温度过高自动暂停、恢复后自动启动
- ✅ 生产计划：设置目标产量、达标自动停止
- ✅ API服务：提供REST API和WebSocket

### 3. 可视化与管理界面（前端）
- ✅ 实时监控大屏：温度曲线、生产状态
- ✅ 传送带可视化：动态显示物品移动
- ✅ 报警管理：报警列表、处理报警
- ✅ 远程控制：启动/停止/切换模式
- ✅ 生产计划管理：设置目标、查看进度
- ✅ 自动调度配置：启用/禁用调度规则

## 快速开始

### 1. 初始化数据库

```sql
-- 登录MySQL后执行
source backend/init_db.sql
```

或手动创建数据库：
```sql
CREATE DATABASE production_monitor CHARACTER SET utf8mb4;
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python run.py
```

后端启动后访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端访问：http://localhost:3000

### 4. 启动模拟器（无硬件时测试）

```bash
cd simulator
pip install aiohttp
python main.py
```

模拟器会自动上报传感器数据，后端会自动管理传送带状态。

## 项目结构

```
├── backend/                 # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── main.py         # FastAPI主应用（所有API接口）
│   │   ├── database.py     # 数据库模型定义
│   │   ├── schemas.py      # 请求/响应数据模型
│   │   ├── config.py       # 配置文件
│   │   ├── conveyor.py     # 传送带管理器
│   │   ├── scheduler.py    # 自动调度管理器
│   │   └── websocket_manager.py  # WebSocket连接管理
│   ├── run.py              # 启动脚本
│   ├── init_db.sql         # 数据库初始化SQL
│   └── requirements.txt
│
├── frontend/               # 前端应用 (Vue3)
│   ├── src/
│   │   ├── App.vue        # 监控大屏主界面
│   │   ├── components/    # 组件
│   │   │   └── ConveyorBelt.vue  # 传送带可视化组件
│   │   ├── api/           # API接口封装
│   │   └── utils/         # WebSocket工具
│   ├── package.json
│   └── vite.config.js
│
├── simulator/              # 设备模拟器（开发测试用）
│   ├── main.py            # 模拟器主程序
│   ├── sensor_simulator.py    # 传感器模拟
│   ├── conveyor_simulator.py  # 传送带模拟
│   ├── device_client.py   # 设备通信客户端
│   └── config.py          # 模拟器配置
│
├── project/                # 树莓派端代码（部署用）
│   ├── zone_detection.py  # YOLOv8区域检测（人员安全）
│   ├── product_detection.py  # 产品检测（颜色/形状识别）
│   └── device_client.py   # 设备通信客户端
│
└── docs/                   # 文档
    ├── 系统架构设计文档.md
    └── 接口设计文档.md
```

## 技术栈

| 模块 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + MySQL |
| 前端 | Vue3 + Element Plus + ECharts |
| 通信 | HTTP REST + WebSocket |
| 检测 | YOLOv8 + OpenCV |

## API 接口

### 传送带相关
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conveyor/{device_id}` | 获取传送带状态 |
| POST | `/api/conveyor/{device_id}/control` | 控制传送带 |

### 控制指令
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/control` | 发送控制指令（启动/停止/暂停/切换模式） |

### 调度管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scheduler/{device_id}` | 获取调度器状态 |
| GET | `/api/scheduler/{device_id}/rules` | 获取调度规则列表 |
| PUT | `/api/scheduler/{device_id}/rules/{rule_id}` | 更新调度规则 |
| POST | `/api/scheduler/{device_id}/plan` | 设置生产计划 |
| DELETE | `/api/scheduler/{device_id}/plan` | 清除生产计划 |
| GET | `/api/scheduler/{device_id}/progress` | 获取生产计划进度 |

### 产品检测
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/product/detection` | 上报产品检测结果 |

### WebSocket 消息类型
| 类型 | 说明 |
|------|------|
| `sensor_update` | 传感器数据更新 |
| `status_change` | 生产状态变化 |
| `conveyor_update` | 传送带状态更新 |
| `alert` | 报警信息 |
| `video_frame` | 视频帧 |
| `schedule_action` | 自动调度动作 |
| `product_detection` | 产品检测结果 |

## 配置说明

### 数据库配置
修改 `backend/app/config.py`：
```python
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "your_password"
DB_NAME = "production_monitor"
```

### 报警阈值
```python
TEMP_WARNING_THRESHOLD = 80.0  # 温度警告阈值
TEMP_DANGER_THRESHOLD = 95.0   # 温度危险阈值
```

## 树莓派部署

1. 将 `project/` 目录复制到树莓派
2. 安装依赖：`pip install ultralytics opencv-python aiohttp requests numpy`
3. 修改 `device_client.py` 中的服务器地址
4. 运行检测程序：
   - 人员安全检测：`python zone_detection.py`
   - 产品检测：`python product_detection.py`

### 产品检测说明
产品检测功能用于识别传送带上物品的颜色和形状：
- **产品A**: 蓝色 + 方形
- **产品B**: 青色 + 圆形

操作方式：
- 按 `c` 键手动捕获检测
- 按 `r` 键重置计数
- 按 `q` 键退出程序

## 自动调度功能

系统支持以下自动调度规则：

1. **高温自动暂停**: 当温度超过95°C时，自动暂停生产线
2. **温度恢复自动启动**: 当温度恢复到80°C以下时，自动恢复生产
3. **产量达标自动停止**: 当产量达到设定目标时，自动停止生产线

可在前端界面的"自动调度"面板中启用/禁用这些规则。

## 生产计划功能

在前端界面的"生产计划"面板中：
1. 设置目标产量
2. 点击"设置"按钮启动计划
3. 实时查看进度和预计完成时间
4. 达到目标后自动停止（如果启用了相应规则）

## 提交内容

1. ✅ 完整的代码
2. ✅ 系统架构和接口设计文档
3. ⏳ 运行演示视频（待录制）
