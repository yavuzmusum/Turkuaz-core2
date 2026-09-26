# TURKUAZ CORE — Sunucu Çekirdeği (Faz 1 MVP)

TURKUAZ AI mimari dokümanının Bölüm 0 (Ortak Çekirdek) ve Bölüm 1.2
(Faz 1 MVP Kapsamı) karşılığı. Windows Yönetici (.NET) ve Android Beta
(Kotlin) istemcileri bu REST API'ye bağlanır — yetki ve hassas mantık
burada durur, istemciler sadece arayüzdür (Bölüm 0.1).

## Kurulum

```bash
cd turkuaz-core
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Varsayılan olarak SQLite (`turkuaz.db`) kullanır — sıfır kurulumla hemen
çalışır. `app/config.py` içindeki `database_url`'i PostgreSQL'e çevirerek
production'a taşıyabilirsiniz.

> **Not:** Bu dosyalar bu sohbetin sandbox ortamında (internet erişimi
> kapalı) yazıldı; sözdizimi (`py_compile`) doğrulandı ama bağımlılıklar
> kurulup gerçek bir sunucu olarak **çalıştırılamadı**. Kendi
> ortamınızda `pip install -r requirements.txt` sonrası çalıştırıp
> `/docs` üzerinden (FastAPI'nin otomatik Swagger arayüzü) test edin.

## Klasör yapısı

```
app/
  config.py          # Ayarlar (JWT secret, DB url, eşik değerler)
  database.py        # SQLAlchemy engine/session
  models.py          # User, Device, UserMemory, MasterMemory, MemoryVersion,
                      # LearningCandidate, SystemLog, FeatureFlag
  schemas.py          # Pydantic request/response şemaları
  security.py         # JWT + cihaz parmak izi doğrulama + rol bazlı yetki
  engines/
    pii_filter.py     # Regex tabanlı PII tespiti + prompt-injection kalıpları
    memory_engine.py  # Kullanıcı/Master hafıza CRUD + basit vektör arama
    ai_engine.py      # Sağlayıcıdan bağımsız adapter (şu an sadece Mock)
    tool_engine.py    # Whitelist'li araç çalıştırma (şu an: hesap makinesi)
    learning_engine.py# Sınıflandır → PII/injection filtrele → güven skoru
  api/
    auth.py           # /register /login /refresh /me
    memory.py         # /memory/me (CRUD+export), /memory/learn-candidate
    admin.py           # /admin/learning-candidates, /admin/master-memory, /admin/system-log, /admin/dashboard
    chat.py             # /chat
```

## Faz 1 kabul kriterleriyle eşleşme (Bölüm 1.3)

| Kriter | Karşılığı |
|---|---|
| Yönetici girişi + sunucu tarafı rol doğrulama | `security.py` (JWT + `require_admin`), `api/auth.py` |
| Uçtan uca öğrenme adayı akışı | `POST /memory/learn-candidate` → `GET/POST /admin/learning-candidates` |
| Çoklu oturumda tutarlı hafıza | `UserMemory` tablosu, cihaz başına değil kullanıcı başına saklanır |
| Sandbox'ta temel araç | `tool_engine.py` — `CalculatorTool` (ast tabanlı güvenli hesaplama) |

## Bilinçli olarak basitleştirilmiş / production öncesi sertleştirilmesi gerekenler

- **Vektör arama**: `memory_engine.fake_embed` deterministik ama anlamsal
  olmayan bir yer tutucu. Gerçek bir embedding sağlayıcısı + pgvector/Qdrant
  ile değiştirilmeli.
- **PII filtresi**: sadece regex. Doküman "yalnızca regex yetersiz kalır"
  diyor — model destekli bir katman eklenmeli.
- **Tool Engine**: gerçek işletim sistemi seviyesinde sandbox (ayrı
  process/container) yok, sadece whitelist + hata yakalama var.
- **AI Engine**: üç saglayicili fallback zinciri — **Gemini → Ollama →
  Mock**. `GEMINI_API_KEY` set edilirse önce Gemini denenir; Gemini hata
  verirse (kota/rate-limit dahil) otomatik olarak `OLLAMA_BASE_URL`'de
  tanımlı yerel Ollama sunucusuna düşülür (varsayılan model
  `llama3.1:8b`); o da yoksa/başarısızsa Mock'a düşülür — `/chat` hiçbir
  zaman 500 döndürmez. Hangi sağlayıcının cevap verdiği yanıtta
  `provider` alanında görünür. Kod `app/engines/ai_engine.py` ->
  `generate_reply()`'de. **Ollama tarafı bu sandbox'ta çalışan bir Ollama
  sunucusu olmadığı için test edilemedi** — Ollama'nın güncel
  `/api/generate` sözleşmesine göre yazıldı, ilk gerçek testi siz
  yapacaksınız (`ollama serve` + `ollama pull llama3.1:8b`).
- **Migration**: `Base.metadata.create_all` kullanılıyor; production için
  Alembic migration dosyaları yazılmalı (kütüphane requirements.txt'te
  hazır).
- **Rol atama**: `/register` herkesi `full` yapar; admin/beta rolüne
  yükseltme için ayrı bir endpoint (yalnızca mevcut adminlerin
  çağırabileceği) eklenmesi gerekiyor — Faz 1'de bilerek dışarıda
  bırakıldı, Admin Center ekranıyla birlikte eklenmeli.
- **Faz 1 dışında bırakılanlar** (dokümana göre bilerek yok): Learning Lab,
  otomatik Evaluation Engine, kendini geliştirme kuyruğunun tam
  otomasyonu, çok sağlayıcılı Model Manager.

## İstemcilerin bilmesi gerekenler (Windows .NET / Android Kotlin)

- Her istek `Authorization: Bearer <access_token>` **ve**
  `X-Device-Fingerprint: <fingerprint>` başlığı taşımalı — token'daki
  parmak izi ile eşleşmezse `403` döner (Bölüm 0.2).
- Access token kısa ömürlü (30 dk, `config.py`); süresi dolunca
  `/api/v1/auth/refresh` ile yenilenir.
- Android Beta, Faz 2 (Tam Sürüm) atlanarak başlatıldığı için bu
  API'deki temel sohbet + kişisel hafıza uçlarını (`/chat`,
  `/memory/me/*`) Beta istemcisinin kendisi implemente etmeli; sunucu
  tarafında Full/Beta ayrımı yapan bir kısıt yok (bilerek — ayrım
  istemci tarafında, feature flag'lerle yapılacak, Bölüm 3.1).

## Sırada ne var

1. Bu sunucuyu kendi ortamınızda çalıştırıp `/docs` üzerinden Faz 1
   kabul kriterlerini elle doğrulayın.
2. Windows Yönetici (.NET WPF/WinUI) istemcisi: Dashboard, Öğrenme
   İnceleme Ekranı, Master Memory Yöneticisi.
3. Android Beta (Kotlin) istemcisi: temel sohbet + kişisel hafıza +
   feature flag altyapısı + geri bildirim formu.
