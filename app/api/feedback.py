"""
Beta uygulamasindaki 'uygulama ici geri bildirim ve hata raporlama formu'
(Bolum 3.1). Gonderilen icerik dogrudan SystemLog'a yazilir, boylece
yonetici Sistem Gunlugu ekranindan gorur (Bolum 3.2 kabul kriteri).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, SystemLog
from app.schemas import FeedbackSubmit
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("")
def submit_feedback(body: FeedbackSubmit, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    level = "WARNING" if body.category == "bug" else "INFO"
    entry = SystemLog(
        level=level,
        source="beta_feedback",
        message=f"[{body.category}] (kullanici: {user.username}) {body.message}",
        user_id=user.id,
    )
    db.add(entry)
    db.commit()
    return {"received": True}
