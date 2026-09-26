"""
Learning Engine: Ogren -> Siniflandir -> Filtrele -> Dogrula -> Ogrenme Adayi
akisinin orkestrasyonu (Bolum 0.4).

Onemli: bu modul HICBIR ZAMAN dogrudan Master Memory'ye yazmaz. En yuksek
guven skorunda bile son yazma islemi admin.py'deki inceleme endpoint'i
uzerinden, bir yoneticinin (ya da acikca yetkilendirilmis otomasyon
kuralinin) onayiyla gerceklesir (Bolum 0.7 ile tutarli).
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LearningCandidate, CandidateStatus
from app.engines.pii_filter import contains_pii, looks_like_injection
from app.engines.memory_engine import find_conflicting_entry


SIMPLE_CATEGORY_KEYWORDS = {
    "kisisel": ["benim", "kedim", "ailem", "adresim", "dogum gunum"],
    "beceri": ["nasil yapilir", "adim adim", "komut", "arac"],
    "genel_bilgi": ["nedir", "tarihi", "tanimi"],
}


def classify(text: str) -> str:
    lowered = text.lower()
    for category, keywords in SIMPLE_CATEGORY_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            return category
    return "genel"


def compute_confidence(text: str, conflict: bool, injection: bool, pii_found: bool) -> float:
    """Basit sezgisel skor. TODO: gercek bir siniflandirici/skor modeliyle degistirin."""
    score = 0.75
    if len(text.strip()) < 5:
        score -= 0.3
    if conflict:
        score -= 0.4
    if injection:
        score -= 0.9
    if pii_found:
        score -= 1.0  # zaten ayri olarak reddedilecek, garanti altina al
    return max(0.0, min(1.0, score))


def submit_candidate(db: Session, text: str, source: str, submitted_by: Optional[int]) -> LearningCandidate:
    """
    Kullaniciya ozel bilgi ('kedimin adi Pamuk') bu fonksiyona HIC GELMEMELI -
    o dogrudan memory_engine.write_user_memory ile Kullanici Hafizasi'na yazilir.
    Bu fonksiyon yalnizca ORTAK ogrenme adaylari icindir (Bolum 0.4).
    """
    pii_found, pii_matches = contains_pii(text)
    injection = looks_like_injection(text)
    conflicting = find_conflicting_entry(db, text)

    confidence = compute_confidence(text, conflict=bool(conflicting), injection=injection, pii_found=pii_found)
    category = classify(text)

    candidate = LearningCandidate(
        submitted_by=submitted_by,
        source=source,
        raw_text=text,
        category=category,
        confidence_score=confidence,
        conflict_flag=bool(conflicting),
        conflict_with_id=conflicting.id if conflicting else None,
        injection_flag=injection,
        status=CandidateStatus.pending,
    )

    if pii_found:
        # PII iceren aday hicbir zaman Master Memory adayi olarak bile
        # tutulmaz; reddedilmis olarak kaydedilir (denetim izi icin), icerik
        # redakte edilerek saklanir.
        candidate.raw_text = f"[PII TESPIT EDILDI - ICERIK REDDEDILDI: {', '.join(pii_matches)}]"
        candidate.status = CandidateStatus.rejected

    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def is_high_priority_review(candidate: LearningCandidate) -> bool:
    """Bolum 0.4: dusuk guvenli / supheli / celiskili adaylar oncelikli olarak yoneticiye gider."""
    return (
        candidate.confidence_score < settings.auto_approve_confidence_threshold
        or candidate.conflict_flag
        or candidate.injection_flag
    )
