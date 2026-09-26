"""
Feature flag okuma ucu — her turden istemci (once Android Beta) kendi
bayrak durumunu buradan cekiyor. Yazma/degistirme sadece admin.py
uzerinden, yonetici yetkisiyle yapilir (Bolum 3.1: 'yonetici tarafindan
uzaktan acilip kapatilabilir').
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, FeatureFlag
from app.schemas import FeatureFlagOut
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/feature-flags", tags=["feature-flags"])


@router.get("", response_model=list[FeatureFlagOut])
def list_flags(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(FeatureFlag).all()
