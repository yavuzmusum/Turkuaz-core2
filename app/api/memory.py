"""
Kullanici hafizasi endpointleri + ortak ogrenme adayi gonderimi.

Bolum 3.1 (Android Beta): kullanici 'sunu ogren' dedi mi bilgi DOGRUDAN
Master Memory'ye degil, ogrenme adayi kuyruguna gider -> /learn-candidate.
Kisisel bilgi ise /me endpoint'i ile doogrudan Kullanici Hafizasi'na yazilir.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserMemoryCreate, UserMemoryOut, LearningCandidateSubmit, LearningCandidateOut
from app.security import get_current_user
from app.engines import memory_engine, learning_engine

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("/me", response_model=list[UserMemoryOut])
def list_my_memory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return memory_engine.read_user_memory(db, user.id)


@router.post("/me", response_model=UserMemoryOut)
def write_my_memory(body: UserMemoryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return memory_engine.write_user_memory(db, user.id, body.key, body.value)


@router.delete("/me/{memory_id}")
def forget_my_memory(memory_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """'Bunu unut' komutu."""
    ok = memory_engine.delete_user_memory(db, user.id, memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Kayit bulunamadi")
    return {"deleted": True}


@router.get("/me/export")
def export_my_memory(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return memory_engine.export_user_memory(db, user.id)


@router.post("/learn-candidate", response_model=LearningCandidateOut)
def submit_learning_candidate(
    body: LearningCandidateSubmit, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return learning_engine.submit_candidate(db, body.text, body.source, submitted_by=user.id)
