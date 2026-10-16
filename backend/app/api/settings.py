import os
from fastapi import APIRouter
from ..config import settings
from ..schemas import SettingsUpdate
from ..services.stream_manager import stream_manager
from ..services.ai_worker import ai_worker

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
def get_settings():
    """Retrieve current operational configuration."""
    # List available local video recordings if any
    available_videos = []
    if os.path.exists("videos"):
        available_videos = [f for f in os.listdir("videos") if f.lower().endswith((".mp4", ".avi", ".mkv"))]

    return {
        "stream_source": stream_manager.source_url,
        "is_stream_connected": stream_manager.is_connected,
        "stream_resolution": f"{stream_manager.width}x{stream_manager.height}",
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
        "pose_confidence_threshold": settings.POSE_CONFIDENCE_THRESHOLD,
        "occupy_hysteresis_seconds": settings.OCCUPY_HYSTERESIS_SECONDS,
        "free_hysteresis_seconds": settings.FREE_HYSTERESIS_SECONDS,
        "default_seats_per_table": settings.DEFAULT_SEATS_PER_TABLE,
        "alert_idle_table_minutes": settings.ALERT_IDLE_TABLE_MINUTES,
        "alert_capacity_percent": settings.ALERT_CAPACITY_PERCENT,
        "database_type": "PostgreSQL" if settings.DATABASE_URL.startswith("postgresql") else "SQLite",
        "available_videos": available_videos,
    }


@router.post("")
def update_settings(payload: SettingsUpdate):
    """Update runtime configuration without restarting."""
    if payload.stream_source is not None and payload.stream_source != stream_manager.source_url:
        stream_manager.update_source(payload.stream_source)
        settings.STREAM_SOURCE = payload.stream_source

    if payload.confidence_threshold is not None:
        settings.CONFIDENCE_THRESHOLD = payload.confidence_threshold
    if payload.pose_confidence_threshold is not None:
        settings.POSE_CONFIDENCE_THRESHOLD = payload.pose_confidence_threshold
    if payload.occupy_hysteresis_seconds is not None:
        settings.OCCUPY_HYSTERESIS_SECONDS = payload.occupy_hysteresis_seconds
    if payload.free_hysteresis_seconds is not None:
        settings.FREE_HYSTERESIS_SECONDS = payload.free_hysteresis_seconds
    if payload.default_seats_per_table is not None:
        settings.DEFAULT_SEATS_PER_TABLE = payload.default_seats_per_table
    if payload.alert_idle_table_minutes is not None:
        settings.ALERT_IDLE_TABLE_MINUTES = payload.alert_idle_table_minutes
    if payload.alert_capacity_percent is not None:
        settings.ALERT_CAPACITY_PERCENT = payload.alert_capacity_percent

    return {"success": True, "settings": get_settings()}
