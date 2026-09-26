"""Pydantic sema (request/response) taniml ari."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

from app.models import UserRole, CandidateStatus


# ---- Auth ----
class RegisterRequest(BaseModel):
    username: str
    password: str
    device_fingerprint: str
    device_label: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str
    device_fingerprint: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: UserRole


class RegisterDeviceRequest(BaseModel):
    """Yeni bir cihazdan ilk girisin sifre ile dogrulanip cihazin kaydedilmesi."""
    device_fingerprint: str
    device_label: Optional[str] = None


# ---- User Memory ----
class UserMemoryCreate(BaseModel):
    key: str
    value: str


class UserMemoryOut(BaseModel):
    id: int
    key: str
    value: str
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- Learning Candidate ----
class LearningCandidateSubmit(BaseModel):
    text: str
    source: str = "chat"


class LearningCandidateOut(BaseModel):
    id: int
    raw_text: str
    category: Optional[str]
    confidence_score: float
    conflict_flag: bool
    injection_flag: bool
    status: CandidateStatus
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateReviewDecision(BaseModel):
    decision: str  # "approve" | "reject" | "edit" | "hold"
    edited_text: Optional[str] = None
    note: Optional[str] = None


# ---- Master Memory ----
class MasterMemoryOut(BaseModel):
    id: int
    content: str
    category: Optional[str]
    version: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Chat ----
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    used_master_memory_ids: List[int] = []
    provider: str  # "gemini" | "ollama" | "mock" - seffaflik icin hangi saglayici cevap verdi


# ---- System Log ----
class SystemLogOut(BaseModel):
    id: int
    level: str
    source: Optional[str]
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Feature Flags (Bolum 3.1: Android Beta) ----
class FeatureFlagOut(BaseModel):
    key: str
    enabled: bool
    description: Optional[str]

    class Config:
        from_attributes = True


class FeatureFlagUpdate(BaseModel):
    enabled: bool
    description: Optional[str] = None


# ---- Feedback (Bolum 3.1/3.2: Beta geri bildirim formu) ----
class FeedbackSubmit(BaseModel):
    message: str
    category: str = "feedback"  # "feedback" | "bug"
