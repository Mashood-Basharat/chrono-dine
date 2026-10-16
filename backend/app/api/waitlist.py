from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import WaitlistParty, TableZone
from ..schemas import WaitlistCreate, WaitlistStatusUpdate

router = APIRouter(prefix="/api/waitlist", tags=["Waitlist"])


@router.get("")
def get_waitlist(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Fetch waitlist queue with wait time calculations."""
    query = db.query(WaitlistParty)
    if status:
        query = query.filter(WaitlistParty.status == status)
    else:
        # Default: show active waiting parties first, then recently seated
        query = query.filter(WaitlistParty.status.in_(["WAITING", "SEATED"])).order_by(
            WaitlistParty.status.desc(),
            WaitlistParty.created_at.asc()
        )
    parties = query.limit(100).all()
    return [p.to_dict() for p in parties]


@router.post("")
def add_to_waitlist(payload: WaitlistCreate, db: Session = Depends(get_db)):
    """Add a new waiting customer party to the queue."""
    party = WaitlistParty(
        customer_name=payload.customer_name,
        party_size=payload.party_size,
        phone=payload.phone,
        quoted_minutes=payload.quoted_minutes,
        notes=payload.notes,
        status="WAITING",
        created_at=datetime.utcnow()
    )
    db.add(party)
    db.commit()
    db.refresh(party)
    return party.to_dict()


@router.put("/{party_id}/seat")
def seat_party(party_id: int, table_name: str, db: Session = Depends(get_db)):
    """Assign party to a table and update their status to SEATED."""
    party = db.query(WaitlistParty).filter(WaitlistParty.id == party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Waitlist party not found")

    party.status = "SEATED"
    party.assigned_table = table_name
    party.seated_at = datetime.utcnow()
    db.commit()
    db.refresh(party)
    return party.to_dict()


@router.put("/{party_id}/status")
def update_party_status(party_id: int, payload: WaitlistStatusUpdate, db: Session = Depends(get_db)):
    """Update party status (WAITING, SEATED, CANCELLED, NO_SHOW)."""
    party = db.query(WaitlistParty).filter(WaitlistParty.id == party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Waitlist party not found")

    party.status = payload.status
    if payload.assigned_table:
        party.assigned_table = payload.assigned_table
    if payload.status == "SEATED" and not party.seated_at:
        party.seated_at = datetime.utcnow()

    db.commit()
    db.refresh(party)
    return party.to_dict()


@router.delete("/{party_id}")
def remove_party(party_id: int, db: Session = Depends(get_db)):
    """Remove a party from the waitlist."""
    party = db.query(WaitlistParty).filter(WaitlistParty.id == party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Waitlist party not found")

    db.delete(party)
    db.commit()
    return {"success": True, "deleted_id": party_id}
