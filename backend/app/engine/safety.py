"""Safety gate: runs on EVERY customer message before anything else.

Any hit stops selling and hands the conversation to Dr. Shaymaa's team.
"""
import json
import re
from dataclasses import dataclass
from functools import lru_cache

from app.config import DATA_DIR
from app.engine.text import find_terms


@dataclass
class SafetyResult:
    hit: bool
    category: str = ""
    term: str = ""
    source: str = "rules"


@lru_cache(maxsize=1)
def _terms() -> dict:
    with open(DATA_DIR / "safety_terms.json", encoding="utf-8") as fh:
        return json.load(fh)


# "I'm 16", "15 years old", "عمري 16": products are for adults, so anyone under 18 goes to the team
_AGE_EN = re.compile(r"\b(?:i'?m|i am|im|aged?|age is|my age is)\s*(1[0-7]|[1-9])\b(?!\s*(?:aed|dhs?|dirhams?|feet|ft|cm|kg|%|products?|items?|months?|weeks?|days?))"
                     r"|\b(1[0-7]|[1-9])\s*(?:years?|yrs?)(?:\s*old)?\b|\b(1[0-7]|[1-9])\s*y/?o\b"
                     r"|\b(?:teen|teenager|teenage|under 18|underage|minor)\b", re.I)
_AGE_AR = re.compile(r"عمري\s*(1[0-7]|[1-9])(?!\d)|(?<!\d)(1[0-7]|[1-9])\s*(?:سنه|سنة|سنوات|عام)|مراهق")


def check(text: str) -> SafetyResult:
    terms = _terms()
    for lang in ("en", "ar"):
        for category, words in terms[lang].items():
            found = find_terms(text, words)
            if found:
                return SafetyResult(True, category, found[0])
    plain = (text or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    m = _AGE_EN.search(plain) or _AGE_AR.search(plain)
    if m:
        return SafetyResult(True, "child", m.group(0))
    return SafetyResult(False)
