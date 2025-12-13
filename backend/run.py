"""
启动后端服务
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("="*60)
    print("🚀 启动智能生产线监控系统后端服务")
    print(f"📡 API地址: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📚 API文档: http://localhost:{settings.API_PORT}/docs")
    print(f"🔌 WebSocket: ws://localhost:{settings.API_PORT}/ws/dashboard")
    print("="*60)
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
