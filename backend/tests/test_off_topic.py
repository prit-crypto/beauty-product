"""Off-topic and side questions (English + Arabic): decline politely, say what the assistant can do, and never lose the
customer's place in the conversation."""
from app.engine.state import Session, handle
from app.engine.templates import t
from app.providers.factory import FallbackProvider, _list_items
from app.providers.rule import RuleProvider


def chat(*turns, lang_start=""):
    s, cart, prov, out = Session(id="ot"), [], FallbackProvider("rule"), []
    handle(s, "", provider=prov, cart=cart)
    for m in turns:
        action = m[4:] if m.startswith("btn:") else None
        r = handle(s, "" if action else m, action=action, provider=prov, cart=[dict(x) for x in cart], label=action)
        for c in r["cards"]:
            if c["type"] == "cart_add":
                cart += [{**it, "qty": 1} for it in c["items"]]
        out.append(r)
    return s, cart, out


def test_off_topic_mid_question_keeps_the_question_arabic():
    s, _, out = chat("بشرتي جافة وفيها بقع", "كيف الطقس اليوم في دبي؟", "اكتب لي قصيدة عن الحب", "ما هو أفضل هاتف آيفون؟")
    assert s.stage == "ask_budget" and s.routine is None  # two off-topic messages did not skip the budget question
    for r in out[1:]:
        assert r["kind"] == "off_topic" and not r["cards"]
        assert t("ar", "ask_budget", 0)[:20] in r["text"] or "الميزانية" in r["text"]
        assert any("500" in q["label"] for q in r["quick_replies"])  # the budget buttons come back
    assert out[1]["text"].count("\n- ") == 6  # first time: the full list of what the assistant can do
    assert out[2]["text"].count("\n- ") == 0  # then a short line


def test_off_topic_mid_question_keeps_the_question_english():
    s, _, out = chat("my skin is dry and dull", "what's the weather today?", "budget 400")
    assert out[1]["kind"] == "off_topic" and "budget" in out[1]["text"].lower()
    assert out[2]["kind"] == "routine" and s.budget == 400


def test_capabilities_in_both_languages():
    for msg in ("what can you do?", "ماذا تستطيعين أن تفعلي؟", "وش تقدرين تسوين؟"):
        _, _, out = chat(msg)
        assert out[0]["kind"] == "capabilities" and out[0]["text"].count("\n- ") == 6


def test_pending_offer_survives_side_questions():
    # routine offered -> off-topic -> delivery question -> "yes" still adds the routine
    s, cart, out = chat("my hair is frizzy, budget 300", "tell me a joke", "do you deliver to Abu Dhabi?", "yes")
    assert "add your routine" in out[1]["text"] and "add your routine" in out[2]["text"]
    assert out[3]["kind"] == "cart" and cart
    s, cart, out = chat("شعري يتساقط وفيه قشرة", "احكي لي نكتة", "نعم")
    assert out[2]["kind"] == "cart" and len(cart) == 2


def test_mixed_message_answers_the_shop_part():
    _, _, out = chat("بشرتي جافة ميزانيتي ٤٠٠ درهم", "من فاز في مباراة الأمس؟ وكم سعر كريم الليل؟")
    r = out[-1]
    assert r["kind"] == "info" and "289" in r["text"] and r["text"].startswith(t("ar", "off_topic_part"))
    _, _, out = chat("my hair is frizzy and dry", "what's the weather like? also budget 300")
    assert out[-1]["kind"] == "routine" and out[-1]["text"].startswith(t("en", "off_topic_part"))


def test_payment_question_is_answered_not_a_checkout():
    _, _, out = chat("شعري يتساقط وفيه قشرة", "أضيفي الروتين للسلة", "هل الدفع عند الاستلام متاح؟", "نعم", "نعم")
    assert out[2]["kind"] == "faq" and not out[2]["cards"]
    assert out[3]["kind"] == "checkout"
    assert out[4]["text"] == t("ar", "checkout_fill_form")  # "yes" again: fill in the form, no second form


def test_arabic_replies_use_arabic_product_text():
    _, _, out = chat("شعري جاف", "btn:concerns_done", "btn:q:hair_type:straight", "btn:q:scalp:fine", "btn:q:colour:no",
                    "btn:budget:none", "كيف أستخدم الماسك؟")
    r = out[-1]
    assert r["kind"] == "info"
    assert not any(w in r["text"] for w in ("Apply", "apply", "hair", "wash")), r["text"]


def test_side_notes_and_old_buttons_return_to_the_routine():
    _, _, out = chat("my hair is frizzy, budget 300", "no it's not sensitive", "btn:concerns_done", "how do I use the mask?")
    assert out[1]["text"].startswith(t("en", "sens_noted_none")) and "routine" in out[1]["text"]
    assert "routine" in out[2]["text"] and out[2]["kind"] != "fallback"
    assert out[3]["text"] == t("en", "how_not_in_routine")


def test_price_question_lists_that_type():
    _, _, out = chat("شعري يتساقط وفيه قشرة", "بكم السيروم؟")
    assert out[-1]["kind"] == "search" and out[-1]["cards"][0]["type"] == "product_list"
    assert all(p["id"].startswith(("luxliss", "nn1-hair", "hair")) or "serum" in p["id"] for p in out[-1]["cards"][0]["items"])


def test_no_false_off_topic():
    rp = RuleProvider()
    for msg in ("أريد قصة شعر جديدة ومنتج للشعر الجاف", "the AC in my car dries my skin", "I cook a lot, my hands are dry",
                "does the night cream match my skin?", "any news on my order?"):
        assert "off_topic" not in rp.extract(msg, "en", {"stage": "ask_area"})["intents"], msg


def test_ai_decides_off_topic_when_it_read_the_message():
    class FakeAI:
        name = "fake"

        def extract(self, text, lang, context):
            return {"area": None, "concerns": [], "budget": None, "sensitivity": None, "intents": ["question"], "products": [],
                    "name": None, "faq": None, "search": {}, "medical": False, "only": False}

    prov = FallbackProvider("rule")
    prov.primary = FakeAI()
    ex = prov.extract("which of your creams can I take on a flight? also tell me a joke", "en", {"stage": "ask_area"})
    assert "off_topic" not in ex["intents"] and not ex["off_topic_part"]


def test_ai_wording_must_keep_the_list():
    draft = "Here's what I can do:\n- one\n- two\n- three"
    assert _list_items(draft) == 3 and _list_items("I can do lots of things!") == 0


def test_routine_buttons_follow_the_cart_and_the_order():
    """Tester's chat: routine -> added -> 'Continue shopping' -> checkout -> order placed -> 'where is my order?'"""
    from app.engine.state import _post_qrs
    s, cart, out = chat("my skin is dull and dry, budget 250", "btn:add_routine", "btn:continue")
    assert "I'm not sure" not in out[2]["text"] and "Hmm" not in out[2]["text"]
    labels = [q["label"] for q in _post_qrs(s)]
    assert "Add routine to cart" not in labels and labels[0] == "Check out (cash on delivery)"  # already in the cart
    # the order is placed (what /api/orders records), then the customer asks about it
    s.orders.append({"id": 2, "ids": [x["id"] for x in s.cart], "items": [x["name"] for x in s.cart], "total": 199,
                     "phone": "+971500005540"})
    r = handle(s, "where is my order?", provider=FallbackProvider("rule"), cart=[])
    labels = [q["label"] for q in r["quick_replies"]]
    assert r["kind"] == "order" and "Add routine to cart" not in labels and "Where is my order?" in labels
    r = handle(s, "", action="continue", provider=FallbackProvider("rule"), cart=[], label="Continue shopping")
    assert "Add routine" not in r["text"] and "add your routine" not in r["text"]
