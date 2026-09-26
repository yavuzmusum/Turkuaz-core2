"""
Veritabani modelleri.

Bolum 0.3 uyarinca hafiza turleri kesin ayrilir:
  - UserMemory    -> Kullanici Hafizasi (kisiye ozel, asla Master ile karismaz)
  - MasterMemory  -> ortak/paylasilan bilgi (sadece onayli adaylardan gelir)
  - LearningCandidate -> Ogrenme Adaylari (henuz onaylanmamis)
  - MemoryVersion -> Master Memory versiyon gecmisi (geri alinabilir)
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, Enum, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    beta = "beta"
    full = "full"


class CandidateStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"
    held = "held"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.full)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("UserMemory", back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    """Bolum 0.2: her cihaz kaydi token'a bagli parmak izi ile eslestirilir."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fingerprint = Column(String(255), nullable=False, index=True)
    label = Column(String(128), nullable=True)  # "Windows Yonetici - Ofis PC" gibi
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="devices")


class UserMemory(Base):
    """Kullaniciya ozel kalici hafiza. Kullanici goruntuleyebilir/silebilir/disa aktarabilir."""
    __tablename__ = "user_memories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # MVP: float listesi (bkz. memory_engine)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="memories")


class MasterMemory(Base):
    """Ortak/paylasilan hafiza. Sadece onaylanmis adaylardan yazilir (bkz. learning_engine)."""
    __tablename__ = "master_memories"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    category = Column(String(64), nullable=True)
    embedding = Column(JSON, nullable=True)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)  # geri alinan versiyonlar False olur
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MemoryVersion(Base):
    """Master Memory degisiklik gecmisi (Bolum 0.3: v1->v2->v3, geri alinabilir)."""
    __tablename__ = "memory_versions"

    id = Column(Integer, primary_key=True)
    master_memory_id = Column(Integer, ForeignKey("master_memories.id"), nullable=False)
    content_snapshot = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    change_note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LearningCandidate(Base):
    """Bolum 0.4 akisindaki 'Ogrenme Adayi'."""
    __tablename__ = "learning_candidates"

    id = Column(Integer, primary_key=True)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    source = Column(String(64), nullable=True)  # "beta_client", "chat", vb.
    raw_text = Column(Text, nullable=False)
    category = Column(String(64), nullable=True)
    confidence_score = Column(Float, default=0.0)
    conflict_flag = Column(Boolean, default=False)
    conflict_with_id = Column(Integer, ForeignKey("master_memories.id"), nullable=True)
    injection_flag = Column(Boolean, default=False)  # "gelecekte sunu yap" kalibi tespit edildi mi
    status = Column(Enum(CandidateStatus), default=CandidateStatus.pending)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True)
    level = Column(String(16), default="INFO")  # INFO | WARNING | ERROR
    source = Column(String(64), nullable=True)  # hangi engine/endpoint
    message = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FeatureFlag(Base):
    """Bolum 3.1: Beta'ya ozel, yoneticinin uzaktan actigi/kapattigi bayraklar."""
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, nullable=False)
    enabled = Column(Boolean, default=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
