"""
Auth / JWT / cihaz dogrulama.

Bolum 0.2: yetki karari HER ISTEKTE sunucuda dogrulanir; istemciler
sadece kisa omurlu access token + yenilenebilir refresh token tasir.
"""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, Device, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    """
    passlib yerine dogrudan bcrypt kutuphanesi kullaniliyor - passlib'in
    bcrypt 4.1+ ile "password cannot be longer than 72 bytes" hatasi veren
    bilinen bir uyumsuzlugu var (kisa sifrelerde bile tetiklenebiliyor).
    bcrypt'in kendisi zaten 72 byte sinirini biliyor; biz de girdi olarak
    ne verilirse verilsin once UTF-8'e cevirip 72 byte'a kirpiyoruz ki
    ne passlib'in sardigi hata ne de bcrypt'in kendi ValueError'u cikmasin.
    """
    pw_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except ValueError:
        # Hash bozuk/taninmayan bir formatta ise (ör. eski passlib hash'i
        # farkli bir seyle karisti) dogrulamayi basarisiz say, patlama.
        return False


def create_token(user: User, device_fingerprint: str, expires_delta: timedelta, token_type: str) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        # cihaz parmak izi token'a gomulur: cikan token baska bir cihazdan
        # tekrar kullanilamaz (bkz. verify_device_matches_token).
        "dfp": device_fingerprint,
        "type": token_type,
        "exp": datetime.utcnow() + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User, device_fingerprint: str) -> str:
    return create_token(
        user, device_fingerprint,
        timedelta(minutes=settings.access_token_expire_minutes), "access"
    )


def create_refresh_token(user: User, device_fingerprint: str) -> str:
    return create_token(
        user, device_fingerprint,
        timedelta(days=settings.refresh_token_expire_days), "refresh"
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Gecersiz veya suresi dolmus token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    x_device_fingerprint: Optional[str] = Header(default=None, alias="X-Device-Fingerprint"),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token bekleniyordu")

    # Cihaz dogrulama (Bolum 0.2): token'daki parmak izi, istekteki basligindakiyle
    # ve kayitli cihazla eslesmiyorsa reddet.
    token_dfp = payload.get("dfp")
    if not x_device_fingerprint or x_device_fingerprint != token_dfp:
        raise HTTPException(status_code=403, detail="Supheli cihaz: parmak izi eslesmiyor")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Kullanici bulunamadi veya pasif")

    registered = db.query(Device).filter(
        Device.user_id == user.id, Device.fingerprint == token_dfp
    ).first()
    if not registered:
        raise HTTPException(status_code=403, detail="Kayitli olmayan cihaz")
    registered.last_seen_at = datetime.utcnow()
    db.commit()

    return user


def require_role(*allowed_roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Bu islem icin yetkiniz yok")
        return user
    return dependency


require_admin = require_role(UserRole.admin)
