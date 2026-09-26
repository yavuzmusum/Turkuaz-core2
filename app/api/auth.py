"""Auth endpointleri: kayit, giris, cihaz kaydi, token yenileme."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Device, UserRole
from app.schemas import RegisterRequest, LoginRequest, TokenResponse, RegisterDeviceRequest
from app.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, get_current_user,
)
from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Kullanici adi zaten alinmis")

    # Ilk kayit olan kullanici admin olmaz - roller Admin Engine/Admin Center
    # uzerinden ayrica atanir. MVP: varsayilan 'full', yukseltme ayri bir
    # yonetici islemi olmali (bkz. admin.py - TODO: rol degistirme endpoint'i).
    user = User(username=body.username, hashed_password=hash_password(body.password), role=UserRole.full)
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(Device(user_id=user.id, fingerprint=body.device_fingerprint, label=body.device_label))
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user, body.device_fingerprint),
        refresh_token=create_refresh_token(user, body.device_fingerprint),
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Kullanici adi veya sifre hatali")

    device = db.query(Device).filter(
        Device.user_id == user.id, Device.fingerprint == body.device_fingerprint
    ).first()
    if not device:
        existing_count = db.query(Device).filter(Device.user_id == user.id).count()
        if existing_count >= settings.max_devices_per_user:
            raise HTTPException(status_code=403, detail="Maksimum cihaz sayisina ulasildi")
        db.add(Device(user_id=user.id, fingerprint=body.device_fingerprint))
        db.commit()

    return TokenResponse(
        access_token=create_access_token(user, body.device_fingerprint),
        refresh_token=create_refresh_token(user, body.device_fingerprint),
        role=user.role,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token bekleniyordu")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Kullanici bulunamadi")
    dfp = payload["dfp"]
    return TokenResponse(
        access_token=create_access_token(user, dfp),
        refresh_token=create_refresh_token(user, dfp),
        role=user.role,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}
