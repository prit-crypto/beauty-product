"""Regression tests from the second tester conversation: yes/ok follow-ups, adding by message, history, orders."""
from app.engine.state import Session, handle
from app.providers.factory import FallbackProvider
from app.providers.llm import LLMProvider
from tests.test_user_flow import Browser, routine


def hair_routine(b):
    b.say()
    b.say(action="area:hair", label="Hair")
    b.say("I have curly hair and it get too much of thin and I also get very much of Dandruff.")
    b.say(action="sens:sensitive", label="Yes, sensitive")
    r = b.say("Under 450 AED")
    assert routine(r)["total"] == 450 and len(routine(r)["steps"]) == 2
    return r


def test_ok_with_nothing_pending_continues_instead_of_cart_message():
    b = Browser()
    b.say()
    r = b.say("OK")
    assert "cart" not in r["text"].lower() and r["quick_replies"][0]["action"].startswith("area:")


def test_history_question_on_a_new_chat():
    b = Browser()
    b.say()
    r = b.say("Hi do you have my previous history?")
    assert "new conversation" in r["text"]


def test_history_question_after_chatting_summarises_what_is_known():
    b = Browser()
    hair_routine(b)
    b.say("add this to my cart")
    r = b.say("do you remember what we talked about?")
    assert "Cystiphane" in r["text"] and "450" in r["text"]


def test_add_this_to_my_cart_after_routine_adds_whole_routine():
    b = Browser()
    hair_routine(b)
    b.say("Add this to my cart.")
    assert set(b.cart_ids) == {"cystiphane-dandruff", "cystiphane-lotion"}


def test_add_routine_button_and_add_again_never_duplicate():
    b = Browser()
    hair_routine(b)
    b.say("Add this to my cart.")
    r1 = b.say(action="add_routine", label="Add routine to cart")
    r2 = b.say("Can you add those thing again to my cart please?")
    assert len(b.cart) == 2 and all(x["qty"] == 1 for x in b.cart)
    for r in (r1, r2):
        assert not any(c["type"] == "cart_add" for c in r["cards"]) and "already in your cart" in r["text"].lower()


def test_after_partial_add_the_rest_is_added_and_message_is_honest():
    b = Browser()
    hair_routine(b)
    b.say("add the shampoo")
    assert b.cart_ids == ["cystiphane-dandruff"]
    r = b.say(action="add_routine", label="Add routine to cart")
    assert set(b.cart_ids) == {"cystiphane-dandruff", "cystiphane-lotion"}
    assert "already in your cart" in r["text"].lower() and "Lotion" in r["text"]


def test_yes_after_routine_adds_it_and_yes_after_that_opens_checkout():
    b = Browser()
    hair_routine(b)
    b.say("yes please")
    assert len(b.cart) == 2
    r = b.say("yes")
    assert any(c["type"] == "checkout" for c in r["cards"])


def test_yes_after_a_product_adds_that_product():
    b = Browser()
    b.say("Tell me about the Hair Elixir")
    b.say("yes")
    assert b.cart_ids == ["hair-elixir"]


def test_no_after_offer_does_nothing():
    b = Browser()
    hair_routine(b)
    r = b.say("no thanks")
    assert b.cart == [] and not r["cards"]


def test_checkout_when_cart_empty_and_full():
    b = Browser()
    assert "empty" in b.say("I want to place my order").get("text").lower()
    hair_routine(b)
    b.say("add this to my cart")
    r = b.say("place my order")
    co = next(c for c in r["cards"] if c["type"] == "checkout")
    assert co["total"] == 450 and len(co["items"]) == 2


def test_order_status_and_cancel_after_ordering(client):
    sid = None
    for msg in ["my hair is frizzy, budget 300", "add this to my cart"]:
        r = client.post("/api/chat", json={"session_id": sid, "message": msg, "cart": []}).json()
        sid = r["session_id"]
    items = [{"id": "luxliss-nourish-gloss", "name": "Nourish & Gloss Shampoo & Conditioner", "price_aed": 120, "qty": 1},
             {"id": "luxliss-argan-mask", "name": "Luxliss Argan Oil Intensive Moisture Mask", "price_aed": 150, "qty": 1}]
    o = client.post("/api/orders", json={"session_id": sid, "items": items, "name": "Huda Ali", "phone": "+971501234567",
                                         "emirate": "Dubai"}).json()
    assert o["ok"] and f"#{o['order_id']}" in o["message"] and "4567" in o["message"]
    st = client.post("/api/chat", json={"session_id": sid, "message": "where is my order?", "cart": []}).json()["reply"]
    assert f"#{o['order_id']}" in st["text"]
    cn = client.post("/api/chat", json={"session_id": sid, "message": "please cancel my order", "cart": []}).json()["reply"]
    assert cn["kind"] == "order" and f"#{o['order_id']}" in cn["text"]
    h = client.get("/api/admin/summary", headers={"X-Admin-Password": "test-pw"}).json()["handoffs"][0]
    assert h["name"] == "Huda Ali" and h["category"] == "order_cancel"
    hist = client.post("/api/chat", json={"session_id": sid, "message": "what are my previous orders?", "cart": []}).json()["reply"]
    assert f"#{o['order_id']}" in hist["text"]


def test_cancel_before_ordering_asks_before_emptying_the_cart():
    b = Browser()
    hair_routine(b)
    b.say("add this to my cart")
    r = b.say("cancel my order")
    assert b.cart and "haven't placed an order" in r["text"]  # never emptied on a guess
    assert [q["action"] for q in r["quick_replies"]] == ["cart_clear", "continue"]
    b.say("", action="cart_clear", label="Empty my cart")
    assert b.cart == []


class GuessingLLM(LLMProvider):
    """An AI that wrongly reads 'get back with the routine' as 'restart' and 'yes' as 'clear the cart'."""
    name = "guess"

    def _complete(self, system, user, json_mode):
        if json_mode:
            return '{"area": null, "concerns": [], "intents": ["restart", "cart_clear"], "medical": false}'
        return ""


def test_ai_alone_cannot_restart_or_clear_cart():
    p = FallbackProvider("rule")
    p.primary = GuessingLLM()
    s = Session(id="g", area="hair", concerns=["frizz"], concerns_done=True, stage="ask_sensitivity",
                cart=[{"id": "hair-elixir", "name": "Hair Elixir", "price_aed": 329, "qty": 1}])
    r = handle(s, "Yeah sure get back with the routine.", provider=p, cart=s.cart)
    assert s.area == "hair" and s.concerns == ["frizz"]
    assert not any(c["type"] == "cart_clear" for c in r["cards"])


def test_language_switch_keeps_the_conversation():
    b = Browser()
    hair_routine(b)
    b.say("add this to my cart")
    r = b.say(action="lang:ar", label="العربية")
    assert r["lang"] == "ar" and r["dir"] == "rtl" and "بالعربية" in r["text"]
    assert len(b.cart) == 2 and b.s.routine is not None
    assert all(any("؀" <= ch <= "ۿ" for ch in q["label"]) for q in r["quick_replies"])
    r2 = b.say(action="lang:en", label="English")
    assert r2["lang"] == "en" and "English" in r2["text"]


def test_language_switch_mid_question_repeats_the_question():
    b = Browser()
    b.say()
    b.say(action="area:skin", label="Skin")
    r = b.say(action="lang:ar", label="العربية")
    assert "بشرتكِ" in r["text"] and r["quick_replies"][0]["action"].startswith("concern:")
