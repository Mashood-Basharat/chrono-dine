import io
import csv
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Visit, Snapshot, TableZone

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    """Summary overview of restaurant dining performance."""
    total_visits = db.query(func.count(Visit.id)).scalar() or 0
    avg_duration = db.query(func.avg(Visit.duration_seconds)).scalar() or 0
    avg_guests = db.query(func.avg(Visit.guest_count)).scalar() or 0
    max_duration = db.query(func.max(Visit.duration_seconds)).scalar() or 0

    return {
        "total_visits": total_visits,
        "avg_duration_seconds": int(avg_duration),
        "avg_duration_formatted": f"{int(avg_duration) // 60}m {int(avg_duration) % 60}s",
        "avg_guests_per_table": round(float(avg_guests), 1),
        "longest_visit_formatted": f"{int(max_duration) // 60}m {int(max_duration) % 60}s",
    }


@router.get("/history")
def get_occupancy_history(minutes: int = Query(default=60, ge=5, le=1440), db: Session = Depends(get_db)):
    """Time-series snapshots of occupancy and guest counts for charts."""
    since = datetime.utcnow() - timedelta(minutes=minutes)
    snapshots = db.query(Snapshot).filter(Snapshot.recorded_at >= since).order_by(Snapshot.id.asc()).all()

    # Downsample if too many points for smooth canvas charts
    MAX_POINTS = 300
    if len(snapshots) > MAX_POINTS:
        step = len(snapshots) // MAX_POINTS + 1
        snapshots = snapshots[::step]

    return [s.to_dict() for s in snapshots]


@router.get("/visits")
def get_visits(limit: int = 50, table_name: Optional[str] = None, db: Session = Depends(get_db)):
    """Recent completed dining visits."""
    query = db.query(Visit).order_by(Visit.id.desc())
    if table_name:
        query = query.filter(Visit.table_name == table_name)
    rows = query.limit(limit).all()
    return [r.to_dict() for r in rows]


@router.get("/tables")
def get_table_performance(db: Session = Depends(get_db)):
    """Per-table turnover statistics and averages."""
    results = db.query(
        Visit.table_name,
        func.count(Visit.id).label("visits"),
        func.avg(Visit.duration_seconds).label("avg_seconds"),
        func.avg(Visit.guest_count).label("avg_guests"),
        func.max(Visit.duration_seconds).label("max_seconds")
    ).group_by(Visit.table_name).order_by(Visit.table_name).all()

    stats = []
    for r in results:
        avg_s = int(r.avg_seconds or 0)
        stats.append({
            "table_name": r.table_name,
            "total_visits": r.visits,
            "avg_duration_seconds": avg_s,
            "avg_duration_formatted": f"{avg_s // 60}m {avg_s % 60}s",
            "avg_guests": round(float(r.avg_guests or 0), 1),
            "max_duration_formatted": f"{int(r.max_seconds or 0) // 60}m",
        })
    return stats


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    """Export complete visit activity log as CSV spreadsheet."""
    visits = db.query(Visit).order_by(Visit.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Visit ID", "Table Name", "Seated Time", "Departure Time", "Duration (Seconds)", "Duration (Formatted)", "Guests"])

    for v in visits:
        writer.writerow([
            v.id,
            v.table_name,
            v.started_at.strftime("%Y-%m-%d %H:%M:%S") if v.started_at else "",
            v.ended_at.strftime("%Y-%m-%d %H:%M:%S") if v.ended_at else "",
            v.duration_seconds,
            f"{v.duration_seconds // 60}m {v.duration_seconds % 60}s",
            v.guest_count
        ])

    csv_data = output.getvalue()
    filename = f"restaurant-activity-{datetime.utcnow().strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
