"""
PII Filtresi (Bolum 0.5).

MVP: kural tabanli (regex) filtre. Dokuman acikca belirtiyor: "yalnizca
regex yetersiz kalir" -> production'da buna ek olarak model destekli bir
siniflandirici (ör. kucuk bir NER/PII modeli) eklenmeli. Bu dosyadaki
`contains_pii` fonksiyonunun imzasi bunu degistirmeden genisletilebilir
sekilde tasarlandi (bkz. asagidaki TODO).
"""
import re
from typing import List, Tuple

PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone_tr": re.compile(r"(?:\+90|0)?\s?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}"),
    "tc_kimlik": re.compile(r"\b[1-9]\d{10}\b"),
    "iban": re.compile(r"\bTR\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}


def contains_pii(text: str) -> Tuple[bool, List[str]]:
    matches = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
    # TODO (production): burada model destekli bir siniflandirici cagrilip
    # matches listesine eklenmeli (ör. isim/adres gibi regex'le yakalanamayan
    # PII turleri icin).
    return (len(matches) > 0, matches)


def redact(text: str) -> str:
    redacted = text
    for name, pattern in PATTERNS.items():
        redacted = pattern.sub(f"[{name.upper()}_REDACTED]", redacted)
    return redacted


INJECTION_PATTERNS = [
    re.compile(r"gelecekte\s+.*\s+yap", re.IGNORECASE),
    re.compile(r"bundan\s+sonra\s+her\s+zaman", re.IGNORECASE),
    re.compile(r"artik\s+sistem\s+talimat", re.IGNORECASE),
    re.compile(r"ignore\s+(previous|all)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer|admin|unrestricted)\s+mode", re.IGNORECASE),
]


def looks_like_injection(text: str) -> bool:
    """Bolum 0.5: 'gelecekte sunu yap' turunden gomulu talimat kaliplari."""
    return any(p.search(text) for p in INJECTION_PATTERNS)
