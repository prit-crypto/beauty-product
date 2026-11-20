"""Picks the provider from AI_PROVIDER (rule | gemini | openai) and wraps it so any failure falls back to rules.

Rule extraction always runs; AI extraction only adds what the rules missed. AI wording is validated before use:
no blocked claims, and no number that is not in the facts.
"""
import logging
import re
import threading
import time

from app.config import settings
from app.engine import claims
from app.providers.rule import RuleProvider

log = logging.getLogger("providers")
COOLDOWN_S = 20
_cooldown_until: dict[str, float] = {}
_lock = threading.Lock()


def _describe(e: Exception) -> str:
    status = getattr(getattr(e, "response", None), "status_code", None)
    if status == 429:
        return "429 quota or rate limit"
    if status:
        return f"HTTP {status}"
    return type(e).__name__
_override: str | None = None
_cache: dict[str, object] = {}
SUPPORTED = ("rule", "gemini", "openai")


def _make(name: str):
    if name == "gemini":
        from app.providers.gemini import GeminiProvider
        return GeminiProvider()
    if name == "openai":
        from app.providers.openai_p import OpenAIProvider
        return OpenAIProvider()
    return RuleProvider()


def available() -> dict[str, bool]:
    return {"rule": True, "gemini": bool(settings.gemini_api_key), "openai": bool(settings.openai_api_key)}


def set_override(name: str | None) -> None:
    global _override
    if name is not None and name not in SUPPORTED:
        raise ValueError(f"unknown provider {name}")
    with _lock:
        _override = name
        _cooldown_until.clear()


def active_name() -> str:
    return _override or settings.ai_provider


class FallbackProvider:
    def __init__(self, primary_name: str):
        self.rule = RuleProvider()
        self.primary = None
        self.requested = primary_name
        if primary_name != "rule":
            try:
                if primary_name not in _cache:
                    _cache[primary_name] = _make(primary_name)
                self.primary = _cache[primary_name]
            except Exception as e:  # missing key etc.
                log.warning("provider %s unavailable, using rule: %s", primary_name, e)
        self.used = "rule"
        self.errors: list[str] = []

    @property
    def name(self) -> str:
        return self.primary.name if self.primary else "rule"

    def _try(self, fn, *a, **kw):
        if not self.primary:
            return None
        name = self.primary.name
        if time.monotonic() < _cooldown_until.get(name, 0):
            # after a failure, skip the AI for a short while so the chat stays fast (rules answer meanwhile)
            if f"{name}: cooling down" not in self.errors:
                self.errors.append(f"{name}: cooling down")
            return None
        try:
            out = fn(*a, **kw)
            self.used = name
            return out
        except Exception as e:
            self.errors.append(f"{name}: {_describe(e)}")
            _cooldown_until[name] = time.monotonic() + COOLDOWN_S
            log.warning("provider %s failed (%s); using rules for %ss", name, _describe(e), COOLDOWN_S)
            return None

    def extract(self, text: str, lang: str, context: dict) -> dict:
        base = self.rule.extract(text, lang, context)
        ai = self._try(getattr(self.primary, "extract", None), text, lang, context) if self.primary else None
        if not ai:
            return base
        merged = dict(base)
        merged["area"] = base["area"] or ai["area"]
        area = merged["area"] or context.get("area")
        merged["concerns"] = list(dict.fromkeys(base["concerns"] + (ai["concerns"] if (ai["area"] or context.get("area")) == area else [])))
        merged["budget"] = base["budget"] or ai["budget"]
        merged["sensitivity"] = base["sensitivity"] or ai["sensitivity"]
        # anything that changes the cart, resets or orders needs the customer's own words, not only the AI's reading
        risky = {"restart", "cart_clear", "cart_remove", "order_cancel", "checkout", "add_to_cart", "add_item"}
        ai_intents = [i for i in ai["intents"] if i not in risky or i in base["intents"]]
        merged["intents"] = list(dict.fromkeys(base["intents"] + ai_intents))
        merged["only"] = bool(base.get("only") or ai.get("only"))
        merged["unsupported"] = base.get("unsupported") or []
        # off-topic keywords are a rough net: when the AI read the message, its judgement decides
        if "off_topic" in base["intents"] and "off_topic" not in ai["intents"]:
            merged["intents"].remove("off_topic")
        merged["tone_change"] = bool(base.get("tone_change"))
        merged["budget_too_low"] = base.get("budget_too_low")
        merged["price_change"] = bool(base.get("price_change"))
        merged["about_routine"] = bool(base.get("about_routine"))
        merged["other_brand"] = bool(base.get("other_brand"))
        merged["off_topic_part"] = bool(base.get("off_topic_part")) and "off_topic" in ai["intents"]
        if "premium" in ai["intents"] and "premium" not in base["intents"] and "cheaper" in merged["intents"]:
            merged["intents"].remove("premium")  # never upsell luxury when the customer is asking for cheaper
        merged["medical"] = bool(ai.get("medical"))
        # the AI resolves references ("the first one", "it") from the conversation, so its products come first
        merged["products"] = list(dict.fromkeys((ai.get("products") or []) + base["products"]))
        merged["named"] = base["products"]  # what the customer actually typed, as opposed to "it"/"this" the AI resolved
        merged["name"] = base.get("name") or ai.get("name")
        merged["faq"] = list(dict.fromkeys((base.get("faq") or []) + ([ai["faq"]] if ai.get("faq") else [])))
        bs, ais = base.get("search") or {}, ai.get("search") or {}
        merged["search"] = {**bs, "max_price": bs.get("max_price") or ais.get("max_price"),
                            "category": ais.get("category"), "type": ais.get("type")}
        if ai.get("products"):
            merged["ref"] = None  # already resolved by the AI
        return merged

    def classify_safety(self, text: str) -> bool | None:
        return self._try(getattr(self.primary, "classify_safety", None), text) if self.primary else None

    def phrase(self, lang: str, draft: str, facts: dict, mode: str = "rewrite", history=None) -> str | None:
        if not self.primary or (mode == "rewrite" and not settings.ai_rewrite):
            return None
        out = self._try(self.primary.phrase, lang, draft, facts, mode, history)
        if not out:
            return None
        out = claims.soften(out)
        context_text = " ".join(h.get("text", "") for h in (history or []))
        if _claims_action(out) and not facts.get("actions_done"):
            self.errors.append(f"{self.primary.name}: rejected wording (claimed an action that did not happen)")
            return None
        if _list_items(out) < _list_items(draft):
            self.errors.append(f"{self.primary.name}: rejected wording (dropped list items)")
            return None
        if not _numbers_ok(out, draft + " " + context_text, facts):
            self.errors.append(f"{self.primary.name}: rejected wording (numbers)")
            return None
        return out


NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
ACTION_CLAIM = re.compile(
    r"\b(i(?:'ve| have)?|we(?:'ve| have)?)\s+(?:just\s+|now\s+|already\s+|gone ahead and\s+)?"
    r"(added|removed|cleared|deleted|emptied|corrected|updated|changed|adjusted|replaced|taken out|placed|put|swapped|cancelled|reverted"
    r"|made sure|ensured|fixed|sorted|taken care|kept only|left only|reset)\b"
    r"|\b(is|are) now in your cart\b|\b(has|have) been (added|removed|cleared|deleted)\b|\byour cart is (now )?empty\b",
    re.I)
ACTION_CLAIM_AR = re.compile(r"(أضفت|اضفت|حذفت|أزلت|ازلت|أفرغت|افرغت|مسحت|عدلت|غيرت|ألغيت|الغيت)")


def _list_items(text: str) -> int:
    return sum(1 for ln in (text or "").split("\n") if re.match(r"\s*(?:[-•*]|\d+[.)])\s+\S", ln))


def _claims_action(text: str) -> bool:
    return bool(ACTION_CLAIM.search(text or "") or ACTION_CLAIM_AR.search(text or ""))


def _nums(s: str) -> set[str]:
    return {n.replace(",", "").rstrip(".").removesuffix(".0") for n in NUM.findall(s or "")}


def _numbers_ok(out: str, draft: str, facts: dict) -> bool:
    import json as _json
    allowed = _nums(draft) | _nums(_json.dumps(facts, ensure_ascii=False))
    for n in _nums(out.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))):
        if n in allowed:
            continue
        try:
            if float(n) <= 31:  # small counts: "2 times a week", "24 hours", "24K"
                continue
        except ValueError:
            pass
        return False
    return True


def get_provider() -> FallbackProvider:
    return FallbackProvider(active_name())
