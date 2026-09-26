"""
TURKUAZ CORE - giris noktasi.
Calistirma: uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.database import Base, engine
from app.api import auth, admin, memory, chat, feature_flags, feedback

# MVP: create_all ile tablo olusturma. Production'da Alembic migration
# kullanin (requirements.txt'e eklendi, henuz migration dosyalari yazilmadi
# - TODO).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="TURKUAZ CORE", version="0.1.0-faz1")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(memory.router)
app.include_router(chat.router)
app.include_router(feature_flags.router)
app.include_router(feedback.router)


@app.get("/health")
def health():
    return {"status": "ok"}
