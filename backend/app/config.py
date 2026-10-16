import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Database: Supports PostgreSQL (e.g. postgresql://user:pass@localhost:5432/resturant_db)
    # Automatically falls back to high-concurrency SQLite if PostgreSQL is not specified
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./restaurant_app.db")
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Camera / Stream Source: Can be RTSP URL, local video file, or webcam device integer
    STREAM_SOURCE: str = os.getenv("STREAM_SOURCE", "videos/Cctv Resturant.mp4")
    STREAM_FPS_TARGET: int = 25
    JPEG_QUALITY: int = 80

    # AI Detection & Calibration defaults
    YOLO_MODEL_PATH: str = "models/yolo11s.pt"
    YOLO_POSE_MODEL_PATH: str = "models/yolo11s-pose.pt"
    CONFIDENCE_THRESHOLD: float = 0.25
    POSE_CONFIDENCE_THRESHOLD: float = 0.30
    OCCUPY_HYSTERESIS_SECONDS: float = 1.0
    FREE_HYSTERESIS_SECONDS: float = 1.5
    DEFAULT_SEATS_PER_TABLE: int = 4

    # Operational Alerts
    ALERT_IDLE_TABLE_MINUTES: int = 15
    ALERT_CAPACITY_PERCENT: int = 85

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
