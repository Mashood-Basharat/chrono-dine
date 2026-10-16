import json
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import TableZone
from ..schemas import TableZoneCreate, TableZoneUpdate
from ..services.ai_worker import ai_worker

router = APIRouter(prefix="/api/calibration", tags=["Calibration"])


@router.get("/zones")
def list_zones(db: Session = Depends(get_db)):
    """List all configured table zones for canvas rendering."""
    zones = db.query(TableZone).order_by(TableZone.id).all()
    return [z.to_dict() for z in zones]


@router.post("/zones")
def create_zone(payload: TableZoneCreate, db: Session = Depends(get_db)):
    """Create a new table zone drawn from the browser canvas."""
    existing = db.query(TableZone).filter(TableZone.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Table with name '{payload.name}' already exists.")

    zone = TableZone(
        name=payload.name,
        polygon_coords=json.dumps(payload.polygon),
        top_coords=json.dumps(payload.top) if payload.top else "[]",
        seats=payload.seats,
        is_active=True
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)

    # Immediately hot-reload AI worker zones
    ai_worker.reload_zones()

    return zone.to_dict()


@router.put("/zones/{zone_id}")
def update_zone(zone_id: int, payload: TableZoneUpdate, db: Session = Depends(get_db)):
    """Update table zone coordinates, seats, or name."""
    zone = db.query(TableZone).filter(TableZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Table zone not found")

    if payload.name is not None and payload.name != zone.name:
        existing = db.query(TableZone).filter(TableZone.name == payload.name, TableZone.id != zone_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Table '{payload.name}' already exists.")
        zone.name = payload.name

    if payload.polygon is not None:
        zone.polygon_coords = json.dumps(payload.polygon)
    if payload.top is not None:
        zone.top_coords = json.dumps(payload.top)
    if payload.seats is not None:
        zone.seats = payload.seats
    if payload.is_active is not None:
        zone.is_active = payload.is_active

    db.commit()
    db.refresh(zone)

    ai_worker.reload_zones()
    return zone.to_dict()


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """Remove a table zone from monitoring."""
    zone = db.query(TableZone).filter(TableZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Table zone not found")

    db.delete(zone)
    db.commit()

    ai_worker.reload_zones()
    return {"success": True, "deleted_id": zone_id}


@router.post("/import-seed")
def seed_from_files(db: Session = Depends(get_db)):
    """Seed zones from existing legacy tables.json and table_tops.json if database is empty."""
    count = db.query(TableZone).count()
    if count > 0:
        return {"message": "Database already contains table zones", "count": count}

    tables_path = "tables.json"
    tops_path = "table_tops.json"

    tables = {}
    tops = {}
    if os.path.exists(tables_path):
        with open(tables_path) as f:
            tables = json.load(f)
    if os.path.exists(tops_path):
        with open(tops_path) as f:
            tops = json.load(f)

    created = 0
    for name, poly in tables.items():
        top = tops.get(name, [])
        zone = TableZone(
            name=name,
            polygon_coords=json.dumps(poly),
            top_coords=json.dumps(top),
            seats=4,
            is_active=True
        )
        db.add(zone)
        created += 1

    db.commit()
    ai_worker.reload_zones()
    return {"message": f"Successfully imported {created} table zones", "count": created}
