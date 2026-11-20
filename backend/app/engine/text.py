"""Small text helpers shared by the engine: language detection, Arabic digits, budget parsing, keyword matching."""
import re

AR_CHARS = re.compile(r"[؀-ۿ]")
LATIN_CHARS = re.compile(r"[A-Za-z]")
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
AR_PREFIXES = ("", "ال", "و", "وال", "ب", "بال", "ل", "لل", "ف", "فال", "ك")


def detect_lang(text: str, current: str | None = None) -> str:
    """Arabic script wins; otherwise keep the session language (default English)."""
    if AR_CHARS.search(text or ""):
        return "ar"
    if LATIN_CHARS.search(text or ""):
        return "en"
    return current or "en"


def normalize(text: str) -> str:
    t = (text or "").translate(AR_DIGITS).lower()
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    t = re.sub(r"[ً-ْـ]", "", t)  # tashkeel + tatweel
    return t


def _norm_term(term: str) -> str:
    return normalize(term)


def contains_term(text_norm: str, term: str) -> bool:
    """Prefix-at-word-start match. English: \\bterm. Arabic: a token that equals prefix+term or starts with it."""
    t = _norm_term(term)
    if not t:
        return False
    if AR_CHARS.search(t):
        if " " in t:
            return t in text_norm
        for tok in re.findall(r"[؀-ۿ]+", text_norm):
            for p in AR_PREFIXES:
                if tok.startswith(p + t):
                    return True
        return False
    if len(t) <= 4 and " " not in t and t not in PREFIX_STEMS:
        # short words must match a whole word (plural allowed): "thin" must not match "things", "foot" not "football"
        return re.search(r"(?<![a-z])" + re.escape(t) + r"(?:s|es)?(?![a-z])", text_norm) is not None
    return re.search(r"(?<![a-z])" + re.escape(t), text_norm) is not None


# short keyword stems that are meant to match longer words ("gumm" -> gummies)
PREFIX_STEMS = {"gumm", "curl", "sag", "firm", "lift", "glow", "pore", "dull", "acne", "dry", "dye", "oily", "limp", "rash"}
# (everything else short must be a whole word: thin/things, foot/football, skin/skinny, card/cardigan, sale/salem...)


def find_terms(text: str, terms: list[str]) -> list[str]:
    n = normalize(text)
    return [t for t in terms if contains_term(n, t)]


BUDGET_RX = [
    re.compile(r"(?:aed|dhs?|dirhams?|درهم|د\.?ا)\s*([\d,]{2,6})"),
    re.compile(r"([\d,]{2,6})\s*(?:aed|dhs?|dirhams?|درهم|د\.?ا)"),
    re.compile(r"(?:budget|spend|under|max(?:imum)?|up to|around|about|ميزانيه|ميزانيتي|حدود|اقل من|تحت)\D{0,12}([\d,]{2,6})"),
]


def parse_budget(text: str) -> int | None:
    n = normalize(text)
    for rx in BUDGET_RX:
        m = rx.search(n)
        if m:
            try:
                v = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if 50 <= v <= 100000:
                return v
    return None


def fmt_aed(v: float, lang: str = "en") -> str:
    s = f"{v:,.0f}"
    return f"AED {s}" if lang == "en" else f"{s} درهم"
