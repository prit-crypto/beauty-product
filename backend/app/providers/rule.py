"""Static, rule-based provider. No API key, no network, fully predictable. Always available as the fallback."""
import json
import re
from functools import lru_cache

from app.config import DATA_DIR
from app.engine import claims
from app.engine.catalog import get_catalog
from app.engine.text import find_terms, normalize, parse_budget

INTENT_TERMS = {
    "restart": (["start over", "restart", "reset", "begin again", "new routine", "new chat"], ["من جديد", "ابدا من جديد", "ابدئي من جديد", "اعادة"]),
    "add_to_cart": (["add to cart", "add to my cart", "add it", "add them", "add those", "add these", "add the routine", "add routine",
                     "add everything", "add all", "buy it", "buy them", "i'll take it", "i will take it", "i'll take them", "put it in",
                     "put them in"],
                    ["اضيفي الروتين", "اضيفيه", "اضيفيها", "اضيف الروتين", "اشتري"]),
    "affirm": (["yes", "yes please", "yeah", "yep", "yup", "sure", "ok", "okay", "okey", "go ahead", "please do", "sounds good",
                "of course", "alright", "do it", "why not", "absolutely", "definitely", "perfect, yes", "yes sure", "ok sure", "yeah sure"],
               ["نعم", "اي", "ايوه", "تمام", "اوكي", "اكيد", "طيب", "ماشي", "يلا"]),
    "deny": (["no", "nope", "no thanks", "no thank you", "not now", "maybe later", "not yet", "nah"], ["لا", "لا شكرا", "مو الحين", "بعدين"]),
    "checkout": (["checkout", "check out", "place order", "place my order", "place the order", "proceed with order", "proceed with the order",
                  "proceed with my order", "proceed to checkout", "proceed to payment", "confirm order", "confirm my order", "confirm the order",
                  "buy now", "order now", "i want to order", "complete my order", "complete the order", "finish my order", "make the order",
                  "pay now", "i'm ready to order", "ready to order"],
                 ["اطلب الحين", "اكمل الطلب", "اكملي الطلب", "تاكيد الطلب", "اكدي الطلب", "ابي اطلب", "ابغى اطلب", "اتمام الطلب", "ابي ادفع", "اريد الدفع", "ادفع الحين"]),
    "history": (["previous history", "my history", "chat history", "previous chat", "previous conversation", "last conversation",
                 "earlier conversation", "past conversation", "last time", "remember me", "do you remember", "what do you know about me",
                 "order history", "my previous order", "my past order", "my orders", "previous orders", "what did we talk"],
                ["محادثتي السابقه", "المحادثه السابقه", "تتذكريني", "تذكريني", "طلباتي السابقه", "سجل"]),
    "order_cancel": (["cancel my order", "cancel the order", "cancel order", "cancel it", "don't want the order", "change my order",
                      "change the order", "modify my order", "edit my order"],
                     ["الغي الطلب", "الغاء الطلب", "ابي الغي", "تعديل الطلب", "غيري الطلب"]),
    "add_item": (["add the", "add a ", "add this", "add that", "add one", "add only", "add just", "yes add", "please add", "can you add", "include the", "also add", "i want the", "i'll take the", "i will take the", "i'd like the"],
                 ["اضيفي ال", "اضيف ال", "ابي ال", "ابغى ال", "اريد ال"]),
    "remove_item": (["remove", "take out", "take off", "without the", "don't want the", "dont want the", "do not want the", "don't need the",
                     "skip the", "drop the", "no need for", "get rid of the", "delete"],
                    ["احذف", "احذفي", "شيلي", "شيل", "بدون ال", "ما ابي ال", "ما ابغى ال", "لا اريد ال", "ازيلي"]),
    "recap": (["what did you recommend", "what did you suggest", "what was the routine", "remind me", "show my routine", "show me my routine",
               "my routine again", "the routine again", "repeat the routine", "what was it", "summar", "what were the products", "total again", "what was the total", "how much was it", "how much in total", "how much was the routine", "the total was"],
              ["ذكريني", "روتيني", "ماذا اقترحت", "وش اقترحتي", "ايش اقترحتي", "الروتين مره ثانيه", "الروتين مرة ثانية"]),
    "compare": (["compare", "difference", "different", "differ ", "differs", " vs", "versus", "which is better", "which one is better", "which one should", "better for me", "better than", "compared to", "compared with", "worse than"],
                ["الفرق", "مقارنه", "قارني", "ايهما", "أيهما", "افضل لي"]),
    "search": (["show me", "do you have", "what do you have", "any options", "options for", "list ", "browse", "looking for a", "looking for some",
                "what shampoos", "what masks", "what serums", "what creams", "which shampoos", "anything under", "something under", "products under"],
               ["عندكم", "عندك", "اعرضي", "ابي اشوف", "ابغى اشوف", "خيارات", "وش عندكم", "ايش عندكم"]),
    "cart_status": (["what's in my cart", "whats in my cart", "what is in my cart", "check my cart", "show my cart", "show me my cart", "view cart", "cart total", "my basket"],
                    ["ماذا في سلتي", "وش في سلتي", "ايش في سلتي", "وش في السله", "محتوى السله", "سلتي"]),
    "how_to_use": (["how to use", "how do i use", "how should i use", "how often", "when do i apply", "when should i apply", "how to apply", "directions", "how much do i",
                    "when should i use", "when do i use", "when to use", "what order", "which order", "in which order", "explain the routine",
                    "explain my routine", "about the routine", "about my routine", "about routine", "use what", "apply what", "routine steps",
                    "متى استخدم", "ترتيب", "اشرحي الروتين", "اشرحي لي الروتين", "كيف استخدم الروتين", "طريقه استخدام الروتين"],
                   ["طريقه الاستخدام", "كيف استخدم", "كيف اطبق", "طريقه استخدام", "متى استخدم", "كم مره"]),
    # explicit luxury words only: "the best product under 300" is NOT a premium request
    "premium": (["premium", "luxury", "luxurious", "cana gold version", "upgrade", "high end", "high-end", "splurge"], ["فاخر", "فخم", "ترقيه"]),
    "cheaper": (["cheaper", "less expensive", "lower price", "lighter", "too expensive", "budget option", "affordable", "something cheaper",
                 "minimal price", "minimum price", "minimal prices", "lowest price", "cheapest", "least expensive", "low budget", "as cheap as",
                 "budget friendly", "budget-friendly", "less money", "spend less", "can't afford", "cannot afford", "cant afford", "over my budget",
                 "above my budget", "more than my budget", "within my budget", "under my budget"],
                ["ارخص", "اقل سعر", "اخف", "غالي", "ميزانيه قليله", "اقل شي", "ما اقدر", "فوق ميزانيتي"]),
    "human": (["human", "real person", "talk to someone", "speak to someone", "talk to a person", "speak to a person", "agent", "customer service",
               "call me", "contact the team", "talk to the team", "talk to dr", "speak with the team"],
              ["موظف", "شخص حقيقي", "خدمه العملاء", "كلميني", "اتصلوا", "التواصل مع الفريق", "اكلم الدكتوره", "التحدث مع الفريق"]),
    "question": (["tell me about", "tell me more", "more about", "more info", "info on", "details of", "details about", "what is the",
                  "what's the", "what does the", "is the", "explain the"],
                 ["حدثيني عن", "اخبريني عن", "ما هو", "ايش هو", "وش هو", "تفاصيل", "معلومات عن"]),
    "greeting": (["hello", "hi", "hey", "good morning", "good evening", "salam", "hiya"], ["مرحبا", "السلام عليكم", "هلا", "اهلا", "صباح الخير", "مساء الخير"]),
    "thanks": (["thank", "thanks", "thx", "appreciate", "great", "perfect", "awesome", "lovely"], ["شكرا", "مشكوره", "يعطيك العافيه", "تسلمين"]),
    "capabilities": (["what can you do", "what do you do", "how can you help", "what can you help", "what can i ask", "what are you able",
                      "what are your features", "what features", "what services", "who are you", "what are you", "help me with what",
                      "what else can you do", "how does this work", "how do you work"],
                     ["ماذا تستطيعين", "ماذا تقدرين", "وش تقدرين", "ايش تقدرين", "وش تسوين", "ايش تسوين", "كيف تساعديني", "كيف تقدرين تساعديني",
                      "بماذا تساعديني", "في ماذا تساعديني", "من انتي", "من انت", "ما هي خدماتك", "ماذا تفعلين", "شو بتقدري", "شو فيكي تساعديني"]),
    "price_question": (["how much is the", "how much are the", "how much does the", "price of the", "price for the", "what's the price",
                        "what is the price", "how much for the", "cost of the"],
                       ["بكم", "كم سعر", "كم سعره", "كم سعرها", "سعر ال", "كم يكلف", "كم تكلف"]),
    "bye": (["bye", "goodbye", "see you", "talk later", "that's it for now"], ["مع السلامه", "باي", "في امان الله"]),

}
# topics far outside a beauty shop. Used only when nothing shop-related is in the message (see extract()).
OFF_TOPIC_TERMS = (["weather", "poem", "poetry", "song lyrics", "lyrics", "football", "soccer", "cricket", "basketball", "who won", "world cup",
                    "match score", "politics", "political", "election", "recipe", "homework", "math", "maths", "coding", "programming",
                    "python", "javascript", "iphone", "android phone", "movie", "netflix", "tell me a joke", "a joke", "stock market",
                    "crypto", "bitcoin", "book a flight", "flight ticket", "book a hotel", "capital of", "write me a story",
                    "write a story", "write an essay", "video game",
                    # attempts to change the assistant or reach other people's data
                    "system prompt", "ignore all previous", "ignore previous instructions", "ignore your instructions",
                    "ignore the instructions", "developer mode", "jailbreak", "your instructions", "your prompt",
                    "customer phone", "customers phone", "customers' phone", "other customers", "all customers", "all orders",
                    "customer data", "admin password", "database"],
                   ["الطقس", "طقس", "قصيده", "اغنيه", "مباراه", "كره القدم", "كوره", "كاس العالم", "مين فاز", "من فاز", "سياسه", "انتخابات", "واجب", "رياضيات",
                    "برمجه", "ايفون", "مسلسل", "نكته", "بورصه", "بيتكوين", "عملات رقميه", "تذكره طيران", "حجز طيران", "حجز فندق",
                    "عاصمه", "العاب الفيديو", "تجاهل تعليماتك", "تجاهلي تعليماتك", "تجاهلي التعليمات", "تجاهل التعليمات",
                    "ارقام العملاء", "بيانات العملاء", "كل الطلبات", "رساله حب"])
OTHER_BRANDS = ["la mer", "nivea", "olay", "loreal", "l'oreal", "l oreal", "cerave", "the ordinary", "clinique", "estee lauder",
                "lancome", "kerastase", "olaplex", "pantene", "dove", "garnier", "neutrogena", "la roche", "vichy", "bioderma",
                "shiseido", "sk-ii", "sk ii", "dior", "chanel", "eucerin", "cetaphil", "head & shoulders", "head and shoulders",
                "tresemme", "sunsilk", "himalaya", "nyx", "maybelline", "اولاي", "نيفيا", "لوريال", "سيرافي", "كلينيك", "لاروش"]
# asking to change skin colour ("how can I be fair"): answered honestly, as brightening of dark spots and dullness
TONE_CHANGE_TERMS = ["be fair", "fair skin", "fairer", "fairness", "fair complexion", "lighter skin", "lighten my skin", "lighten skin",
                     "skin lightening", "whiter skin", "white skin", "whiten", "whitening", "bleach", "change my skin colour",
                     "change my skin color", "تبييض", "بشرتي بيضاء", "بيضاء اكثر", "افتح لون", "تفتيح لون", "لون بشره افتح", "بشره بيضا"]
SENSITIVE_TERMS = (["sensitive", "irritat", "reactive", "redness"], ["حساسه", "حساس", "تتهيج", "احمرار"])
NOT_SENSITIVE_TERMS = (["not sensitive", "no", "normal", "nope", "not really"], ["لا", "ليست حساسه", "عاديه"])
SHORT_EXACT = {"yes", "ok", "okay", "okey", "sure", "no", "nope", "nah", "yep", "yup", "yeah", "hi", "hey", "نعم", "لا", "اي", "تمام", "طيب"}
AFFIRM_PREFIX = re.compile(r"^(yes|yeah|yep|yup|sure|ok|okay|alright|of course|absolutely|definitely|نعم|اي|ايوه|تمام|اكيد|طيب)\b")

# product type words -> routine steps (for browsing: "show me hair masks under 200")
TYPE_WORDS = {
    "shampoo": ["shampoo_set", "shampoo"], "conditioner": ["shampoo_set"], "mask": ["mask", "hair_mask"], "serum": ["serum", "hair_serum"],
    "cream": ["day_cream", "night_cream", "eye", "moisturizer", "brightening"], "moisturi": ["moisturizer", "day_cream", "night_cream"],
    "toner": ["toner"], "eye": ["eye"], "exfoli": ["exfoliant", "peel"], "scrub": ["exfoliant", "body"], "peel": ["peel"],
    "protein": ["protein"], "keratin": ["protein"], "botox": ["protein"], "straighten": ["protein"], "vitamin": ["supplement"],
    "supplement": ["supplement"], "gumm": ["supplement"], "body": ["body"], "lotion": ["scalp"], "scalp": ["scalp"], "set": ["set"],
    "شامبو": ["shampoo_set", "shampoo"], "ماسك": ["mask", "hair_mask"], "سيروم": ["serum", "hair_serum"], "كريم": ["day_cream", "night_cream", "eye", "moisturizer", "brightening"],
    "تونر": ["toner"], "بروتين": ["protein"], "فيتامين": ["supplement"], "مكمل": ["supplement"], "لوشن": ["scalp"],
}
LINE_WORDS = {"cana": "Cana Gold 24K", "luxliss": "Luxliss", "cystiphane": "Cystiphane", "ivybears": "IvyBears", "ivy bears": "IvyBears",
              "naturally": "Naturally No.1", "كانا": "Cana Gold 24K", "سيستيفان": "Cystiphane"}
MAX_PRICE_RX = re.compile(r"(?:under|below|less than|cheaper than|max(?:imum)?|up to|within|no more than|اقل من|تحت|حدود|بحدود)\s*(?:aed|dhs?|dirhams?|درهم)?\s*([\d,]{2,6})")
ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "last": -1,
            "الاول": 0, "الثاني": 1, "الثالث": 2, "الاخير": -1}
PRONOUN_REFS = ["it", "that one", "this one", "that", "this", "them", "both", "هذا", "هذه", "هذي", "ذا", "هذول", "الاثنين"]
NAME_RX = re.compile(r"\b(my name is|my name's|call me|i am|i'm|im|this is)\s+([A-Za-z][A-Za-z]{1,19})\b", re.I)
NAME_RX_AR = re.compile(r"(?:اسمي|انا اسمي)\s+([؀-ۿ]{2,15})")
NOT_NAMES = {"a", "an", "the", "not", "looking", "interested", "pregnant", "breastfeeding", "fine", "good", "ok", "okay", "here", "new",
             "so", "very", "really", "just", "trying", "from", "in", "on", "sure", "having", "getting", "worried", "allergic",
             "sensitive", "back", "done", "ready", "curious", "wondering", "using", "also", "still", "planning", "going", "after",
             "concerned", "struggling", "dealing", "losing", "thinking", "happy", "sorry", "years", "over", "under", "around", "about"}


@lru_cache(maxsize=1)
def _faq() -> dict:
    with open(DATA_DIR / "faq.json", encoding="utf-8") as fh:
        return json.load(fh)["topics"]


def _intent_hits(text: str, en: list[str], ar: list[str]) -> bool:
    n = normalize(text).strip(" .!?؟،")
    for term in en + ar:
        tn = normalize(term)
        if tn in SHORT_EXACT or len(tn) <= 3:
            if n == tn.strip() or re.fullmatch(rf"{re.escape(tn.strip())}[ ,!.]*(please|thanks|thank you|شكرا)?", n):
                return True
            continue
        if tn in n:
            return True
    return False


def extract_name(text: str) -> str | None:
    m = NAME_RX.search(text)
    if m:
        cue, name = m.group(1).lower(), m.group(2)
        strong = cue in ("my name is", "my name's", "call me")
        if name.lower() not in NOT_NAMES and (strong or name[0].isupper()):
            return name[0].upper() + name[1:].lower()
    m = NAME_RX_AR.search(text)
    if m:
        return m.group(1)
    return None


def extract_search(text: str) -> dict:
    n = normalize(text)
    steps = sorted({s for w, ss in TYPE_WORDS.items() if normalize(w) in n for s in ss})
    lines = sorted({line for w, line in LINE_WORDS.items() if normalize(w) in n})
    m = MAX_PRICE_RX.search(n)
    max_price = int(m.group(1).replace(",", "")) if m else None
    area = "hair" if find_terms(text, ["hair", "scalp", "شعر"]) else ("skin" if find_terms(text, ["face", "skin", "بشره", "وجه"]) else None)
    return {"steps": steps, "lines": lines, "max_price": max_price, "area": area}


def extract_ref(text: str) -> int | str | None:
    n = normalize(text)
    for w, i in ORDINALS.items():
        if re.search(rf"(?<![a-z؀-ۿ]){re.escape(normalize(w))}(?![a-z])", n):
            return i
    for w in PRONOUN_REFS:
        if re.search(rf"(?<![a-z؀-ۿ]){re.escape(normalize(w))}(?![a-z؀-ۿ])", n):
            return "both" if w in ("both", "them", "هذول", "الاثنين") else "it"
    return None


CART_WORDS = ["cart", "basket", "my order", "the order", "سله", "سلتي", "السله", "الطلب"]
CLEAR_WORDS = ["clear", "empty", "revert", "undo", "cancel", "start the cart over", "reset", "remove everything", "remove all",
               "delete everything", "delete all", "remove the current", "remove current", "all products", "all items", "everything",
               "فضي", "امسحي", "الغي", "الغاء", "كل المنتجات", "كلها", "الكل"]
REMOVE_WORDS = ["remove", "take out", "take off", "delete", "drop", "don't want", "dont want", "do not want", "get rid of", "without",
                "احذف", "احذفي", "شيلي", "شيل", "ازيلي", "ما ابي", "لا اريد"]
ONLY_WORDS = ["only", "just", "not more", "nothing else", "that one", "this one", "single", "فقط", "بس", "هذا بس"]


def extract_cart_op(text: str) -> str | None:
    """'remove the current products from my cart' -> cart_clear; 'remove the serum from my cart' -> cart_remove."""
    n = normalize(text)
    if not any(normalize(w) in n for w in CART_WORDS):
        return None
    if any(normalize(w) in n for w in CLEAR_WORDS):
        return "cart_clear"
    if any(normalize(w) in n for w in REMOVE_WORDS):
        return "cart_remove"
    return None


@lru_cache(maxsize=1)
def _unsupported() -> dict:
    with open(DATA_DIR / "unsupported.json", encoding="utf-8") as fh:
        return json.load(fh)["needs"]


def extract_unsupported(text: str) -> list[str]:
    """Needs the range doesn't cover ("do you have sunscreen?", "my feet are dry")."""
    return [k for k, v in _unsupported().items() if find_terms(text, v["kw_en"] + v["kw_ar"])]


def extract_faq(text: str) -> list[str]:
    """All store topics a message asks about ("do you deliver to Sharjah and can I pay cash?" -> shipping + payment)."""
    return [topic for topic, v in _faq().items() if find_terms(text, v["kw_en"] + v["kw_ar"])]


class RuleProvider:
    name = "rule"

    def extract(self, text: str, lang: str, context: dict) -> dict:
        cat = get_catalog()
        area_hits = {a: len(find_terms(text, v["kw_en"] + v["kw_ar"])) for a, v in cat.areas.items()}
        concern_hits = {
            a: [k for k, v in cs.items() if find_terms(text, v["kw_en"] + v["kw_ar"])]
            for a, cs in cat.concerns.items()
        }
        area = context.get("area")
        new_area = None
        ranked = sorted(area_hits.items(), key=lambda kv: (-kv[1], kv[0]))
        if ranked[0][1] > 0:
            # supplements only when explicitly mentioned; skin/hair by strongest signal
            if area_hits["supplement"] > 0 and ("vitamin" in normalize(text) or area_hits["supplement"] >= area_hits["hair"]):
                new_area = "supplement"
            else:
                new_area = max(("skin", "hair"), key=lambda a: (area_hits[a], len(concern_hits[a])))
        elif not area:
            skin_c, hair_c = len(concern_hits["skin"]), len(concern_hits["hair"])
            if set(concern_hits["supplement"]) & {"sleep", "immunity"} and not (skin_c or hair_c):
                new_area = "supplement"  # sleep and immunity are only covered by supplements
            elif skin_c or hair_c:
                new_area = "skin" if skin_c >= hair_c else "hair"
        use_area = new_area or area
        concerns = concern_hits.get(use_area, []) if use_area else []

        intents = [name for name, (en, ar) in INTENT_TERMS.items() if _intent_hits(text, en, ar)]
        if "affirm" not in intents and AFFIRM_PREFIX.match(normalize(text).strip()) and len(text.split()) <= 6:
            intents.append("affirm")
        if "price_question" not in intents and re.search(r"(?<![؀-ۿ])بكم(?![؀-ۿ])", normalize(text)):  # "بكم السيروم؟"
            intents.append("price_question")
        if claims.is_claim_question(text):
            intents.append("claim_question")
        if "question" not in intents and ("?" in text or "؟" in text or re.match(r"^\s*(what|which|how|can|could|is|are|do|does|should|will|would|when|where|why|هل|كيف|ماذا|ايش|وش|متى|ليش)\b", normalize(text))):
            intents.append("question")

        sensitivity = None
        if _intent_hits(text, *SENSITIVE_TERMS) and not find_terms(text, ["not sensitive", "ليست حساسه"]):
            sensitivity = "sensitive"
        elif (context.get("stage") in ("ask_sensitivity", "ask_q:sensitivity") and _intent_hits(text, *NOT_SENSITIVE_TERMS)) or \
                find_terms(text, ["not sensitive", "isn't sensitive", "is not sensitive", "ليست حساسه", "مو حساسه", "مش حساسه", "غير حساسه"]):
            sensitivity = "none"

        cart_op = extract_cart_op(text)
        if cart_op:
            intents.append(cart_op)
            intents = [i for i in intents if i not in ("remove_item", "add_to_cart")]
        products = [p["id"] for p in cat.find_mentioned(text)]
        only = any(normalize(w) in normalize(text) for w in ONLY_WORDS)
        budget = parse_budget(text)
        bare = re.fullmatch(r"\s*(?:aed|dhs?)?\s*([\d,]{2,6})\s*(?:aed|dhs?|dirhams?|درهم)?\s*", normalize(text))
        if budget is None and bare:  # a number on its own ("300") is a budget answer
            v = int(bare.group(1).replace(",", ""))
            budget = v if 50 <= v <= 100000 else None
        unsupported, faq = extract_unsupported(text), extract_faq(text)
        tone_change = bool(find_terms(text, TONE_CHANGE_TERMS)) and "grey_hair" not in unsupported
        if tone_change and use_area in (None, "skin") and "dark_spots" not in concerns:
            new_area, use_area = new_area or ("skin" if not area else None), use_area or "skin"
            if use_area == "skin":
                concerns = concerns + ["dark_spots"]
        # off-topic: say no politely when nothing shop-related is asked; in a mixed message answer the shop part
        # (off_topic_part: the engine adds "I'll leave that part aside" only if it ends up answering a shop question)
        off_topic_part = bool(find_terms(text, OFF_TOPIC_TERMS[0] + OFF_TOPIC_TERMS[1]))
        if off_topic_part:
            shop = (new_area or concerns or budget or products or faq or unsupported or sensitivity
                    or set(intents) - {"question", "greeting", "thanks", "affirm", "deny", "off_topic", "search"})
            if not shop:
                intents.append("off_topic")
        too_low = None
        price_change = bool(find_terms(text, ["set the price", "change the price", "price to", "lower the price", "make it free",
                                              "for free", "free of charge", "give it to me for", "غيري السعر", "خلي السعر", "ببلاش", "مجانا"]))
        if budget is None and not products and not price_change and find_terms(text, ["budget", "aed", "dirham", "dhs", "ميزانيه", "ميزانيتي", "درهم"]):
            m = re.search(r"(?<![\d.])(\d{1,2})(?![\d.])", normalize(text).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
            too_low = int(m.group(1)) if m else None
        other_brand = bool(find_terms(text, OTHER_BRANDS))
        about_routine = bool(find_terms(text, ["routine", "everything", "all of them", "each one", "each product", "what thing",
                                               "which thing", "use what", "the products", "these products", "الروتين", "كل منتج", "المنتجات"]))
        return {"about_routine": about_routine, "price_change": price_change, "budget_too_low": too_low, "other_brand": other_brand, "tone_change": tone_change, "off_topic_part": off_topic_part, "unsupported": unsupported, "named": products, "only": only, "area": new_area, "concerns": concerns, "budget": budget, "sensitivity": sensitivity,
                "intents": intents, "products": products, "name": extract_name(text), "faq": faq,
                "search": extract_search(text), "ref": extract_ref(text), "medical": False}

    def classify_safety(self, text: str) -> bool | None:
        return None

    def phrase(self, lang: str, draft: str, facts: dict, mode: str = "rewrite", history=None) -> str | None:
        return None
