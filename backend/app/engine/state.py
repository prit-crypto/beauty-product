"""Conversation engine. One call per customer message (or quick-reply button).

Every turn:
  1. safety gate (keywords; plus the AI's medical flag when an AI provider is active) -> hand-off, nothing sold
  2. understand the message with the recent conversation (rules, merged with the AI when available)
  3. decide what to do: FAQ, recap, cart, compare, browse, add/remove, product questions, or the consultation
  4. the AI writes the reply in a natural voice from the engine's facts (validated); cards stay deterministic
  5. remember: conversation history, name, products just shown, cart
"""
import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from app.config import DATA_DIR
from app.engine import claims, safety
from app.engine.catalog import get_catalog
from app.engine import questions as Q
from app.engine.recommender import build
from app.engine.templates import join_list, slot_label, t
from app.engine.text import detect_lang, fmt_aed

AREA_CHIPS = ["skin", "hair", "supplement"]
CONCERN_CHIPS = {
    "skin": ["fine_lines", "dullness", "dark_spots", "dryness", "pores", "dark_circles", "sagging"],
    "hair": ["dry_damaged", "colour_treated", "frizz", "curly", "flat_volume", "hair_fall", "dandruff"],
    "supplement": ["hair_growth", "skin_glow", "immunity", "sleep"],
}
INTENT_ACTIONS = {"add_routine": "add_to_cart", "premium": "premium", "cheaper": "cheaper", "how_to_use": "how_to_use",
                  "restart": "restart", "recap": "recap", "cart_status": "cart_status", "human": "human", "checkout": "checkout"}
BUDGET_CHIPS = [("qr_b500", "500"), ("qr_b1000", "1000"), ("qr_b2500", "2500"), ("qr_bnone", "none")]
HISTORY_KEEP = 80  # remembered per conversation; the AI sees the last 30 turns


@dataclass
class Session:
    id: str
    lang: str = "en"
    stage: str = "start"
    area: str | None = None
    concerns: list[str] = field(default_factory=list)
    concerns_done: bool = False
    sensitivity: str | None = None
    budget: int | None = None
    budget_asked: bool = False
    fast_path: bool = False
    premium: bool = False
    min_mode: bool = False  # the customer asked for the cheapest option
    fill: bool = False  # "my budget is higher, add more": use the budget for every relevant extra
    excluded_min: list[str] = field(default_factory=list)  # temporary: cheaper rivals set aside for "cheapest" mode
    unanswered: int = 0  # how many times the current question went unanswered
    answers: dict = field(default_factory=dict)  # profile questions answered: {"skin_type": "oily", ...}
    essentials: bool = False  # "just the essentials": one product per concern, the rest as optional extras
    off_topic_count: int = 0  # off-topic messages so far: the full list of what the assistant can do is shown the first time
    awaiting: str = ""  # what the last reply offered: add_routine | add_product | checkout | handoff, so "yes" does that
    orders: list[dict] = field(default_factory=list)  # orders placed in this chat (id, items, total, name, phone, when)
    routine: dict | None = None
    handoff: bool = False
    handoff_topic: str = ""
    cart_value: float = 0.0
    turns: int = 0
    # memory
    name: str | None = None
    history: list[dict] = field(default_factory=list)  # [{"role": "user"|"assistant", "text": ...}]
    last_products: list[str] = field(default_factory=list)  # ids shown in the last cards, for "the first one" / "it"
    last_card: str = ""
    last_list: list[str] = field(default_factory=list)  # the last list shown (browse, compare, routine) for "the second one"
    last_single: str | None = None  # the last single product discussed, for "it"
    excluded: list[str] = field(default_factory=list)  # products the customer took out of the routine
    cart: list[dict] = field(default_factory=list)  # snapshot of the browser cart

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def _faq() -> dict:
    with open(DATA_DIR / "faq.json", encoding="utf-8") as fh:
        return json.load(fh)["topics"]


# ---------------------------------------------------------------- reply helpers
def _reply(s: Session, text: str, cards=None, qrs=None, event: str | None = None, kind: str = "text",
           facts: dict | None = None, mode: str = "rewrite", ai: bool = True) -> dict:
    return {"text": text, "cards": cards or [], "quick_replies": qrs or [], "lang": s.lang,
            "dir": "rtl" if s.lang == "ar" else "ltr", "event": event, "kind": kind,
            "_facts": facts or {}, "_mode": mode, "_ai": ai}


def _sum(p: dict, lang: str) -> str:
    """The product's one-line summary in the chat's language."""
    return (p.get("summary_ar") if lang == "ar" else None) or p["summary"]


def _how(p: dict, lang: str) -> str:
    """The usage directions in the chat's language ('' when the shop page gave none)."""
    return ((p.get("how_to_use_ar") if lang == "ar" else None) or p.get("how_to_use") or "")


def _qr(s: Session, key: str, action: str) -> dict:
    return {"label": t(s.lang, key), "action": action}


def _area_qrs(s: Session) -> list[dict]:
    return [_qr(s, f"qr_{a}", f"area:{a}") for a in AREA_CHIPS]


def _default_qrs(s: Session) -> list[dict]:
    return _post_qrs(s) if s.routine else _area_qrs(s)


def _browse_qrs(s: Session, products: list[dict] | None = None) -> list[dict]:
    """Buttons after showing products: next steps that fit what was shown, not the generic Skin/Hair/Supplements."""
    if s.routine:
        return _post_qrs(s)
    areas = {("hair" if p["category"] == "anti-hair-loss" else p["area"]) for p in products or []}
    area = next(iter(areas)) if len(areas) == 1 else s.area
    q = [_qr(s, f"qr_choose_{area}", f"area:{area}")] if area in ("skin", "hair", "supplement") else []
    if s.cart:
        q += [_qr(s, "qr_cart", "cart_status"), _qr(s, "qr_checkout", "checkout")]
    return q or _area_qrs(s)


def _concern_qrs(s: Session, area: str, exclude: list[str]) -> list[dict]:
    cat = get_catalog()
    return [{"label": cat.concern_label(area, c, s.lang), "action": f"concern:{c}"} for c in CONCERN_CHIPS[area] if c not in exclude]


def _labels(s: Session) -> str:
    cat = get_catalog()
    return join_list(s.lang, [cat.concern_label(s.area, c, s.lang).lower() if s.lang == "en" else cat.concern_label(s.area, c, s.lang)
                              for c in s.concerns])


def _profile(s: Session) -> dict:
    """What the advisor knows about the customer; given to the AI on every reply."""
    cat = get_catalog()
    return {
        "name": s.name, "language": s.lang, "topic": s.area,
        "concerns": [cat.concern_label(s.area, c, "en") for c in s.concerns] if s.area else [],
        "budget_aed": s.budget, "sensitive": s.sensitivity == "sensitive",
        "current_routine": ({"items": [f"{x['name']} (AED {x['price_aed']:.0f}, {x['slot']})" for x in s.routine["steps"]],
                             "total_aed": s.routine["total"], "premium": s.routine["tier"] == "premium"} if s.routine else None),
        "cart": [f"{i.get('name')} x{i.get('qty', 1)} (AED {i.get('price_aed', 0):.0f})" for i in s.cart],
    }


# ---------------------------------------------------------------- main entry
def handle(s: Session, message: str = "", action: str | None = None, provider=None, cart: list | None = None,
           label: str | None = None) -> dict:
    from app.providers.factory import get_provider
    prov = provider or get_provider()
    if cart is not None:
        s.cart = clean_cart(cart)
    s.turns += 1
    text = (message or "").strip()
    if text:
        s.lang = detect_lang(text, s.lang)
    user_turn = text or label or ""

    rep = _route(s, text, action, prov)

    facts, mode, use_ai = rep.pop("_facts"), rep.pop("_mode"), rep.pop("_ai")
    question = rep.pop("_question", None)
    facts.setdefault("actions_done", [])  # the AI may only describe these; anything else it must not claim
    if use_ai and question and rep["text"].endswith(question):
        # a consultation question: the AI writes a short reaction to what was said; the question (which matches
        # the buttons) is added word for word
        lead = rep["text"][: -len(question)].strip()
        reaction = prov.phrase(s.lang, lead, {**facts, "customer": _profile(s), "customer_message": user_turn}, "react",
                               s.history[-30:] + ([{"role": "user", "text": user_turn}] if user_turn else []))
        if reaction:  # keep the first full sentence that isn't a question ("Dr." and "No." don't end a sentence)
            safe = re.sub(r"\b(Dr|No|Mr|Ms|Mrs)\.", lambda m: m.group(1) + "\u2024", reaction.strip())
            sentences = [x for x in re.split(r"(?<=[.!؟?])\s+", safe) if x and not x.rstrip().endswith(("?", "؟"))]
            reaction = sentences[0].replace("\u2024", ".") if sentences else ""
        rep["text"] = f"{reaction or lead} {question}".strip()
        use_ai = False
    if use_ai:
        worded = prov.phrase(s.lang, rep["text"], {**facts, "customer": _profile(s), "customer_message": user_turn},
                             mode, s.history[-30:] + ([{"role": "user", "text": user_turn}] if user_turn else []))
        if worded:
            rep["text"] = worded
    rep["text"] = claims.soften(rep["text"])

    # ---- memory
    if user_turn:
        s.history.append({"role": "user", "text": user_turn[:600]})
    s.history.append({"role": "assistant", "text": rep["text"][:800]})
    s.history = s.history[-HISTORY_KEEP:]
    _sync_cart(s, rep["cards"])
    if rep["kind"] in ("fallback", "info", "claim", "faq", "smalltalk", "text") and not rep["cards"]:
        named = get_catalog().find_mentioned(rep["text"])
        if len(named) == 1:  # "...start with the Day Cream. Shall I add it?" -> "yes, add only that one"
            s.last_single, s.last_card = named[0]["id"], "product"
    shown = _shown_ids(rep["cards"])
    if shown:
        s.last_products, s.last_card = shown, rep["cards"][0]["type"]
        if s.last_card == "product":
            s.last_single = shown[0]
        elif s.last_card in ("product_list", "compare", "routine"):
            s.last_list = shown
    return rep


def clean_cart(cart: list) -> list[dict]:
    """The cart as the server trusts it: known products only, catalogue names and prices (never the browser's),
    quantities 1-20, each product once."""
    cat = get_catalog()
    out: dict[str, dict] = {}
    for c in cart or []:
        if not isinstance(c, dict) or c.get("id") not in cat.by_id:
            continue
        p = cat.get(c["id"])
        try:
            qty = int(c.get("qty", 1))
        except (TypeError, ValueError):
            qty = 1
        qty = max(1, min(qty, 20))
        if p["id"] in out:
            out[p["id"]]["qty"] = min(out[p["id"]]["qty"] + qty, 20)
        else:
            out[p["id"]] = {"id": p["id"], "name": p["name"], "price_aed": p["price_aed"], "qty": qty}
    return list(out.values())[:50]


def _sync_cart(s: Session, cards: list[dict]) -> None:
    """Mirror what the browser will do with the cart cards, so the next turn sees the right cart."""
    for c in cards:
        if c["type"] == "cart_add":
            for it in c["items"]:
                line = next((x for x in s.cart if x.get("id") == it["id"]), None)
                if line:
                    line["qty"] = int(line.get("qty", 1)) + 1
                else:
                    s.cart.append({**it, "qty": 1})
        elif c["type"] == "cart_remove":
            s.cart = [x for x in s.cart if x.get("id") not in c["ids"]]
        elif c["type"] == "cart_clear":
            s.cart = []


def _shown_ids(cards: list[dict]) -> list[str]:
    for c in cards:
        if c["type"] == "routine":
            return [x["id"] for x in c["routine"]["steps"]] + [x["id"] for x in c["routine"]["addons"]]
        if c["type"] == "product":
            return [c["product"]["id"]]
        if c["type"] in ("product_list", "compare"):
            return [x["id"] for x in c["items"]]
    return []


def _route(s: Session, text: str, action: str | None, prov) -> dict:
    cat = get_catalog()
    L = s.lang

    if not text and not action:  # widget opened
        s.stage = "ask_area"
        if s.history:
            return _reply(s, t(L, "greet_again", s.turns, name_part=f", {s.name}" if s.name else ""), qrs=_default_qrs(s), ai=False)
        return _reply(s, t(L, "greet", s.turns) + "\n\n" + t(L, "safety_note"), qrs=_area_qrs(s), ai=False)

    # ---- 1. safety gate, keyword part (free text only; buttons can't carry medical content)
    if text and not action:
        res = safety.check(text)
        if res.hit:
            return _handoff(s, res.category)

    # ---- 2. understand
    ex = {"area": None, "concerns": [], "budget": None, "sensitivity": None, "intents": [], "products": [],
          "medical": False, "name": None, "faq": [], "search": {}, "ref": None, "only": False, "unsupported": []}
    if action:
        if action.startswith("lang:"):  # the EN / ع switch: same conversation, now in the other language
            if action[5:] in ("en", "ar"):
                s.lang = action[5:]
            return _switch_language(s)
        if action == "handoff_request":
            return _handoff(s, "product")
        if action == "human":
            return _human(s)
        if action == "continue":  # "Continue shopping": pick up where the chat was
            back, qrs = _resume(s, "")
            return _reply(s, t(L, "continue_ok", s.turns) + " " + back, qrs=qrs, facts={"back_to": back})
        if action == "cart_clear":
            return _cart_edit(s, "cart_clear", [])
        if action.startswith("cart_remove:"):
            pid = action.split(":", 1)[1]
            return _cart_edit(s, "cart_remove", [cat.get(pid)] if pid in cat.by_id else [])
        if action == "q:supp_safety:yes":  # pregnant, breastfeeding, under 18 or on medication: the team advises first
            s.answers["supp_safety"] = "yes"
            return _handoff(s, "product")
        if action.startswith("add_item:"):
            pid = action.split(":", 1)[1]
            if pid in cat.by_id:
                return _add_item(s, cat.get(pid))
        if action in INTENT_ACTIONS:
            ex["intents"] = [INTENT_ACTIONS[action]]
        else:
            _apply_action(s, action)
    else:
        ex = {**ex, **prov.extract(text, L, {"stage": s.stage, "area": s.area, "history": s.history[-20:],
                                               "last_products": s.last_list or s.last_products, "last_single": s.last_single})}
        if ex.get("medical"):  # safety gate, AI part: medical topics the keyword list missed
            return _handoff(s, "condition")

    intro = ""
    if ex.get("name") and ex["name"] != s.name:
        s.name = ex["name"]
        intro = t(L, "nice_to_meet", s.turns, name=s.name)

    awaiting, s.awaiting = s.awaiting, ""
    rep = _dispatch(s, text, ex, prov, just_named=bool(intro), awaiting=awaiting)
    if ex.get("unsupported") and rep["kind"] not in ("unsupported", "handoff"):
        from app.providers.rule import _unsupported
        need = join_list(L, [_unsupported()[n][L] for n in ex["unsupported"]])
        rep["text"] = t(L, "unsupported_need", need=need) + " " + rep["text"]
        rep["_facts"]["not_in_range"] = ex["unsupported"]
    if ex.get("price_change") and rep["kind"] != "handoff":
        rep["text"] = t(L, "price_fixed") + " " + rep["text"]
        rep["_facts"]["important"] = t("en", "price_fixed")
    if ex.get("tone_change") and rep["kind"] not in ("handoff",):
        rep["text"] = t(L, "tone_note") + " " + rep["text"]
        rep["_facts"]["important"] = t("en", "tone_note")
    if ex.get("off_topic_part") and rep["kind"] not in ("off_topic", "handoff", "unsupported"):
        # "who won the match? and how much is the night cream?" -> decline the first part, answer the second
        rep["text"] = t(L, "off_topic_part") + " " + rep["text"]
        rep["_facts"]["declined_unrelated_part_of_message"] = True
    if intro and rep["kind"] != "handoff":
        rep["text"] = f"{intro} {rep['text']}"
    return rep


def _resolve_products(s: Session, text: str, ex: dict) -> list[dict]:
    cat = get_catalog()
    mentioned = [cat.get(pid) for pid in ex.get("products") or []]
    ref = ex.get("ref")
    intents = set(ex["intents"])
    # "it"/"that one" only point at a product when the message is about doing something with a product,
    # not in sentences like "...as IT was my budget"
    acts = {"add_item", "add_to_cart", "remove_item", "compare", "how_to_use", "cart_remove"}
    if ref is not None and not (intents & acts) and len(text.split()) > 8:
        ref = None
    if not mentioned and ref is not None:
        lst = s.last_list or s.last_products
        if ref == "both" and lst:
            mentioned = [cat.get(i) for i in lst[:2]]
        elif ref == "it":
            if s.last_card == "product" and s.last_single:
                mentioned = [cat.get(s.last_single)]
            elif len(s.last_products) == 1:
                mentioned = [cat.get(s.last_products[0])]
        elif isinstance(ref, int) and lst and -len(lst) <= ref < len(lst):
            mentioned = [cat.get(lst[ref])]
            # "how is IT different from the second one?": the product just discussed is the other side
            if "compare" in intents and s.last_single and s.last_single != lst[ref]:
                mentioned = [cat.get(s.last_single)] + mentioned
    if not mentioned and s.routine and intents & {"remove_item", "add_item", "how_to_use", "question", "compare"}:
        p = _routine_product(s.routine, text)
        if p:
            mentioned = [p]
    return mentioned


def _dispatch(s: Session, text: str, ex: dict, prov, just_named: bool = False, awaiting: str = "") -> dict:
    cat = get_catalog()
    L = s.lang
    intents = set(ex["intents"])
    mentioned = _resolve_products(s, text, ex)
    new_info = bool(ex["concerns"] or ex["budget"] or ex["area"])
    # products the customer NAMED in this message (not "it"/"this", which the AI may resolve to a single product)
    named = [cat.get(i) for i in (ex.get("named") if ex.get("named") is not None else ex.get("products") or []) if i in cat.by_id]
    if not named and s.routine:
        rp = _routine_product(s.routine, text)
        named = [rp] if rp else []

    if "restart" in intents:
        _reset(s)
        s.stage = "ask_area"
        return _reply(s, t(L, "restart", s.turns), qrs=_area_qrs(s), ai=False)

    if "human" in intents:
        return _human(s)

    if "history" in intents and not new_info:
        return _history_reply(s)

    faq_now = ex.get("faq") or []
    if ("order_status" in faq_now or "order_cancel" in intents) and s.orders:
        return _order_cancel(s) if "order_cancel" in intents else _order_status(s)
    if "order_cancel" in intents and not s.orders:
        # no order in this chat: never empty the cart on a guess; ask first
        if s.cart:
            return _reply(s, t(L, "cancel_no_order_cart", items=join_list(L, [c["name"] for c in s.cart])),
                          qrs=[_qr(s, "qr_clear_cart", "cart_clear"), _qr(s, "qr_keep_cart", "continue")], kind="text",
                          facts={"actions_done": []})
        back, qrs = _resume(s, awaiting)
        return _reply(s, t(L, "no_order_in_chat") + " " + back, qrs=qrs, kind="text", facts={"back_to": back})
    if "order_status" in faq_now and not s.orders and not (intents - {"question", "greeting", "thanks"}):
        back, qrs = _resume(s, awaiting)
        return _reply(s, t(L, "no_order_in_chat") + " " + back, qrs=qrs + [_qr(s, "qr_human", "human")], kind="text",
                      facts={"back_to": back})

    if "checkout" in intents:
        return _checkout(s)

    unsupported = ex.get("unsupported") or []
    if unsupported:
        from app.providers.rule import _unsupported
        if not ex["concerns"] or any(_unsupported()[n].get("overrides_concerns") for n in unsupported):
            return _unsupported_reply(s, unsupported)

    if s.stage == "ask_more" and text and not [c for c in ex["concerns"] if c not in s.concerns] \
            and ex["area"] in (None, s.area) and not named and \
            ("deny" in intents or Q.done_words(text)):
        s.concerns_done = True  # "nothing else", "that's all", "بس كذا"
        if ex["budget"]:
            s.budget, s.budget_asked = ex["budget"], True
        return _next(s)
    if s.stage.startswith("ask_q:") and text and s.stage[6:] in Q.BY_KEY:
        q = Q.BY_KEY[s.stage[6:]]
        opt = Q.match_option(q, text)
        if opt:
            if q.key == "supp_safety" and opt.value == "yes":
                s.answers[q.key] = "yes"
                return _handoff(s, "product")
            Q.apply(s, q, opt.value)
            if not (ex["concerns"] or ex["budget"] or ex["area"] or named or (intents - {"affirm", "deny", "question", "thanks"})):
                return _next(s)

    actionable = intents - {"affirm", "deny", "question", "thanks", "greeting"}
    if "affirm" in intents and not actionable and not new_info and not named:
        if awaiting == "add_routine" and s.routine:
            return _add_to_cart(s)
        if awaiting == "add_product" and s.last_single:
            p = cat.get(s.last_single)
            return _caution(s, p) if (p["caution"] or p["handoff"]) else _add_item(s, p)
        if awaiting == "checkout":
            return _checkout(s)
        if awaiting == "checkout_form" and s.cart:
            s.awaiting = "checkout_form"
            return _reply(s, t(L, "checkout_fill_form"), kind="text", facts={"actions_done": []})
        if awaiting == "handoff":
            return _handoff(s, "product")
        if s.stage == "ask_sensitivity":
            s.sensitivity = "sensitive"
            return _next(s)
        if not s.routine:
            return _next(s)  # nothing pending: carry on with the consultation
        return _reply(s, t(L, "what_next", s.turns), qrs=_post_qrs(s), kind="text")
    if "deny" in intents and not actionable and not new_info:
        if s.stage == "ask_sensitivity":
            s.sensitivity = "none"
            return _next(s)
        if awaiting in ("add_routine", "add_product", "checkout", "handoff"):
            return _reply(s, t(L, "no_problem", s.turns), qrs=_default_qrs(s), kind="text")

    if "capabilities" in intents and not new_info and not mentioned and not ex.get("faq"):
        back, qrs = _resume(s, awaiting)
        caps = t(L, "capability_list")
        return _reply(s, t(L, "capabilities", s.turns, capabilities=caps) + "\n\n" + back, qrs=qrs, kind="capabilities",
                      facts={"what_i_can_do": caps.split("\n"), "back_to": back})

    if "off_topic" in intents and not new_info and not mentioned and not ex.get("faq"):
        # politely say no, say what the assistant CAN do, then pick the conversation up exactly where it was
        back, qrs = _resume(s, awaiting)
        caps = t(L, "capability_list")
        first = s.off_topic_count % 3 == 0  # the full list the first time (and now and then), a short line otherwise
        s.off_topic_count += 1
        lead = t(L, "off_topic", s.turns, capabilities=caps) if first else t(L, "off_topic_again", s.turns)
        return _reply(s, lead + "\n\n" + back, qrs=qrs, kind="off_topic",
                      facts={"declined": "the message is not about Dr. Beauty Care, its products or orders",
                             "what_i_can_do": caps.split("\n") if first else [], "back_to": back})

    if ex.get("budget_too_low") is not None and not ex["budget"] and not ex["concerns"]:
        cheapest = min(p["price_aed"] for p in cat.products if p["concerns"])
        back, qrs = _resume(s, awaiting)
        return _reply(s, t(L, "budget_too_low", budget=fmt_aed(ex["budget_too_low"], L), cheapest=fmt_aed(cheapest, L)) + " " + back,
                      qrs=qrs, facts={"back_to": back, "cheapest_product_aed": cheapest})
    if ex.get("other_brand") and (intents & {"compare", "question", "search"} or "?" in text or "؟" in text):
        ours = [p for p in mentioned if p] or []
        if ours:  # "is your serum better than La Mer?": describe ours, never judge another brand
            p = ours[0]
            return _reply(s, t(L, "other_brand", product=p["name"], price=fmt_aed(p["price_aed"], L), summary=_sum(p, L)),
                          cards=[{"type": "product", "product": _pcard(p)}], qrs=_browse_qrs(s, [p]), kind="info",
                          facts={"product": _pfacts(p)})
        back, qrs = _resume(s, awaiting)
        return _reply(s, t(L, "other_brand_none") + " " + back, qrs=qrs, facts={"back_to": back})
    if ex.get("tone_change") and s.routine and not [c for c in ex["concerns"] if c not in s.concerns] and not ex["budget"]:
        back, qrs = _resume(s, awaiting)  # the honest note is added in _route
        return _reply(s, back, qrs=qrs, facts={"back_to": back})

    # "no, my skin isn't sensitive" said outside that question: note it, then carry on where we were
    if (ex["sensitivity"] and s.area and s.stage != "ask_sensitivity" and not ex["concerns"] and not ex["budget"]
            and ex["area"] in (None, s.area) and not named and "question" not in intents and not (actionable - {"off_topic"})):
        s.sensitivity = ex["sensitivity"]
        back, qrs = _resume(s, awaiting)
        return _reply(s, t(L, f"sens_noted_{ex['sensitivity']}") + " " + back, qrs=qrs, facts={"back_to": back})

    # "how much is the serum?" with no particular serum named: show the serums (in the current topic)
    if "price_question" in intents and not mentioned and not ex["concerns"]:
        srch = dict(ex.get("search") or {})
        if srch.get("steps") or srch.get("type"):
            if not srch.get("area") and s.area:
                srch["area"] = s.area
            ex["search"] = srch
            intents.add("search")

    # ---- cart edits ("remove the serum from my cart", "clear my cart", "revert the order")
    cart_op = "cart_clear" if "cart_clear" in intents else ("cart_remove" if "cart_remove" in intents else None)
    if cart_op:
        out = _cart_edit(s, cart_op, mentioned)
        # "...revert the order, and give me the best product under 300" -> clear, then the fitted suggestion
        if s.area and s.concerns and (ex["budget"] or "cheaper" in intents or "search" in intents or ex["concerns"]):
            if ex["budget"]:
                s.budget, s.budget_asked, s.premium = ex["budget"], True, False
            if "cheaper" in intents and not ex["budget"]:
                s.min_mode = True
            out = _merge(out, _recommend(s))
        return out

    # ---- store questions (payment, delivery, returns, founder...)
    faq_topics = [f for f in (ex.get("faq") or []) if f in _faq()]
    if "order_status" in faq_topics and s.orders:
        return _order_status(s)
    if faq_topics and not ex["concerns"]:
        answers = [_faq()[f][L] for f in faq_topics[:3]]
        needs_team = next((f for f in faq_topics if _faq()[f].get("handoff")), None)
        cards = [{"type": "handoff", "category": "request"}] if needs_team else []
        if needs_team:
            s.handoff, s.handoff_topic = True, needs_team
            return _reply(s, " ".join(answers), cards=cards, qrs=_default_qrs(s), kind="faq", event="handoff",
                          facts={"answers": answers})
        text_out, qrs, facts = " ".join(answers), _default_qrs(s), {"answers": answers}
        if awaiting or s.stage in MID_CONSULTATION:  # a side question: answer it, then back to where we were
            back, qrs = _resume(s, awaiting)
            text_out += "\n\n" + back
            facts["back_to"] = back
        return _reply(s, text_out, qrs=qrs, kind="faq", facts=facts)

    if "cart_status" in intents:
        return _cart_status(s)

    if "recap" in intents:
        if not s.routine or not s.routine.get("steps"):
            return _reply(s, t(L, "recap_none"), qrs=_area_qrs(s), kind="recap")
        return _reply(s, t(L, "recap", s.turns, concerns=_labels(s), total=fmt_aed(s.routine["total"], L)),
                      cards=[{"type": "routine", "routine": _localize_routine(s.routine, L)}], qrs=_post_qrs(s),
                      kind="recap", facts={"routine": s.routine})

    # ---- claims ("will this cure...")
    if "claim_question" in intents:
        p = mentioned[0] if mentioned else None
        if not p and ex["concerns"]:
            area = ex["area"] or s.area or ("hair" if ex["concerns"][0] in CONCERN_CHIPS["hair"] + ["thinning"] else "skin")
            steps = build(cat, area, ex["concerns"], None).steps
            p = steps[0].product if steps else None
        if not p and s.routine and s.routine["steps"]:
            p = cat.get(s.routine["steps"][0]["id"])
        txt = t(L, "claim_product", product=p["name"], summary=_sum(p, L)) if p else t(L, "claim_general")
        cards = [{"type": "product", "product": _pcard(p)}] if p else []
        return _reply(s, txt, cards=cards, qrs=_default_qrs(s), kind="claim", facts={"product": _pfacts(p)} if p else {})

    # ---- edit the routine
    if "remove_item" in intents and s.routine:
        ids = {x["id"] for x in s.routine["steps"] + s.routine["addons"]}
        target = next((p for p in mentioned if p["id"] in ids), None)
        if not target:
            return _reply(s, t(L, "remove_none"), qrs=_post_qrs(s), kind="text")
        s.excluded = list(dict.fromkeys(s.excluded + [target["id"]]))
        return _recommend(s, lead_key="removed", lead_kw={"product": target["name"]})

    changes_routine = bool(s.routine and (intents & {"premium", "cheaper"} or
                                          [c for c in ex["concerns"] if c not in s.concerns] or ex["budget"]))
    if intents & {"add_item", "add_to_cart"} and not changes_routine:
        from app.engine.text import find_terms
        whole = bool(find_terms(text, ["routine", "everything", "all of them", "all of it", "them all", "both", "the whole", "those",
                                       "these", "them", "all products", "the products", "الروتين", "الكل", "كلها", "هذول"])) and not ex.get("only")
        routine_offered = s.routine and (s.last_card == "routine" or awaiting == "add_routine")
        if named and not whole:
            targets = named  # "add the shampoo", "add the shampoo and the lotion", "add only the day cream"
        elif whole or (routine_offered and not ex.get("only")):
            targets = []  # "add this to my cart" right after the routine = the whole routine
        elif mentioned:
            targets = mentioned[:1]  # "add it" after a single product
        else:
            targets = []
        if targets:
            blocked = [p for p in targets if p["caution"] or p["handoff"]]
            if blocked:
                return _caution(s, blocked[0])
            return _add_items(s, targets)
        if s.routine:
            return _add_to_cart(s)
        if not new_info:
            nxt = _next(s)  # no routine yet: say so, then carry on with the consultation
            nxt["text"] = t(L, "nothing_to_add") + " " + nxt["text"]
            return nxt

    # ---- compare and browse
    if "compare" in intents and len(mentioned) == 1 and ex.get("ref") is None and not _mentions_list(text):
        # "is your day cream better than Nivea?" -> describe ours; never compare with other brands
        p = mentioned[0]
        return _reply(s, t(L, "other_brand", product=p["name"], price=fmt_aed(p["price_aed"], L), summary=_sum(p, L)),
                      cards=[{"type": "product", "product": _pcard(p)}], qrs=_browse_qrs(s, [p]), kind="info",
                      facts={"product": _pfacts(p)})
    if "compare" in intents:
        prods = mentioned[:3]
        if len(prods) < 2:
            extra = ([s.last_single] if s.last_single else []) + (s.last_list or s.last_products)[:2]
            prods = list({p["id"]: p for p in prods + [cat.get(i) for i in extra]}.values())[:2]
        if len(prods) < 2:
            return _reply(s, t(L, "compare_need_two"), qrs=_default_qrs(s))
        return _reply(s, t(L, "compare_intro", s.turns), cards=[{"type": "compare", "items": [_pcard(p) for p in prods]}],
                      qrs=_browse_qrs(s, prods), kind="compare", facts={"compared": [_pfacts(p) for p in prods]})

    if "search" in intents and not ex["concerns"] and not (intents & {"premium", "cheaper"} and s.routine):
        results, flt = _search(s, ex.get("search") or {})
        if results:
            fp = t(L, "under", price=fmt_aed(flt["max_price"], L)) if flt.get("max_price") else ""
            return _reply(s, t(L, "search_intro", s.turns, filter_part=fp),
                          cards=[{"type": "product_list", "items": [_pcard(p) for p in results]}], qrs=_browse_qrs(s, results),
                          kind="search", facts={"products_shown": [_pfacts(p) for p in results]})
        if any(flt.values()):
            return _reply(s, t(L, "search_none"), qrs=_area_qrs(s), kind="search")

    # "when should I use what?" about the whole routine: a morning / evening plan, no buy buttons
    real_named = [cat.get(i) for i in (ex.get("named") if ex.get("named") is not None else []) if i in cat.by_id]
    if s.routine and s.routine.get("steps") and ex.get("about_routine") and "how_to_use" in intents and not real_named:
        return _routine_how_to(s)

    # ---- a question about a product
    if mentioned and (not ex["concerns"] or intents & {"how_to_use", "question"}):
        p = mentioned[0]
        if p["caution"] or p["handoff"]:
            return _caution(s, p)
        if "how_to_use" in intents or ("question" in intents and s.routine and p["id"] in s.last_products):
            txt = t(L, "how_to_use", product=p["name"], how=_how(p, L)) if _how(p, L) else \
                t(L, "how_to_use_missing", product=p["name"], summary=_sum(p, L))
            mode = "answer"
        else:
            txt = t(L, "product_info", product=p["name"], price=fmt_aed(p["price_aed"], L), summary=_sum(p, L))
            mode = "answer" if "question" in intents else "rewrite"
        owned = p["id"] in {c.get("id") for c in s.cart} or p["id"] in {i for o in s.orders for i in o.get("ids", [])}
        if owned:  # already in the cart (or ordered): just answer, no buy button and no "shall I add it?"
            return _reply(s, txt, qrs=_post_qrs(s) if s.routine else _browse_qrs(s, [p]), kind="info",
                          facts={"product": _pfacts(p), "details": p["details_en"][:700], "already_in_cart_or_ordered": True,
                                 "note": "Do not offer to add this product; the customer already has it."}, mode=mode)
        s.awaiting = "add_product"
        return _reply(s, txt, cards=[{"type": "product", "product": _pcard(p)}], qrs=_browse_qrs(s, [p]), kind="info",
                      facts={"product": _pfacts(p), "details": p["details_en"][:700]}, mode=mode)

    if "how_to_use" in intents and s.routine and not (ex.get("search") or {}).get("steps"):
        return _routine_how_to(s)
    if "how_to_use" in intents and s.routine:
        want = set((ex.get("search") or {}).get("steps") or [])  # "how do I use the mask?"
        steps = [st for st in s.routine["steps"] if not want or cat.get(st["id"])["step"] in want]
        if not steps:
            return _reply(s, t(L, "how_not_in_routine"), qrs=_post_qrs(s), kind="info", facts={"routine": s.routine})
        lines = []
        for st in steps:
            p = cat.get(st["id"])
            lines.append(f"{p['name']} ({slot_label(L, st['slot'])}): {_how(p, L) or _sum(p, L)}")
        return _reply(s, "\n\n".join(lines), qrs=_post_qrs(s), kind="info", facts={"routine": s.routine}, mode="answer")

    # ---- small talk
    if not new_info and intents & {"thanks", "bye"}:
        key = "bye" if "bye" in intents else "thanks"
        return _reply(s, t(L, key, s.turns), qrs=_default_qrs(s), kind="smalltalk")
    talked_before = any(h["role"] == "user" for h in s.history)
    if not new_info and (just_named or ("greeting" in intents and not intents - {"greeting", "question"})):
        if just_named or not talked_before:
            return _next(s)  # "Hi, I'm Layla" -> "Lovely to meet you, Layla! What can I help you with...?"
        if awaiting or s.stage in MID_CONSULTATION or s.routine:
            back, qrs = _resume(s, awaiting)
            return _reply(s, t(L, "hello_again", s.turns) + " " + back, qrs=qrs, facts={"back_to": back})
        return _reply(s, t(L, "greet_again", s.turns, name_part=f", {s.name}" if s.name else ""), qrs=_default_qrs(s))

    # ---- the consultation
    area_changed = bool(ex["area"] and ex["area"] != s.area)
    new_concerns = [c for c in ex["concerns"] if c not in s.concerns]
    if area_changed:
        if s.area:  # switching topic, e.g. from skin to hair
            s.concerns, s.concerns_done, s.routine, s.premium, s.excluded = [], False, None, False, []
        s.area = ex["area"]
    if ex["concerns"]:
        s.concerns = list(dict.fromkeys(s.concerns + ex["concerns"]))
        s.concerns_done = True
    if ex["budget"]:
        s.budget, s.budget_asked, s.premium, s.min_mode = ex["budget"], True, False, False
    if ex["sensitivity"]:
        s.sensitivity = ex["sensitivity"]
    if s.stage in ("start", "ask_area") and s.area and s.concerns:
        if len(s.concerns) >= 2 or ex["budget"] or ex["sensitivity"]:
            s.fast_path = True
        elif ex["concerns"] and not s.routine:
            s.concerns_done = False  # "how can I be fair?": learn a bit more about their skin first  # described the need in one message: skip the follow-up questions except a skin budget

    if s.routine:
        if "premium" in intents:
            if s.area == "skin":
                s.premium = True
                return _recommend(s, intro_key="premium_intro")
            s.fill = True  # no luxury line for hair or supplements: use the budget for every relevant extra
            return _recommend(s, intro_key="fill_intro")
        if "cheaper" in intents:
            if s.premium or s.fill:
                s.premium = s.fill = False  # back to the everyday routine, original budget kept
                return _recommend(s, intro_key="cheaper_intro")
            if len(s.routine["steps"]) <= 1:
                return _reply(s, t(L, "already_cheapest", s.turns, product=s.routine["steps"][0]["name"] if s.routine["steps"] else "",
                                   total=fmt_aed(s.routine["total"], L)),
                              cards=[{"type": "routine", "routine": _localize_routine(s.routine, L)}], qrs=_post_qrs(s),
                              kind="routine", facts={"routine": s.routine})
            s.budget = int(s.routine["total"]) - 1
            return _recommend(s, intro_key="cheaper_intro")
        if new_concerns or ex["budget"]:  # a budget restated (even the same one) re-fits and re-shows the routine
            return _recommend(s)
        if intents & {"add_to_cart", "add_item"}:
            return _add_to_cart(s)
        # anything else after the routine: the AI answers from what it knows; rules give a helpful fallback
        back, qrs = _resume(s, awaiting)
        if not text:  # an old button from earlier in the chat
            return _reply(s, back, qrs=qrs, facts={"back_to": back})
        return _reply(s, t(L, "fallback", s.turns) + "\n\n" + back, qrs=qrs, kind="fallback",
                      facts={"routine": s.routine, "store": {k: v[L] for k, v in _faq().items()}, "back_to": back}, mode="answer")

    if "premium" in intents:
        s.premium = True
    if "cheaper" in intents:
        s.min_mode, s.premium = True, False
    if ex["budget"] and not s.routine and not new_concerns:
        nxt = _next(s)
        if nxt["kind"] == "text":
            nxt["text"] = t(L, "ack_budget", budget=fmt_aed(s.budget, L)) + " " + nxt["text"]
        return nxt
    asking = s.stage in ("ask_sensitivity", "ask_budget") or s.stage.startswith("ask_q:")
    if asking and text and not new_info and not ex["sensitivity"]:
        s.unanswered += 1
        if s.unanswered >= 2:  # don't loop on the same question: assume a sensible default and move on
            if s.stage == "ask_sensitivity":
                s.sensitivity = "none"
            elif s.stage.startswith("ask_q:"):
                s.answers[s.stage[6:]] = "skip"
            else:
                s.budget_asked = True
            nxt = _next(s)
            nxt["text"] = t(L, "move_on") + " " + nxt["text"]
            return nxt
    if new_concerns and not s.routine:
        rep = _next(s)
        if rep["kind"] == "text" and s.stage in ("ask_budget", "ask_sensitivity"):
            rep["text"] = t(L, "ack_concerns", s.turns, concerns=_labels(s)) + " " + rep["text"]
        return rep
    if not new_info and "question" in intents and s.stage not in ("ask_sensitivity", "ask_budget", "ask_more", "ask_concern"):
        # a general question before any routine
        return _reply(s, t(L, "fallback", s.turns), qrs=_area_qrs(s), kind="fallback",
                      facts={"store": {k: v[L] for k, v in _faq().items()}}, mode="answer")
    return _next(s)


def _next(s: Session) -> dict:
    L = s.lang
    before = s.stage
    out = _next_question(s)
    if s.stage != before:
        s.unanswered = 0
    return out


MID_CONSULTATION = ("ask_concern", "ask_more", "ask_sensitivity", "ask_budget", "ask_q:skin_type", "ask_q:sensitivity",
                    "ask_q:routine_size", "ask_q:hair_type", "ask_q:scalp", "ask_q:colour", "ask_q:supp_safety")


def _short(text: str, limit: int = 240) -> str:
    """First sentences of a usage text, up to about `limit` characters."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("。"), cut.rfind("؟"), cut.rfind("! "))
    return (cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "…").strip()


def _routine_how_to(s: Session) -> dict:
    """The whole routine as a plan: what to use in the morning, in the evening, weekly, then a line per product."""
    cat = get_catalog()
    L = s.lang
    # application order: thinnest first (toner, serum, eye, treatment), richest last (creams); wash before mask
    rank = {"toner": 0, "exfoliant": 1, "peel": 1, "serum": 2, "eye": 3, "brightening": 4, "day_cream": 5, "night_cream": 5,
            "moisturizer": 5, "shampoo_set": 0, "shampoo": 0, "mask": 1, "hair_mask": 1, "scalp": 2, "hair_serum": 3, "protein": 4}
    steps = sorted(s.routine["steps"], key=lambda st: rank.get(cat.get(st["id"])["step"], 6))
    groups: dict[str, list[str]] = {}
    for st in steps:
        slot = st["slot"]
        keys = [t(L, "how_morning"), t(L, "how_evening")] if slot == "AM & PM" else \
            [t(L, "how_morning")] if slot == "AM" else [t(L, "how_evening")] if slot == "PM" else [slot_label(L, slot)]
        for k in keys:
            groups.setdefault(k, []).append(st["name"])
    order = [t(L, "how_morning"), t(L, "how_evening")]
    plan = [f"**{k}:** " + t(L, "then_join").join(v) for k, v in sorted(groups.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 9)]
    details = [f"- {st['name']}: {_short(_how(cat.get(st['id']), L) or _sum(cat.get(st['id']), L))}" for st in steps]
    text = t(L, "routine_how_intro") + "\n" + "\n".join(plan) + "\n\n" + "\n".join(details)
    if s.cart:
        text += "\n\n" + t(L, "resume_checkout")
    return _reply(s, text, qrs=_post_qrs(s), kind="info", mode="rewrite",
                  facts={"routine": s.routine, "actions_done": [], "note": "Explain when to use each product; do not offer to add anything."})


def _resume(s: Session, awaiting: str) -> tuple[str, list[dict]]:
    """After a side question: the line (and buttons) that brings the customer back to where the chat was.
    Changes nothing, except keeping a pending offer ("Shall I add...?") open so a later "yes" still works."""
    cat = get_catalog()
    L = s.lang
    has_routine = bool(s.routine and s.routine.get("steps"))
    if awaiting == "add_routine" and has_routine and _routine_state(s) == "new":
        s.awaiting = awaiting
        return t(L, "resume_add_routine", total=fmt_aed(s.routine["total"], L)), _post_qrs(s)
    if awaiting == "add_product" and s.last_single and s.last_single in cat.by_id:
        s.awaiting = awaiting
        return t(L, "resume_add_product", product=cat.get(s.last_single)["name"]), _default_qrs(s)
    if awaiting == "checkout" and s.cart:
        s.awaiting = awaiting
        return t(L, "resume_checkout"), [_qr(s, "qr_checkout", "checkout"), _qr(s, "qr_cart", "cart_status")]
    if has_routine and _routine_state(s) == "new":
        return t(L, "resume_routine", s.turns, total=fmt_aed(s.routine["total"], L)), _post_qrs(s)
    if s.cart:
        return t(L, "resume_checkout"), [_qr(s, "qr_checkout", "checkout"), _qr(s, "qr_cart", "cart_status")]
    if s.orders:
        return t(L, "resume_after_order"), _area_qrs(s)
    q = _next_question(s, dry=True)  # the consultation question we were on
    if q:
        return q["text"], q["quick_replies"]
    if s.cart:
        return t(L, "resume_cart"), [_qr(s, "qr_checkout", "checkout"), _qr(s, "qr_cart", "cart_status")]
    return t(L, "ask_area", s.turns), _area_qrs(s)


def _next_question(s: Session, dry: bool = False) -> dict | None:
    """The next consultation question, or the routine when everything is known.
    dry=True: only the question (None instead of building a routine)."""
    out = _next_question_inner(s, dry)
    if out and out["kind"] == "text" and not out["cards"]:
        out["_question"] = out["text"]  # the AI may add a reaction, but the question itself is never reworded
    return out


def _next_question_inner(s: Session, dry: bool = False) -> dict | None:
    L = s.lang
    if not s.area:
        s.stage = "ask_area"
        return _reply(s, t(L, "ask_area", s.turns), qrs=_area_qrs(s))
    if not s.concerns:
        s.stage = "ask_concern"
        return _reply(s, t(L, f"ask_concern_{s.area}", s.turns), qrs=_concern_qrs(s, s.area, []))
    if not s.concerns_done:
        s.stage = "ask_more"
        return _reply(s, t(L, "ask_more", s.turns, concerns=_labels(s)),
                      qrs=[_qr(s, "qr_done", "concerns_done")] + _concern_qrs(s, s.area, s.concerns))
    # profile questions: only those whose answer changes the products (see engine/questions.py)
    Q.note_known(s)
    q = Q.next_question(s, get_catalog())
    if q:
        s.stage = f"ask_q:{q.key}"
        return _reply(s, t(L, f"q_{q.key}", s.turns),
                      qrs=[{"label": t(L, f"qo_{q.key}_{o.value}"), "action": f"q:{q.key}:{o.value}"} for o in q.options])
    if s.area == "skin" and s.fast_path and s.budget is None and not s.budget_asked and not s.min_mode:
        s.stage = "ask_budget"
        return _reply(s, t(L, "ask_budget", s.turns), qrs=[_qr(s, k, f"budget:{v}") for k, v in BUDGET_CHIPS])
    if s.area != "supplement" and not s.fast_path:
        if s.budget is None and not s.budget_asked and not s.min_mode:
            s.stage = "ask_budget"
            return _reply(s, t(L, "ask_budget", s.turns), qrs=[_qr(s, k, f"budget:{v}") for k, v in BUDGET_CHIPS])
    if dry:
        return None
    return _recommend(s)


def _recommend(s: Session, intro_key: str = "routine_intro", lead_key: str | None = None, lead_kw: dict | None = None) -> dict:
    cat = get_catalog()
    premium = s.premium and s.area == "skin"
    # an explicit premium request shows the full luxury routine; the budget is mentioned, not enforced
    budget = None if premium else s.budget
    if s.min_mode and not premium:
        # one product: the one that covers the most of their concerns, then the cheapest
        full = build(cat, s.area, s.concerns, None, exclude=s.excluded)
        pick = min(full.steps, key=lambda st: (-len(st.covers), st.product["price_aed"]), default=None)
        if pick:
            budget = min(budget, pick.product["price_aed"]) if budget else pick.product["price_aed"]
            s.excluded_min = [st.product["id"] for st in full.steps if st is not pick and st.product["price_aed"] <= budget]
    before = {x["id"] for x in (s.routine or {}).get("steps", [])}
    sens_out = [p["id"] for p in cat.products if p["step"] in ("exfoliant", "peel")] \
        if s.area == "skin" and s.sensitivity == "sensitive" else []
    r = build(cat, s.area, s.concerns, budget, premium=premium, exclude=s.excluded + getattr(s, "excluded_min", []) + sens_out,
              fill=s.fill, essentials=s.essentials and not s.fill)
    if sens_out:
        would = build(cat, s.area, s.concerns, budget, premium=premium, exclude=s.excluded)
        sens_out = [st.product["name"] for st in would.steps + would.addons if st.product["id"] in sens_out]
    s.excluded_min = []
    s.routine = r.to_dict()
    s.stage = "recommended"
    L = s.lang
    if lead_key and not r.steps:  # they took out the last product
        s.awaiting, s.routine = "", None
        return _reply(s, t(L, "routine_empty", product=(lead_kw or {}).get("product", "")),
                      qrs=[_qr(s, "qr_restart", "restart")] + _area_qrs(s)[:0], kind="text",
                      facts={"actions_done": [f"routine updated: removed {(lead_kw or {}).get('product', '')}"]})
    if lead_key:
        parts = [t(L, lead_key, s.turns, total=fmt_aed(r.total, L), **(lead_kw or {}))]
    else:
        if not r.steps:  # nothing in the range matches what they asked for: say so plainly
            s.awaiting, s.routine, s.stage = "", None, "no_match"
            return _reply(s, t(L, "nothing_matches", concerns=_concern_list(s, r.uncovered or s.concerns)),
                          qrs=[_qr(s, "qr_human", "human"), _qr(s, "qr_restart", "restart")], kind="text",
                          facts={"no_product_for": r.uncovered or s.concerns, "actions_done": []})
        if intro_key == "fill_intro":
            added = [st.product["name"] for st in r.steps if st.product["id"] not in before]
            parts = [t(L, "fill_intro" if added else "fill_nothing", added=join_list(L, added))]
        elif premium and r.tier != "premium":
            parts = [t(L, "premium_none", concerns=_labels(s))]
        else:
            parts = [t(L, intro_key, s.turns, concerns=_labels(s))]
        if premium and r.tier == "premium":
            parts.append(t(L, "routine_total", total=fmt_aed(r.total, L)))
            if s.budget and r.total > s.budget:
                parts.append(t(L, "premium_over_budget", budget=fmt_aed(s.budget, L)))
        elif r.over_budget_minimum:
            parts.append(t(L, "over_budget_minimum", product=r.steps[0].product["name"], total=fmt_aed(r.total, L),
                           budget=fmt_aed(r.budget, L)))
        elif s.min_mode and not s.budget:
            parts.append(t(L, "min_mode_pick", product=r.steps[0].product["name"], total=fmt_aed(r.total, L)))
        elif r.dropped:
            parts.append(t(L, "routine_dropped", full_total=fmt_aed(r.full_total, L), budget=fmt_aed(r.budget, L),
                           dropped=join_list(L, [st.product["name"] for st in r.dropped])))
            parts.append(t(L, "routine_total", total=fmt_aed(r.total, L)))
        else:
            parts.append(t(L, "routine_total", total=fmt_aed(r.total, L)))
            if r.budget:
                parts.append(t(L, "routine_within", budget=fmt_aed(r.budget, L)))
        for a in r.addons:
            if a.note == "alternative":
                parts.append(t(L, "alt_note", product=a.product["name"], concerns=_concern_list(s, a.covers)))
            elif a.note == "alternate_wash":
                parts.append(t(L, "alt_wash_note", product=a.product["name"], concerns=_concern_list(s, a.covers)))
        if any(a.note not in ("alternative", "alternate_wash") for a in r.addons):
            parts.append(t(L, "addons_intro"))
        if r.uncovered:
            parts.append(t(L, "no_product_for", concerns=_concern_list(s, r.uncovered)))
        for tip in r.tips:
            parts.append(t(L, tip))
        if sens_out:
            parts.append(t(L, "sens_left_out", products=join_list(L, sens_out)))
        if s.essentials and r.addons and not s.fill:
            parts.append(t(L, "essentials_note"))
        if s.sensitivity == "sensitive" and s.area in ("skin", "hair"):
            parts.append(t(L, "sensitive_note", area_word=t(L, f"area_word_{s.area}")))
    parts.append(t(L, "cta", s.turns))
    s.awaiting = "add_routine"
    return _reply(s, " ".join(parts), cards=[{"type": "routine", "routine": _localize_routine(s.routine, L)}],
                  qrs=_post_qrs(s), event="recommended", kind="routine",
                  facts={"routine": s.routine, "optional_extras": [f"{a['name']} (AED {a['price_aed']:.0f})" for a in s.routine["addons"]],
                         "why_each_product": {x["name"]: [cat.concern_label(s.area, c, "en") for c in x["covers"]] for x in s.routine["steps"]},
                         "no_product_in_range_for": [cat.concern_label(s.area, c, "en") for c in r.uncovered],
                         "actions_done": [f"routine updated: removed {lead_kw['product']}"] if lead_key == "removed" and lead_kw else [],
                         "note": "The routine is only a suggestion shown on screen; nothing has been added to the cart."})


def _unsupported_reply(s: Session, needs: list[str]) -> dict:
    """'Do you have sunscreen?' -> we don't, plainly; a labelled alternative only when a real product fits."""
    from app.providers.rule import _unsupported
    L, cat = s.lang, get_catalog()
    info = _unsupported()
    parts = [t(L, "unsupported_need", need=join_list(L, [info[n][L] for n in needs]))]
    cards = []
    for n in needs:
        alt = info[n].get("alternative")
        if alt and alt in cat.by_id:
            p = cat.get(alt)
            parts.append(info[n][f"alt_{L}"].format(product=p["name"]))
            cards.append({"type": "product", "product": _pcard(p)})
            s.awaiting = "add_product"
    if any(info[n].get("team") for n in needs):
        parts.append(t(L, "unsupported_team"))
    nxt_q = t(L, "unsupported_next") if not s.routine else ""
    if nxt_q:
        parts.append(nxt_q)
    qrs = ([_qr(s, "qr_human", "human")] if any(info[n].get("team") for n in needs) else []) + _default_qrs(s)
    return _reply(s, " ".join(parts), cards=cards[:1], qrs=qrs, kind="unsupported",
                  facts={"not_in_range": [info[n]["en"] for n in needs], "actions_done": []})


def _concern_list(s: Session, concerns: list[str]) -> str:
    cat = get_catalog()
    labels = [cat.concern_label(s.area, c, s.lang) for c in concerns]
    return join_list(s.lang, [x.lower() if s.lang == "en" else x for x in labels])


def _localize_routine(rd: dict, lang: str) -> dict:
    """Slot names, 'for: <concern>' labels and the extra/alternative note in the customer's language."""
    cat = get_catalog()
    out = dict(rd)
    for key in ("steps", "dropped", "addons"):
        out[key] = [{**st, "slot_label": slot_label(lang, st["slot"]),
                     "for_labels": [cat.concern_label(rd["area"], c, lang) for c in st.get("covers") or []],
                     "note_label": t(lang, f"note_{st['note']}") if st.get("note") else ""} for st in rd[key]]
    return out


def _routine_state(s: Session) -> str:
    """'new' (not in the cart yet), 'in_cart' or 'ordered': decides whether "Add routine to cart" still makes sense."""
    ids = {x["id"] for x in (s.routine or {}).get("steps", [])}
    if not ids:
        return "new"
    if ids <= {c.get("id") for c in s.cart}:
        return "in_cart"
    if ids <= {i for o in s.orders for i in o.get("ids", [])}:
        return "ordered"
    return "new"


def _post_qrs(s: Session) -> list[dict]:
    state = _routine_state(s)
    if state == "in_cart":
        q = [_qr(s, "qr_checkout", "checkout")]
    elif state == "ordered":
        q = [{"label": t(s.lang, "qr_where_order"), "action": "say:" + t(s.lang, "qr_where_order")}]
    else:
        q = [_qr(s, "qr_add", "add_routine")]
    if state != "new":  # already in the cart or ordered: no upsell buttons
        return q + [_qr(s, "qr_how", "how_to_use"), _qr(s, "qr_restart", "restart")]
    if s.area == "skin":
        q.append(_qr(s, "qr_cheaper", "cheaper") if s.premium else _qr(s, "qr_premium", "premium"))
    elif s.area == "hair" and s.routine and s.routine.get("addons") and not s.fill:
        q.append(_qr(s, "qr_fill", "premium"))
    q += [_qr(s, "qr_how", "how_to_use"), _qr(s, "qr_restart", "restart")]
    return q


def _search(s: Session, srch: dict) -> tuple[list[dict], dict]:
    from app.providers.rule import extract_search
    cat = get_catalog()
    steps = set(srch.get("steps") or [])
    if srch.get("type"):
        steps |= set(extract_search(srch["type"])["steps"])
    flt = {"steps": sorted(steps), "lines": srch.get("lines") or [], "category": srch.get("category"),
           "area": srch.get("area"), "max_price": srch.get("max_price")}
    if not any(flt.values()):
        if not s.area:
            return [], flt
        flt["area"] = s.area
    items = cat.products
    if flt["steps"]:
        items = [p for p in items if p["step"] in flt["steps"]]
    if flt["lines"]:
        items = [p for p in items if p["line"] in flt["lines"]]
    if flt["category"]:
        items = [p for p in items if p["category"] == flt["category"]]
    if flt["area"]:
        items = [p for p in items if p["area"] == flt["area"] or (flt["area"] == "hair" and p["category"] == "anti-hair-loss")]
    if flt["max_price"]:
        items = [p for p in items if p["price_aed"] <= flt["max_price"]]
    return sorted(items, key=lambda p: p["price_aed"])[:6], flt


def _cart_status(s: Session) -> dict:
    L = s.lang
    if not s.cart:
        return _reply(s, t(L, "cart_empty"), qrs=_default_qrs(s), kind="cart_status")
    count = sum(int(i.get("qty", 1)) for i in s.cart)
    total = sum(float(i.get("price_aed", 0)) * int(i.get("qty", 1)) for i in s.cart)
    items = join_list(L, [f"{i.get('name')}" + (f" x{i.get('qty')}" if int(i.get("qty", 1)) > 1 else "") for i in s.cart])
    s.awaiting = "checkout"
    return _reply(s, t(L, "cart_status", count=count, items=items, total=fmt_aed(total, L)), qrs=_cart_qrs(s),
                  kind="cart_status", facts={"cart_total_aed": total})


def _in_cart(s: Session) -> set[str]:
    return {x.get("id") for x in s.cart}


def _switch_language(s: Session) -> dict:
    """Carry on in the new language: confirm, then repeat where we are (question, routine or cart) in that language."""
    L = s.lang
    if s.stage.startswith("ask_"):  # mid-question: ask the same question again, now in the new language
        nxt = _next(s)
        nxt["text"] = t(L, "lang_switched") + " " + nxt["text"]
        return nxt
    if s.routine:  # no need to repeat the whole routine card: offer it, plus the usual next steps
        qrs = [_qr(s, "qr_recap", "recap")] + (_cart_qrs(s) if s.cart else _post_qrs(s))
        return _reply(s, t(L, "lang_switched") + " " + t(L, "lang_what_next"), qrs=qrs, kind="text", ai=False)
    s.stage = "ask_area"
    return _reply(s, t(L, "lang_switched") + " " + t(L, "ask_area", s.turns), qrs=_area_qrs(s), kind="text", ai=False)


def _cart_total(s: Session) -> float:
    return sum(float(x.get("price_aed", 0)) * int(x.get("qty", 1)) for x in s.cart)


def _cart_qrs(s: Session) -> list[dict]:
    return [_qr(s, "qr_checkout", "checkout"), _qr(s, "qr_cart", "cart_status"), _qr(s, "qr_continue", "continue")]


def _add_to_cart(s: Session) -> dict:
    cat = get_catalog()
    return _add_items(s, [cat.get(st["id"]) for st in s.routine["steps"]], routine=True)


def _add_items(s: Session, products: list[dict], routine: bool = False) -> dict:
    """Add products to the cart: never twice, say exactly what changed, and offer to check out."""
    L = s.lang
    in_cart = _in_cart(s)
    new = [p for p in products if p["id"] not in in_cart]
    already = [p for p in products if p["id"] in in_cart]
    s.awaiting = "checkout"
    if not new:
        names = join_list(L, [p["name"] for p in already])
        return _reply(s, t(L, "already_in_cart", items=names, total=fmt_aed(_cart_total(s), L)), qrs=_cart_qrs(s), kind="cart",
                      facts={"actions_done": [], "cart_total_now_aed": _cart_total(s)})
    items = [{"id": p["id"], "name": p["name"], "price_aed": p["price_aed"]} for p in new]
    added_total = sum(i["price_aed"] for i in items)
    cart_total = _cart_total(s) + added_total
    s.cart_value += added_total
    if routine:
        s.stage = "added"
    parts = [t(L, "added", s.turns, items=join_list(L, [i["name"] for i in items]), total=fmt_aed(added_total, L))]
    if already:
        parts.append(t(L, "was_already", items=join_list(L, [p["name"] for p in already])))
    if s.budget and cart_total > s.budget:
        parts.append(t(L, "item_over_budget", total=fmt_aed(cart_total, L), budget=fmt_aed(s.budget, L)))
    parts.append(t(L, "checkout_q", s.turns))
    return _reply(s, " ".join(parts), cards=[{"type": "cart_add", "items": items, "total": added_total}], qrs=_cart_qrs(s),
                  event="cart_add", kind="cart",
                  facts={"actions_done": [f"added to cart: {i['name']} (AED {i['price_aed']:.0f})" for i in items],
                         "already_in_cart_before": [p["name"] for p in already], "cart_total_now_aed": cart_total})


def _checkout(s: Session) -> dict:
    L = s.lang
    if not s.cart:
        if s.orders:
            return _order_status(s)
        return _reply(s, t(L, "checkout_empty"), qrs=_default_qrs(s), kind="cart", facts={"actions_done": []})
    items = join_list(L, [f"{x.get('name')}" + (f" x{x.get('qty')}" if int(x.get("qty", 1)) > 1 else "") for x in s.cart])
    total = _cart_total(s)
    s.awaiting = "checkout_form"
    return _reply(s, t(L, "checkout_intro", items=items, total=fmt_aed(total, L)),
                  cards=[{"type": "checkout", "items": s.cart, "total": total}], qrs=[], kind="checkout",
                  facts={"actions_done": [], "note": "The order is NOT placed yet; the customer must fill in the form and confirm."})


def _order_status(s: Session) -> dict:
    L = s.lang
    o = s.orders[-1]
    return _reply(s, t(L, "order_status_known", id=o["id"], items=join_list(L, o["items"]), total=fmt_aed(o["total"], L),
                       phone=_mask(o.get("phone", ""))), qrs=_default_qrs(s), kind="order", facts={"order": o, "actions_done": []})


def _order_cancel(s: Session) -> dict:
    L = s.lang
    o = s.orders[-1]
    s.handoff, s.handoff_topic = True, "order_cancel"
    return _reply(s, t(L, "order_cancel_sent", id=o["id"], phone=_mask(o.get("phone", ""))), qrs=_default_qrs(s),
                  kind="order", event="handoff",
                  facts={"actions_done": [f"cancellation or change request for order #{o['id']} sent to Dr. Shaymaa's team"]})


def _mask(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"…{digits[-4:]}" if len(digits) >= 4 else phone


def _history_reply(s: Session) -> dict:
    L = s.lang
    talked = [h for h in s.history if h["role"] == "user"]
    if not talked and not s.orders and not s.cart:
        return _reply(s, t(L, "history_none"), qrs=_area_qrs(s), kind="text", facts={"actions_done": []})
    cat = get_catalog()
    bits = []
    if s.area and s.concerns:
        bits.append(t(L, "hist_topic", area=t(L, f"qr_{s.area}").lower() if L == "en" else t(L, f"qr_{s.area}"), concerns=_labels(s)))
    if s.routine:
        bits.append(t(L, "hist_routine", items=join_list(L, [x["name"] for x in s.routine["steps"]]), total=fmt_aed(s.routine["total"], L)))
    if s.cart:
        bits.append(t(L, "hist_cart", items=join_list(L, [x.get("name") for x in s.cart]), total=fmt_aed(_cart_total(s), L)))
    if s.orders:
        o = s.orders[-1]
        bits.append(t(L, "hist_order", id=o["id"], total=fmt_aed(o["total"], L)))
    name_part = f", {s.name}" if s.name else ""
    return _reply(s, t(L, "history_summary", name_part=name_part, details=" ".join(bits) or t(L, "hist_little")),
                  qrs=_default_qrs(s), kind="text", facts={"actions_done": [], "customer_known": _profile(s)})


def _cart_edit(s: Session, op: str, mentioned: list[dict]) -> dict:
    L = s.lang
    if not s.cart:
        return _reply(s, t(L, "cart_nothing"), qrs=_default_qrs(s), kind="cart", facts={"actions_done": []})
    if op == "cart_clear":
        names = [x.get("name") for x in s.cart]
        return _reply(s, t(L, "cart_cleared", s.turns), cards=[{"type": "cart_clear"}], qrs=_default_qrs(s), kind="cart",
                      facts={"actions_done": [f"removed from cart: {n}" for n in names] + ["the cart is now empty"]})
    ids = _in_cart(s)
    targets = [p for p in mentioned if p["id"] in ids]
    if not targets and len(s.cart) == 1:
        targets = [get_catalog().get(s.cart[0]["id"])] if s.cart[0].get("id") in get_catalog().by_id else []
    if not targets:
        qrs = [{"label": f"{t(L, 'qr_remove')} {x.get('name')}", "action": f"cart_remove:{x.get('id')}"} for x in s.cart[:4]]
        qrs.append(_qr(s, "qr_clear_cart", "cart_clear"))
        return _reply(s, t(L, "cart_remove_which"), qrs=qrs, kind="cart", facts={"actions_done": [], "cart": s.cart})
    left = sum(float(x.get("price_aed", 0)) * int(x.get("qty", 1)) for x in s.cart if x.get("id") not in {p["id"] for p in targets})
    return _reply(s, t(L, "cart_removed", s.turns, product=join_list(L, [p["name"] for p in targets]), total=fmt_aed(left, L)),
                  cards=[{"type": "cart_remove", "ids": [p["id"] for p in targets]}], qrs=_default_qrs(s), kind="cart",
                  facts={"actions_done": [f"removed from cart: {p['name']}" for p in targets], "cart_total_now_aed": left})


def _mentions_list(text: str) -> bool:
    from app.engine.text import find_terms
    return bool(find_terms(text, ["first", "second", "third", "last one", "these", "those", "both", "الاول", "الثاني", "هذول"]))


def _merge(first: dict, second: dict) -> dict:
    """One reply that does two things (e.g. empty the cart, then show the fitted suggestion)."""
    out = dict(second)
    out["text"] = f"{first['text']} {second['text']}"
    out["cards"] = first["cards"] + second["cards"]
    out["_facts"] = {**second["_facts"], "actions_done": first["_facts"].get("actions_done", []) + second["_facts"].get("actions_done", [])}
    return out


def _add_item(s: Session, p: dict) -> dict:
    return _add_items(s, [p])


def _caution(s: Session, p: dict) -> dict:
    s.awaiting = "handoff"
    return _reply(s, t(s.lang, "product_caution", product=p["name"]), cards=[{"type": "product", "product": _pcard(p)}],
                  qrs=[_qr(s, "qr_handoff", "handoff_request"), _qr(s, "qr_continue", "continue")], kind="caution", ai=False)


def _handoff(s: Session, category: str) -> dict:
    s.handoff, s.handoff_topic = True, category
    topic = t(s.lang, f"handoff_topic_{category}") if category else t(s.lang, "handoff_topic_condition")
    # fixed wording on purpose: safety messages are never re-worded by the AI
    return _reply(s, t(s.lang, "handoff", topic=topic), cards=[{"type": "handoff", "category": category}],
                  qrs=[_qr(s, "qr_continue", "continue")], event="handoff", kind="handoff", ai=False)


def _human(s: Session) -> dict:
    s.handoff, s.handoff_topic = True, "request"
    return _reply(s, t(s.lang, "handoff_request"), cards=[{"type": "handoff", "category": "request"}],
                  qrs=[_qr(s, "qr_continue", "continue")], event="handoff", kind="handoff", ai=False)


def _apply_action(s: Session, action: str) -> None:
    kind, _, val = action.partition(":")
    if kind == "area" and val in AREA_CHIPS:
        if s.area != val:
            s.concerns, s.concerns_done, s.routine, s.premium, s.excluded = [], False, None, False, []
        s.area = val
    elif kind == "concern" and s.area:
        if val not in s.concerns:
            s.concerns.append(val)
        s.concerns_done = len(s.concerns) >= 3
    elif kind == "concerns_done":
        s.concerns_done = True
    elif kind == "sens":
        s.sensitivity = "sensitive" if val == "sensitive" else "none"
    elif kind == "q":
        key, _, value = val.partition(":")
        if key in Q.BY_KEY and any(o.value == value for o in Q.BY_KEY[key].options):
            Q.apply(s, Q.BY_KEY[key], value)
    elif kind == "budget":
        s.budget_asked = True
        s.budget = None if val == "none" else int(val)


def _reset(s: Session) -> None:
    """Start the consultation again but keep who the customer is and the conversation so far."""
    keep = {k: getattr(s, k) for k in ("id", "lang", "turns", "cart_value", "handoff", "handoff_topic", "name", "history", "cart")}
    fresh = Session(id=s.id)
    for k in fresh.__dataclass_fields__:
        setattr(s, k, getattr(fresh, k))
    for k, v in keep.items():
        setattr(s, k, v)


PRODUCT_WORDS = {  # word in the product name -> words a customer may use for it (EN + AR, normalised)
    "eye": ["eye", "عين", "العين"], "mask": ["mask", "ماسك", "قناع"], "serum": ["serum", "سيروم"],
    "shampoo": ["shampoo", "wash", "شامبو"], "conditioner": ["conditioner", "بلسم"], "toner": ["toner", "تونر"],
    "lotion": ["lotion", "لوشن"], "exfoliant": ["exfoliant", "scrub", "مقشر"], "elixir": ["elixir", "اكسير"],
    "botox": ["botox", "بوتوكس"], "vitamins": ["vitamin", "gumm", "فيتامين"], "day cream": ["day cream", "كريم النهار"],
    "night cream": ["night cream", "كريم الليل"], "cream": ["cream", "كريم"], "oil": ["oil", "زيت"],
    "moisturizer": ["moisturi", "مرطب"], "brightening": ["brighten", "whiten", "تفتيح"],
}


def _routine_product(routine: dict, text: str) -> dict | None:
    """The routine product a message refers to by its type ("the mask", "السيروم"); most specific match wins."""
    from app.engine.text import find_terms
    cat = get_catalog()
    best, best_score = None, 0
    for st in routine["steps"] + routine["addons"] + routine["dropped"]:
        name = st["name"].lower()
        score = sum(len(key) for key, words in PRODUCT_WORDS.items() if key in name and find_terms(text, words))
        if score > best_score:
            best, best_score = cat.get(st["id"]), score
    return best


def _pcard(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "name", "line", "price_aed", "summary", "summary_ar", "how_to_use", "category",
                                  "caution", "handoff", "size", "origin", "time", "image", "concerns")}


def _pfacts(p: dict) -> dict:
    return {k: p[k] for k in ("name", "line", "price_aed", "summary", "how_to_use", "size", "origin")}
