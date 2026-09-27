"""
Yonetici (Windows Admin uygulamasinin tukettigi) API'lar.

Onemli: is mantiginin TAMAMI burada; Windows Yonetici uygulamasi (.NET) bu
API'lari cagiran bir ARAYUZDEN ibaret olmali, karar mantigini kendi
kodunda tutmamali (Bolum 0.1 - Admin Engine notu).
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, LearningCandidate, CandidateStatus, MasterMemory, SystemLog, FeatureFlag
from app.schemas import (
    LearningCandidateOut, CandidateReviewDecision, MasterMemoryOut, SystemLogOut,
    FeatureFlagOut, FeatureFlagUpdate,
)
from app.security import require_admin
from app.engines import memory_engine

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/learning-candidates", response_model=list[LearningCandidateOut])
def list_candidates(
    status_filter: CandidateStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    q = db.query(LearningCandidate)
    if status_filter:
        q = q.filter(LearningCandidate.status == status_filter)
    # Dusuk guven / celiski / injection bayrakli olanlar once gelsin (Bolum 0.4).
    return q.order_by(
        LearningCandidate.conflict_flag.desc(),
        LearningCandidate.injection_flag.desc(),
        LearningCandidate.confidence_score.asc(),
    ).all()


@router.post("/learning-candidates/{candidate_id}/review", response_model=LearningCandidateOut)
def review_candidate(
    candidate_id: int,
    body: CandidateReviewDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    candidate = db.query(LearningCandidate).filter(LearningCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Aday bulunamadi")
    if candidate.status != CandidateStatus.pending:
        raise HTTPException(status_code=400, detail="Bu aday zaten incelenmis")

    if body.decision == "approve":
        entry = memory_engine.promote_to_master_memory(
            db, content=candidate.raw_text, category=candidate.category,
            approved_by=admin.id, note=body.note,
        )
        candidate.status = CandidateStatus.approved
        candidate.conflict_with_id = candidate.conflict_with_id or None
        candidate.reviewer_note = f"master_memory_id={entry.id}"
    elif body.decision == "edit":
        if not body.edited_text:
            raise HTTPException(status_code=400, detail="edited_text zorunlu")
        memory_engine.promote_to_master_memory(
            db, content=body.edited_text, category=candidate.category,
            approved_by=admin.id, note=body.note or "yonetici tarafindan duzenlendi",
        )
        candidate.status = CandidateStatus.edited
    elif body.decision == "reject":
        candidate.status = CandidateStatus.rejected
    elif body.decision == "hold":
        candidate.status = CandidateStatus.held
    else:
        raise HTTPException(status_code=400, detail="Gecersiz karar")

    candidate.reviewer_id = admin.id
    candidate.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/master-memory", response_model=list[MasterMemoryOut])
def search_master_memory(q: str = "", db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if not q:
        return db.query(MasterMemory).order_by(MasterMemory.created_at.desc()).limit(50).all()
    return memory_engine.search_master_memory(db, q)


@router.post("/master-memory/{entry_id}/rollback", response_model=MasterMemoryOut)
def rollback(entry_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    entry = memory_engine.rollback_master_memory(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Kayit bulunamadi")
    return entry


@router.get("/system-log", response_model=list[SystemLogOut])
def system_log(limit: int = 100, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(limit).all()


@router.get("/feature-flags", response_model=list[FeatureFlagOut])
def list_all_flags(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.query(FeatureFlag).all()


@router.put("/feature-flags/{key}", response_model=FeatureFlagOut)
def upsert_flag(
    key: str, body: FeatureFlagUpdate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    """Bolum 3.1: bayragi uzaktan ac/kapat. Yoksa olusturur."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if not flag:
        flag = FeatureFlag(key=key, enabled=body.enabled, description=body.description)
        db.add(flag)
    else:
        flag.enabled = body.enabled
        if body.description is not None:
            flag.description = body.description
    db.commit()
    db.refresh(flag)
    return flag


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """Bolum 1.1 Dashboard icin ozet sayilar."""
    return {
        "active_users": db.query(User).filter(User.is_active == True).count(),  # noqa: E712
        "pending_candidates": db.query(LearningCandidate).filter(
            LearningCandidate.status == CandidateStatus.pending
        ).count(),
        "recent_errors": db.query(SystemLog).filter(SystemLog.level == "ERROR").count(),
    }

import os
from pydantic import BaseModel

class BootstrapRequest(BaseModel):
    username: str
    setup_key: str

@router.post("/bootstrap")
def make_user_admin(data: BootstrapRequest, db = Depends(get_db)):
    expected_key = os.getenv("ADMIN_BOOTSTRAP_KEY")
    if not expected_key or data.setup_key != expected_key:
        raise HTTPException(status_code=403, detail="Gecersiz setup key.")
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi.")
    user.role = "admin"
    db.commit()
    return {"message": f"{data.username} artik admin."}
