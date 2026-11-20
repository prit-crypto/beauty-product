"""Shared logic for LLM providers (Gemini, OpenAI). Subclasses implement _complete() only.

Two calls per customer message:
  extract()  reads the message WITH the recent conversation -> structured fields (what to do)
  phrase()   writes the assistant's reply in a natural, human voice from the engine's facts (what to say)
The engine in between decides products, prices and safety; the AI never does.
"""
import json
import re
from functools import lru_cache

from app.engine.catalog import get_catalog
from app.engine.text import normalize
from app.providers.base import INTENTS

LANG_NAME = {"en": "English", "ar": "Arabic (warm, simple Gulf-friendly Modern Standard Arabic; address the customer in the feminine)"}
FAQ_TOPICS = ["payment", "shipping", "returns", "order_status", "offers", "founder", "origin"]
CATEGORIES = ["skincare", "haircare", "protein", "supplements", "anti-hair-loss"]

PERSONA = (
    "You are the beauty advisor of Dr. Beauty Care, a UAE skincare, haircare and supplements brand founded by "
    "Dr. Shaymaa Abdel Nabi. You talk like a warm, knowledgeable human consultant in a boutique: friendly, calm, "
    "concise and genuinely helpful, never robotic or salesy. Make the conversation engaging: react to what the customer "
    "actually said (their words, feelings, routine, earlier messages), add one small useful insight or tip where it fits "
    "(only from FACTS), and end with one easy, specific question or next step. Vary your openings; don't start every "
    "message the same way. "
)
RULES = (
    "Rules: (1) Only mention products, prices and facts that appear in FACTS or DRAFT; write prices like 'AED 150' "
    "(Arabic: '150 درهم'); never invent products, prices, ingredients, delivery times or results. (2) Never give medical "
    "advice or diagnoses, and never use the words cure, treat, heal, guarantee, permanent, 'stops hair loss' or whitening "
    "(say brightening). (3) You are the shop's advisor, not Dr. Shaymaa and not a doctor. (4) Don't say hello again "
    "mid-conversation; use the customer's name now and then if known, not every message. (5) The product cards shown "
    "under your message already list items and prices, so don't repeat every detail; mention the key one or two. "
    "(6) Never mention 'facts', 'draft', 'data' or 'the system'. (7) Keep it short: 2 to 4 sentences (at most 90 words), "
    "plain text; a short '- ' list only if it really helps. (8) Keep any question the DRAFT asks, so the conversation "
    "moves forward. (9) ACTIONS: FACTS.actions_done lists the only things that actually happened this turn (cart or routine "
    "changes). Never say you added, removed, cleared, changed, corrected, ordered or placed anything that is not in "
    "actions_done; if it is empty, nothing was done, so you may only offer or ask. Never promise to do something the DRAFT "
    "does not offer. (10) Never suggest a product, price or routine that is not in FACTS or DRAFT, and never go above the "
    "customer's budget on your own. Never state where a product is made, what it contains or what it does unless FACTS "
    "says so. (11) Stay on Dr. Beauty Care topics (its skincare, haircare, supplements, orders); "
    "politely decline anything else, and never recommend other brands or home remedies. (12) If the customer is unhappy, "
    "apologise once, briefly, then say plainly what is now on screen. (13) If the DRAFT has a '- ' list, keep every "
    "item as a '- ' list line (you may shorten the wording); the list doesn't count toward the length limit. (14) If the "
    "customer goes off topic or asks something else mid-way, answer or decline that briefly, then bring them back to "
    "FACTS.back_to (the question or offer that was pending) so they never lose their place."
)


@lru_cache(maxsize=1)
def _catalog_lines() -> str:
    cat = get_catalog()
    return "\n".join(f"{p['id']} | {p['name']} | {p['line']} | AED {p['price_aed']:.0f}" for p in cat.products)


def _history_text(history: list[dict] | None, limit: int = 30) -> str:
    if not history:
        return "(start of conversation)"
    lines = []
    for h in history[-limit:]:
        who = "Customer" if h["role"] == "user" else "Advisor"
        lines.append(f"{who}: {h['text'][:400]}")
    return "\n".join(lines)


class LLMProvider:
    name = "llm"

    def _complete(self, system: str, user: str, json_mode: bool) -> str:  # pragma: no cover - network
        raise NotImplementedError

    # ---- extract (understanding, with conversation memory)
    def extract(self, text: str, lang: str, context: dict) -> dict:
        cat = get_catalog()
        allowed = {a: list(cs.keys()) for a, cs in cat.concerns.items()}
        system = (
            "You read a beauty shop customer's latest chat message (English or Arabic, any dialect) in the context of the "
            "conversation and return ONLY a JSON object with these keys:\n"
            "area: skin | hair | supplement | null (the topic of THIS message; null if unchanged or unclear)\n"
            f"concerns: array of objects {{\"concern\": one of the allowed values, \"words\": the customer's exact words in the "
            f"LATEST MESSAGE that state it}}; allowed per area: {json.dumps(allowed)}. Only concerns the customer actually states "
            f"in the LATEST MESSAGE; never infer one from budget, premium or shopping words, and never repeat earlier ones\n"
            "budget_aed: integer or null (only if the customer states a budget for a routine)\n"
            "sensitivity: 'sensitive' | 'none' | null\n"
            f"intents: array from {INTENTS}\n"
            "product_ids: array of catalogue ids the customer refers to, including references like 'it', 'that one', "
            "'the first one', 'the mask' resolved using the conversation and LAST SHOWN; [] if none\n"
            "customer_name: the customer's first name if they tell it, else null\n"
            f"faq_topic: one of {FAQ_TOPICS} if they ask about payment, delivery, returns, order tracking, offers, the founder "
            "or where products come from; else null\n"
            f"search: {{\"category\": one of {CATEGORIES} or null, \"type\": a product type word like shampoo, mask, serum, "
            "cream, toner, supplement or null, \"max_price_aed\": integer or null}} when they want to browse products\n"
            "medical: true if the message mentions pregnancy, breastfeeding, any medication or treatment by a doctor, an "
            "allergy, a medical or skin condition or disease, a child as the user, or asks for medical advice; ordinary "
            "beauty concerns (wrinkles, dull skin, frizz, dandruff, dry hair) are NOT medical.\n"
            "Intent guide: add_to_cart = put the suggested routine (or the product just discussed) in the cart; add_item = "
            "add one specific product; remove_item = take a product out of the routine; recap = repeat what was suggested; "
            "compare = compare products; search = browse products; cart_status = what is in the cart; cart_remove = take a "
            "product out of the CART; cart_clear = empty the cart / revert or cancel the order; human = wants a person; bye; "
            "thanks; greeting; restart; premium = explicitly wants the luxury Cana Gold line; cheaper = wants a lower price, "
            "the cheapest option, or says something is over budget; how_to_use; claim_question = asks for cures or guaranteed "
            "results; off_topic = unrelated to beauty, this shop or its orders (weather, sport, news, coding, poems...); affirm = yes/ok/sure answering the advisor's last "
            "question; deny = no/not now; checkout = wants to place or confirm the order / pay; history = asks what you remember "
            "or about earlier chats or past orders; order_cancel = wants to cancel or change an order already placed; capabilities = asks what you can do, how you can help "
            "or who you are; "
            "question = any other question.\n"
            "only: true if the customer wants ONLY the specific product(s) they refer to (e.g. 'add only that one').\n"
            "Use null/empty when not stated. Do not guess."
        )
        last = ", ".join(f"{i + 1}. {pid}" for i, pid in enumerate(context.get("last_products") or [])) or "(none)"
        user = (f"CATALOGUE (id | name | line | price):\n{_catalog_lines()}\n\n"
                f"CONVERSATION SO FAR:\n{_history_text(context.get('history'))}\n\n"
                f"LAST LIST shown (in order): {last}\nLAST PRODUCT discussed: {context.get('last_single') or '(none)'}\nStage: {context.get('stage')}. Current topic: {context.get('area')}.\n\n"
                f"LATEST MESSAGE: {text}")
        data = json.loads(_strip_fence(self._complete(system, user, json_mode=True)))
        area = data.get("area") if data.get("area") in allowed else None
        use_area = area or context.get("area")
        # a concern is kept only if the AI quotes words that really are in the message (no invented concerns)
        msg = normalize(text)
        concerns = []
        for item in data.get("concerns") or []:
            if isinstance(item, dict):
                c, words = item.get("concern"), normalize(str(item.get("words") or ""))
                if use_area and c in allowed.get(use_area, []) and len(words) >= 3 and words in msg:
                    concerns.append(c)
        budget = data.get("budget_aed")
        budget = int(budget) if isinstance(budget, (int, float)) and 50 <= budget <= 100000 else None
        sens = data.get("sensitivity") if data.get("sensitivity") in ("sensitive", "none") else None
        intents = [i for i in (data.get("intents") or []) if i in INTENTS]
        pids = [p for p in (data.get("product_ids") or []) if isinstance(p, str) and p in cat.by_id]
        name = data.get("customer_name")
        name = name.strip()[:30] if isinstance(name, str) and 1 < len(name.strip()) <= 30 else None
        faq = data.get("faq_topic") if data.get("faq_topic") in FAQ_TOPICS else None
        srch = data.get("search") if isinstance(data.get("search"), dict) else {}
        search = {"category": srch.get("category") if srch.get("category") in CATEGORIES else None,
                  "type": srch.get("type") if isinstance(srch.get("type"), str) else None,
                  "max_price": int(srch["max_price_aed"]) if isinstance(srch.get("max_price_aed"), (int, float)) else None}
        return {"area": area, "concerns": concerns, "budget": budget, "sensitivity": sens, "intents": intents,
                "products": pids, "name": name, "faq": faq, "search": search, "medical": data.get("medical") is True,
                "only": data.get("only") is True}

    # ---- safety (kept for compatibility; the medical flag now comes with extract())
    def classify_safety(self, text: str) -> bool | None:
        return None

    # ---- phrase (the reply, in a human voice)
    def phrase(self, lang: str, draft: str, facts: dict, mode: str = "rewrite", history=None) -> str | None:
        if mode == "react":
            task = ("Write ONE short, warm sentence (max 25 words) reacting to the customer's latest message, the way a "
                    "friendly advisor acknowledges what they just said. Use the DRAFT's facts if it has any. No question, "
                    "no product names, no prices, no promises. ")
        elif mode == "answer":
            task = ("Answer the customer's latest message using ONLY the FACTS and the conversation. If they don't contain "
                    "the answer, say honestly you're not sure, share the closest helpful detail, and offer to pass the "
                    "question to Dr. Shaymaa's team. ")
        else:
            task = ("Write your next message to the customer. The DRAFT says what to communicate: keep its decisions, "
                    "product names, prices and any question it asks, but say it the way a friendly human advisor would, "
                    "connecting naturally to what was said before. ")
        system = PERSONA + task + f"Reply in {LANG_NAME.get(lang, 'English')}. " + RULES
        user = (f"CONVERSATION SO FAR:\n{_history_text(history)}\n\n"
                f"DRAFT:\n{draft}\n\nFACTS (JSON):\n{json.dumps(facts, ensure_ascii=False)[:6000]}")
        out = self._complete(system, user, json_mode=False).strip()
        return out or None


def _strip_fence(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    return m.group(1) if m else s
