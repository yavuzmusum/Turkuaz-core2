"""
AI Engine: saglayicidan bagimsiz adapter mimarisi.

Yerel LLM, Gemini, ya da ileride TURKUAZ'in kendi modeli - hepsi ayni
ModelProvider arayuzunu implemente eder. Model Manager (Faz 1'de basit
tek-saglayicili surum) hangi provider'in aktif oldugunu belirler.
"""
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import List, Tuple

from app.config import settings


class ModelProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, context: List[str]) -> str:
        """context: chat/master-memory'den gelen ilgili metin parcalari."""
        raise NotImplementedError


class MockProvider(ModelProvider):
    """
    Gercek bir saglayici baglanana kadar gelistirmeyi/testleri surdurmeye
    yarayan yer tutucu. Gercek entegrasyon icin (ör. yerel LLM sunucusu ya da
    Gemini API) bu siniftan turetilen yeni bir Provider yazin ve
    get_active_provider() icinde secin.
    """
    name = "mock"

    def generate(self, prompt: str, context: List[str]) -> str:
        ctx_note = f" (baglam: {len(context)} parca)" if context else ""
        return f"[MOCK YANIT]{ctx_note} '{prompt[:80]}' icin henuz gercek bir model baglanmadi."


class GeminiProvider(ModelProvider):
    """
    Google Gemini API (generateContent, klasik/stateless uc) uzerinden
    gercek model cagrisi. Harici bir HTTP kutuphanesi (requests vb.)
    EKLENMEDI - stdlib'deki urllib.request kullanildi, boylece
    requirements.txt'e yeni bir bagimlilik girmedi.

    Kullanim: .env dosyasina GEMINI_API_KEY=... yazin, main.py'de
    get_active_provider("gemini") secin.

    NOT: Bu kod bu sandbox'ta (internet kapali) gercekten test edilemedi -
    Google'in guncel REST sozlesmesine (v1beta, POST .../{model}:generateContent
    ?key=...) gore yazildi. Ilk gercek cagriyi siz yapacaksiniz; bir hata
    alirsaniz yanit govdesini paylasin, birlikte duzeltelim.
    """
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY bos - .env dosyasina eklemeden bu provider kullanilamaz")
        self.api_key = api_key
        self.model = model
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def generate(self, prompt: str, context: List[str]) -> str:
        # Master Memory'den gelen ilgili parcalari basit bir sistem talimati
        # gibi prompt'un basina ekliyoruz.
        full_prompt = prompt
        if context:
            joined = "\n".join(f"- {c}" for c in context)
            full_prompt = f"Ilgili bilgi:\n{joined}\n\nKullanici mesaji: {prompt}"

        body = {
            "contents": [
                {"parts": [{"text": full_prompt}]}
            ]
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}?key={self.api_key}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Gemini API hatasi ({e.code}): {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Gemini API'ye ulasilamadi: {e.reason}") from e

        try:
            return parsed["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Gemini yaniti beklenmeyen formatta: {parsed}") from e


class OllamaProvider(ModelProvider):
    """
    Yerel bir Ollama sunucusuna (varsayilan: http://localhost:11434) REST
    istegi atar. GeminiProvider'daki gibi ekstra kutuphane yok - stdlib
    urllib.request kullanildi.

    Onerilen model: "llama3.1:8b" - cok dilli (Turkce dahil) performansi
    iyi ve orta seviye bir GPU/bilgisayarda calisabilir boyutta. Sabit
    kodlanmadi, config.py -> OLLAMA_MODEL ile degistirilebilir.

    NOT: Bu kod bu sandbox'ta calisan bir Ollama sunucusu OLMADIGI icin
    gercekten test edilemedi - Ollama'nin guncel /api/generate REST
    sozlesmesine (POST {base_url}/api/generate, govde {"model","prompt",
    "stream": false}, yanit govdesinde "response" alani) gore yazildi.
    Gercek testi siz yapacaksiniz: `ollama serve` + `ollama pull llama3.1:8b`
    calistirdiktan sonra deneyin; bir hata alirsaniz yanit govdesini
    paylasin, birlikte duzeltelim.
    """
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        if not base_url:
            raise ValueError("OLLAMA_BASE_URL bos - .env dosyasina eklemeden bu provider kullanilamaz")
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: str, context: List[str]) -> str:
        full_prompt = prompt
        if context:
            joined = "\n".join(f"- {c}" for c in context)
            full_prompt = f"Ilgili bilgi:\n{joined}\n\nKullanici mesaji: {prompt}"

        body = {"model": self.model, "prompt": full_prompt, "stream": False}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Ollama API hatasi ({e.code}): {error_body}") from e
        except urllib.error.URLError as e:
            # Sunucu calismiyorsa (ör. "Connection refused") buraya duser.
            raise RuntimeError(f"Ollama sunucusuna ulasilamadi ({self.base_url}): {e.reason}") from e

        try:
            return parsed["response"]
        except KeyError as e:
            raise RuntimeError(f"Ollama yaniti beklenmeyen formatta: {parsed}") from e


def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
    """Bolum: Gemini'den 429/kota hatasi mi geldi tespiti (kaba ama yeterli)."""
    msg = str(exc).lower()
    return any(marker in msg for marker in ("429", "quota", "rate limit", "resource_exhausted"))


def _build_providers() -> dict:
    providers: dict = {"mock": MockProvider()}
    if settings.gemini_api_key:
        providers["gemini"] = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    if settings.ollama_base_url:
        providers["ollama"] = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    return providers


_PROVIDERS = _build_providers()


def get_active_provider(name: str = "mock") -> ModelProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        if name in ("gemini", "ollama"):
            raise ValueError(f"{name} saglayicisi aktif degil - .env dosyasinda ilgili ayari yapin")
        raise ValueError(f"Bilinmeyen model saglayici: {name}")
    return provider


def generate_reply(prompt: str, context: List[str]) -> Tuple[str, str]:
    """
    Model Manager'in cok saglayicili fallback zinciri:
      1) Gemini varsa once o denenir.
      2) Gemini kota/rate-limit hatasi (ya da baska herhangi bir hata)
         verirse Ollama'ya dusulur - sistem sadece kota hatasinda degil,
         Gemini'yle ilgili HERHANGI bir sorunda (ag kopmasi, format hatasi
         vb.) da bir sonraki saglayiciya gecer; boylece "asla tamamen
         cokme" ilkesi (Bolum 0.1) daha saglam saglanir.
      3) Ollama da yoksa/basarisiz olursa Mock'a dusulur - boylece /chat
         hicbir zaman 500 donmez.
    Donus: (yanit_metni, kullanilan_saglayici_adi) - saglayici adi
    seffaflik icin ChatResponse.provider alanina yaziliyor.
    """
    if "gemini" in _PROVIDERS:
        try:
            return _PROVIDERS["gemini"].generate(prompt, context), "gemini"
        except Exception as gemini_error:
            # Kota/rate-limit oldugu ozel olarak isaretleniyor (spesifik
            # senaryo buydu) ama fallback her turlu hata icin calisiyor.
            _ = _is_quota_or_rate_limit_error(gemini_error)  # ileride loglama icin kullanilabilir

    if "ollama" in _PROVIDERS:
        try:
            return _PROVIDERS["ollama"].generate(prompt, context), "ollama"
        except Exception:
            pass

    return _PROVIDERS["mock"].generate(prompt, context), "mock"
