from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SystemAlert

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("")
def get_alerts(unread_only: bool = False, db: Session = Depends(get_db)):
    """Fetch active system and floor alerts."""
    query = db.query(SystemAlert).order_by(SystemAlert.id.desc())
    if unread_only:
        query = query.filter(SystemAlert.is_dismissed == False)
    alerts = query.limit(50).all()
    return [a.to_dict() for a in alerts]


@router.put("/{alert_id}/dismiss")
def dismiss_alert(alert_id: int, db: Session = Depends(get_db)):
    """Dismiss an active alert."""
    alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_dismissed = True
    db.commit()
    return {"success": True, "alert_id": alert_id}


@router.post("/dismiss-all")
def dismiss_all_alerts(db: Session = Depends(get_db)):
    """Dismiss all active alerts."""
    db.query(SystemAlert).filter(SystemAlert.is_dismissed == False).update({"is_dismissed": True})
    db.commit()
    return {"success": True}
