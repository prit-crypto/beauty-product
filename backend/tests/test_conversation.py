"""Conversation features: memory, references, recap, edit routine, compare, browse, cart, FAQ, human hand-off."""
from app.engine import claims
from app.engine.state import Session, handle
from app.providers.factory import FallbackProvider


def say(s, msg=None, action=None, cart=None, label=None):
    return handle(s, msg or "", action=action, provider=FallbackProvider("rule"), cart=cart, label=label)


def card(r, kind):
    return next((c for c in r["cards"] if c["type"] == kind), None)


def test_remembers_name_and_history():
    s = Session(id="m")
    r = say(s, "Hi, I'm Sara")
    assert s.name == "Sara" and "Sara" in r["text"]
    say(s, "my skin is dull, budget AED 900")
    assert [h["role"] for h in s.history] == ["user", "assistant", "user", "assistant"]
    assert s.history[2]["text"] == "my skin is dull, budget AED 900"


def test_button_label_is_kept_in_history():
    s = Session(id="b")
    say(s)  # greeting
    say(s, action="area:hair", label="Hair")
    assert s.history[-2] == {"role": "user", "text": "Hair"}


def test_recap_shows_the_same_routine_again():
    s = Session(id="r")
    first = card(say(s, "fine lines and dull skin, budget AED 900"), "routine")["routine"]
    r = say(s, "sorry, what did you recommend again?")
    assert r["kind"] == "recap" and card(r, "routine")["routine"]["total"] == first["total"]


def test_remove_product_from_routine_and_it_stays_out():
    s = Session(id="x")
    say(s, "fine lines, dull skin and dark circles, budget AED 900")
    r = say(s, "remove the eye cream please")
    ids = [x["id"] for x in card(r, "routine")["routine"]["steps"]]
    assert "nn1-eye-cream" not in ids and r["kind"] == "routine"
    r2 = say(s, "actually make it AED 2000")
    assert "nn1-eye-cream" not in [x["id"] for x in card(r2, "routine")["routine"]["steps"]]


def test_add_single_product_to_cart():
    s = Session(id="a")
    say(s, "fine lines and dull skin, budget AED 900")
    r = say(s, "add the exfoliant too")
    added = card(r, "cart_add")
    assert added and added["items"][0]["id"] == "nn1-exfoliant"


def test_compare_two_named_products():
    r = say(Session(id="c"), "What's the difference between the day cream and the night cream?")
    c = card(r, "compare")
    assert c and {i["id"] for i in c["items"]} == {"nn1-day-cream", "nn1-night-cream"}


def test_browse_with_price_filter():
    r = say(Session(id="s"), "show me hair masks under 200")
    lst = card(r, "product_list")
    assert lst and all(i["price_aed"] <= 200 for i in lst["items"])
    assert any(i["id"] == "luxliss-argan-mask" for i in lst["items"])


def test_ordinal_reference_to_shown_products():
    s = Session(id="o")
    say(s, "show me shampoos under 200")
    shown = s.last_products
    r = say(s, "tell me more about the second one")
    assert card(r, "product")["product"]["id"] == shown[1]


def test_add_it_after_viewing_a_product_adds_that_product():
    s = Session(id="i")
    say(s, "Tell me about the Hair Elixir")
    r = say(s, "ok add it")
    assert card(r, "cart_add")["items"][0]["id"] == "hair-elixir"


def test_cart_status_uses_browser_cart():
    cart = [{"id": "nn1-day-cream", "name": "Anti-Aging Day Cream", "price_aed": 269, "qty": 2}]
    r = say(Session(id="k"), "what's in my cart?", cart=cart)
    assert r["kind"] == "cart_status" and "538" in r["text"]
    assert say(Session(id="k2"), "what's in my cart?", cart=[])["kind"] == "cart_status"


def test_faq_payment_and_returns_handoff():
    r = say(Session(id="f"), "do you do cash on delivery?")
    assert r["kind"] == "faq" and "cash on delivery" in r["text"].lower()
    r2 = say(Session(id="f2"), "I want to return an item")
    assert card(r2, "handoff") is not None


def test_ask_for_a_human():
    s = Session(id="h")
    r = say(s, "can I talk to a real person?")
    assert r["kind"] == "handoff" and s.handoff_topic == "request"


def test_restart_keeps_name_and_history():
    s = Session(id="z")
    say(s, "my name is Mona")
    say(s, "my hair is frizzy")
    say(s, "", action="restart", label="Start over")
    assert s.name == "Mona" and s.routine is None and len(s.history) >= 4


def test_rule_replies_vary_and_stay_clean():
    texts = set()
    for i in range(3):
        s = Session(id=f"v{i}", turns=i)
        r = say(s, "hello")
        texts.add(r["text"])
        assert not claims.violations(r["text"])
    assert len(texts) >= 2


def test_history_endpoint_restores_chat(client):
    r = client.post("/api/chat", json={"message": "fine lines and dull skin, budget AED 900"}).json()
    sid = r["session_id"]
    client.post("/api/chat", json={"session_id": sid, "action": "add_routine", "label": "Add routine to cart"})
    h = client.get("/api/chat/history", params={"session_id": sid}).json()["messages"]
    assert [m["role"] for m in h] == ["user", "assistant", "user", "assistant"]
    assert h[2]["text"] == "Add routine to cart"
    assert any(c["type"] == "routine" for c in h[1]["reply"]["cards"])
    assert client.get("/api/chat/history", params={"session_id": "nope"}).json()["messages"] == []


def test_compare_it_with_the_second_one_from_earlier_list():
    s = Session(id="cmp")
    say(s, "show me shampoos under 150")
    lst = list(s.last_list)
    say(s, "tell me about the colour protect shampoo")
    r = say(s, "and how is it different from the second one?")
    c = card(r, "compare")
    assert c and {i["id"] for i in c["items"]} == {"luxliss-colour-protect", lst[1]} or lst[1] == "luxliss-colour-protect"
