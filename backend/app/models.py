from datetime import datetime
import json
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from .database import Base


class TableZone(Base):
    __tablename__ = "table_zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    # Stored as JSON strings of [[x1, y1], [x2, y2], ...] normalized or absolute pixel coordinates
    polygon_coords = Column(Text, nullable=False)  # Area bounding box / polygon
    top_coords = Column(Text, nullable=True)      # Table surface polygon
    seats = Column(Integer, default=4)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "polygon": json.loads(self.polygon_coords) if self.polygon_coords else [],
            "top": json.loads(self.top_coords) if self.top_coords else [],
            "seats": self.seats,
            "is_active": self.is_active,
        }


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(50), index=True, nullable=False)
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False)
    guest_count = Column(Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "table_name": self.table_name,
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S") if self.started_at else None,
            "ended_at": self.ended_at.strftime("%Y-%m-%d %H:%M:%S") if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "duration_formatted": f"{self.duration_seconds // 60}m {self.duration_seconds % 60}s",
            "guest_count": self.guest_count,
        }


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    occupied_tables = Column(Integer, nullable=False)
    total_guests = Column(Integer, nullable=False)
    utilization_pct = Column(Float, default=0.0)

    def to_dict(self):
        return {
            "id": self.id,
            "time": self.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if self.recorded_at else None,
            "occupied_tables": self.occupied_tables,
            "total_guests": self.total_guests,
            "utilization_pct": round(self.utilization_pct, 1),
        }


class WaitlistParty(Base):
    __tablename__ = "waitlist_parties"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    party_size = Column(Integer, default=2)
    phone = Column(String(30), nullable=True)
    status = Column(String(20), default="WAITING", index=True)  # WAITING, SEATED, CANCELLED, NO_SHOW
    quoted_minutes = Column(Integer, default=15)
    notes = Column(String(255), nullable=True)
    assigned_table = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    seated_at = Column(DateTime, nullable=True)

    def to_dict(self):
        elapsed_mins = int((datetime.utcnow() - self.created_at).total_seconds() / 60) if self.created_at else 0
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "party_size": self.party_size,
            "phone": self.phone or "",
            "status": self.status,
            "quoted_minutes": self.quoted_minutes,
            "notes": self.notes or "",
            "assigned_table": self.assigned_table or "",
            "wait_minutes": elapsed_mins,
            "is_overdue": elapsed_mins > self.quoted_minutes if self.status == "WAITING" else False,
            "created_at": self.created_at.strftime("%H:%M:%S") if self.created_at else None,
            "seated_at": self.seated_at.strftime("%H:%M:%S") if self.seated_at else None,
        }


class SystemAlert(Base):
    __tablename__ = "system_alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False)  # HIGH_OCCUPANCY, LONG_DWELL, WAITLIST_OVERDUE, DISCONNECTION
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="INFO")  # INFO, WARNING, CRITICAL
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.alert_type,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "is_dismissed": self.is_dismissed,
            "time": self.created_at.strftime("%H:%M:%S") if self.created_at else None,
        }


class CameraConfig(Base):
    __tablename__ = "camera_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="Primary Dining Floor")
    source_type = Column(String(20), default="FILE")  # RTSP, FILE, WEBCAM
    source_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "is_active": self.is_active,
        }
