"""
Memory Engine (Bolum 0.3).

MVP notu: gercek bir vektor-index (pgvector/Qdrant/FAISS) yerine, embedding'ler
JSON float listesi olarak saklaniyor ve benzerlik Python'da cosine similarity
ile hesaplaniyor. Veri buyudukce bu fonksiyonlar (search_master_memory)
degistirilmeden, sadece ic implementasyonu pgvector sorgusuna cevrilerek
olceklenebilir.
"""
import math
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import UserMemory, MasterMemory, MemoryVersion


def fake_embed(text: str, dim: int = 32) -> List[float]:
    """
    Gercek bir embedding modeli baglanana kadar KULLANILACAK yer tutucu.
    Deterministiktir (ayni metin -> ayni vektor) ama anlamsal degildir.
    TODO: gercek bir embedding saglayicisi ile degistirin.
    """
    vec = [0.0] * dim
    for i, ch in enumerate(text.lower()):
        vec[i % dim] += ord(ch)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# ---- Kullanici Hafizasi ----

def write_user_memory(db: Session, user_id: int, key: str, value: str) -> UserMemory:
    existing = db.query(UserMemory).filter(
        UserMemory.user_id == user_id, UserMemory.key == key
    ).first()
    if existing:
        existing.value = value
        existing.embedding = fake_embed(value)
        existing.updated_at = datetime.utcnow()
    else:
        existing = UserMemory(user_id=user_id, key=key, value=value, embedding=fake_embed(value))
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def read_user_memory(db: Session, user_id: int) -> List[UserMemory]:
    return db.query(UserMemory).filter(UserMemory.user_id == user_id).all()


def delete_user_memory(db: Session, user_id: int, memory_id: int) -> bool:
    """'Bunu unut' komutu: kayit tamamen silinir, yumusatilmis/arsivlenmis
    hali tutulmaz."""
    item = db.query(UserMemory).filter(
        UserMemory.id == memory_id, UserMemory.user_id == user_id
    ).first()
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def export_user_memory(db: Session, user_id: int) -> List[dict]:
    items = read_user_memory(db, user_id)
    return [{"key": i.key, "value": i.value, "updated_at": i.updated_at.isoformat()} for i in items]


# ---- Master Memory ----

def promote_to_master_memory(
    db: Session, content: str, category: Optional[str], approved_by: int, note: Optional[str] = None
) -> MasterMemory:
    entry = MasterMemory(content=content, category=category, embedding=fake_embed(content),
                          version=1, approved_by=approved_by)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    db.add(MemoryVersion(
        master_memory_id=entry.id, content_snapshot=content, version=1,
        changed_by=approved_by, change_note=note or "ilk onay"
    ))
    db.commit()
    return entry


def rollback_master_memory(db: Session, master_memory_id: int) -> Optional[MasterMemory]:
    """Bir onceki versiyona geri doner (Bolum 0.3: 'geri alinabilir')."""
    entry = db.query(MasterMemory).filter(MasterMemory.id == master_memory_id).first()
    if not entry:
        return None
    versions = db.query(MemoryVersion).filter(
        MemoryVersion.master_memory_id == master_memory_id
    ).order_by(MemoryVersion.version.desc()).all()
    if len(versions) < 2:
        return entry  # geri donulecek onceki versiyon yok
    previous = versions[1]
    entry.content = previous.content_snapshot
    entry.version += 1
    db.commit()
    db.refresh(entry)
    return entry


def search_master_memory(db: Session, query_text: str, top_k: int = 5) -> List[MasterMemory]:
    query_vec = fake_embed(query_text)
    candidates = db.query(MasterMemory).filter(MasterMemory.is_active == True).all()  # noqa: E712
    scored = [(cosine_similarity(query_vec, c.embedding or []), c) for c in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def find_conflicting_entry(db: Session, text: str, threshold: float = 0.92) -> Optional[MasterMemory]:
    """Bolum 0.4: celisen bilgiler otomatik secilmez, oncelikle yonetici gorur.
    MVP: yuksek embedding benzerligi ama farkli metin -> potansiyel celiski."""
    query_vec = fake_embed(text)
    for entry in db.query(MasterMemory).filter(MasterMemory.is_active == True).all():  # noqa: E712
        sim = cosine_similarity(query_vec, entry.embedding or [])
        if sim > threshold and entry.content.strip().lower() != text.strip().lower():
            return entry
    return None
