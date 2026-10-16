from typing import List, Optional, Any
from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float
    y: float


class TableZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    polygon: List[List[float]] = Field(..., min_length=3)
    top: Optional[List[List[float]]] = None
    seats: int = Field(default=4, ge=1, le=20)


class TableZoneUpdate(BaseModel):
    name: Optional[str] = None
    polygon: Optional[List[List[float]]] = None
    top: Optional[List[List[float]]] = None
    seats: Optional[int] = Field(default=None, ge=1, le=20)
    is_active: Optional[bool] = None


class WaitlistCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100)
    party_size: int = Field(default=2, ge=1, le=30)
    phone: Optional[str] = None
    quoted_minutes: int = Field(default=15, ge=1, le=180)
    notes: Optional[str] = None


class WaitlistStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(WAITING|SEATED|CANCELLED|NO_SHOW)$")
    assigned_table: Optional[str] = None


class SettingsUpdate(BaseModel):
    stream_source: Optional[str] = None
    confidence_threshold: Optional[float] = Field(None, ge=0.05, le=0.95)
    pose_confidence_threshold: Optional[float] = Field(None, ge=0.05, le=0.95)
    occupy_hysteresis_seconds: Optional[float] = Field(None, ge=0.1, le=30.0)
    free_hysteresis_seconds: Optional[float] = Field(None, ge=0.1, le=30.0)
    default_seats_per_table: Optional[int] = Field(None, ge=1, le=20)
    alert_idle_table_minutes: Optional[int] = Field(None, ge=1, le=120)
    alert_capacity_percent: Optional[int] = Field(None, ge=50, le=100)


class AlertDismiss(BaseModel):
    dismissed: bool = True
