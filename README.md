# 智能生产线监控与调度系统

基于多源数据的智能生产线监控与调度系统，用于模拟小型生产线或设备集群的监控与调度。

## 系统架构

```
树莓派端 (摄像头检测/传感器)
        │
        │ HTTP/WebSocket
        ▼
后端服务 (FastAPI + MySQL)
        │
        │ WebSocket
        ▼
前端大屏 (Vue3 + ECharts)
```

## 功能模块

### 1. 生产线模块（树莓派端）
- ✅ 目标检测：YOLOv8检测人员进入危险区域
- ✅ 传感器数据采集：温度、压力、湿度
- ✅ 报警控制：LED灯、蜂鸣器

### 2. 中心控制与数据服务模块（后端）
- ✅ 数据聚合：接收并存储设备数据
- ✅ 控制指令：下发启动/停止/切换模式指令
- ✅ API服务：提供REST API和WebSocket

### 3. 可视化与管理界面（前端）
- ✅ 实时监控大屏：温度曲线、生产状态
- ✅ 报警管理：报警列表、处理报警
- ✅ 远程控制：启动/停止/切换模式

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

模拟器会自动上报传感器数据和检测结果，完全模拟树莓派行为。

## 项目结构

```
├── backend/                 # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── main.py         # FastAPI主应用（所有API接口）
│   │   ├── database.py     # 数据库模型定义
│   │   ├── schemas.py      # 请求/响应数据模型
│   │   ├── config.py       # 配置文件（数据库密码等）
│   │   └── websocket_manager.py  # WebSocket连接管理
│   ├── run.py              # 启动脚本
│   ├── init_db.sql         # 数据库初始化SQL
│   └── requirements.txt
│
├── frontend/               # 前端应用 (Vue3)
│   ├── src/
│   │   ├── App.vue        # 监控大屏主界面
│   │   ├── api/           # API接口封装
│   │   └── utils/         # WebSocket工具
│   ├── package.json
│   └── vite.config.js
│
├── simulator/              # 设备模拟器（独立服务）
│   ├── main.py            # 模拟器主程序
│   ├── sensor_simulator.py    # 传感器模拟
│   ├── detection_simulator.py # 检测模拟
│   ├── device_client.py   # 设备通信客户端
│   └── config.py          # 模拟器配置
│
├── project/                # 树莓派端代码
│   ├── zone_detection.py  # YOLOv8区域检测
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

1. 将 `project/zone_detection.py` 复制到树莓派
2. 安装依赖：`pip install ultralytics opencv-python requests`
3. 修改服务器地址后运行

## 提交内容

1. ✅ 完整的代码
2. ✅ 系统架构和接口设计文档
3. ⏳ 运行演示视频（待录制）
