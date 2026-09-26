"""Sohbet endpoint'i: AI Engine + Memory Engine + Tool Engine'i bir araya getirir."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, SystemLog
from app.schemas import ChatRequest, ChatResponse
from app.security import get_current_user
from app.engines import memory_engine, ai_engine

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        relevant = memory_engine.search_master_memory(db, body.message, top_k=3)
        context = [r.content for r in relevant]
        # Bolum: cok saglayicili fallback (Gemini -> Ollama -> Mock).
        # Hicbir saglayici basarisiz olsa bile /chat 500 dondurmez.
        reply, provider_used = ai_engine.generate_reply(body.message, context)
        return ChatResponse(reply=reply, used_master_memory_ids=[r.id for r in relevant], provider=provider_used)
    except Exception as e:
        db.add(SystemLog(level="ERROR", source="chat", message=str(e), user_id=user.id))
        db.commit()
        raise
