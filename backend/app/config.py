"""
配置文件
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库配置
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "WZY216814wzy"
    DB_NAME: str = "production_monitor"
    
    # 数据库URL
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # 服务配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # 报警阈值
    TEMP_WARNING_THRESHOLD: float = 80.0  # 温度警告阈值
    TEMP_DANGER_THRESHOLD: float = 95.0   # 温度危险阈值
    
    class Config:
        env_file = ".env"


settings = Settings()
