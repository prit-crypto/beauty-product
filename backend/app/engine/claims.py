"""Claims filter: every outgoing reply passes through here. Blocked claims are rewritten to safer wording."""
import json
import re
from functools import lru_cache

from app.config import DATA_DIR

CLAIM_QUESTION_EN = re.compile(
    r"\b(cure|cures|heal|guarantee|guaranteed|permanent|permanently|forever|100\s?%|stop (?:my |the )?hair ?(?:loss|fall)|"
    r"regrow|grow (?:back|new)|get rid of .* forever|miracle)\b", re.I)
CLAIM_QUESTION_AR = re.compile(r"(يعالج|علاج نهائي|يشفي|مضمون|نهائيا|نهائياً|للابد|للأبد|يوقف|معجزه|معجزة)")


@lru_cache(maxsize=1)
def _rules() -> dict:
    with open(DATA_DIR / "blocked_terms.json", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {lang: [(re.compile(r["pattern"], re.I), r["replace"]) for r in raw[lang]] for lang in ("en", "ar")}


def violations(text: str) -> list[str]:
    found = []
    for lang, rules in _rules().items():
        for rx, _ in rules:
            m = rx.search(text or "")
            if m:
                found.append(m.group(0))
    return found


def soften(text: str) -> str:
    out = text or ""
    for rules in _rules().values():
        for rx, rep in rules:
            out = rx.sub(rep, out)
    return out


def is_claim_question(text: str) -> bool:
    return bool(CLAIM_QUESTION_EN.search(text or "") or CLAIM_QUESTION_AR.search(text or ""))
