"""
TURKUAZ CORE - Ayarlar
Bolum 0.2 / 0.3: yetki ve hafiza mimarisi sunucu tarafinda; tum gizli
degerler burada merkezilestirilir, istemci koduna hicbir sekilde gomulmez.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -- Genel --
    app_name: str = "TURKUAZ CORE"
    environment: str = "development"  # development | staging | production

    # -- Veritabani --
    # MVP: SQLite (kolay yerel calistirma). Production: PostgreSQL + pgvector.
    database_url: str = "sqlite:///./turkuaz.db"

    # -- Auth / JWT --
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION_ENV"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # -- Cihaz dogrulama (Bolum 0.2) --
    max_devices_per_user: int = 5

    # -- Auto-onay esigi (Bolum 0.4) --
    auto_approve_confidence_threshold: float = 0.90

    # -- AI Engine: Gemini saglayicisi (opsiyonel) --
    # Bos birakilirsa MockProvider kullanilmaya devam eder. Doldurulunca
    # main.py'de get_active_provider("gemini") secilerek etkinlestirilir.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    # -- AI Engine: Ollama saglayicisi (opsiyonel, yerel model, fallback) --
    # Bos birakilirsa Ollama hic denenmez. Gemini kota/rate-limit hatasi
    # verdiginde otomatik olarak buna dusulur (bkz. ai_engine.generate_reply).
    ollama_base_url: str = ""
    ollama_model: str = "llama3.1:8b"

    class Config:
        env_file = ".env"


settings = Settings()
