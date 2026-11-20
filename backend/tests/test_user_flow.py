"""Regression tests from a real tester conversation: budget, cheapest option, cart edits, honest AI wording."""
from app.engine.state import Session, handle
from app.providers.factory import FallbackProvider, _claims_action
from app.providers.llm import LLMProvider


class Browser:
    """Plays the conversation like the website: buttons send actions, cart cards change the cart."""

    def __init__(self, provider=None):
        self.s, self.cart, self.provider = Session(id="flow"), [], provider

    def say(self, msg="", action=None, label=None):
        r = handle(self.s, msg, action=action, provider=self.provider or FallbackProvider("rule"),
                   cart=[dict(x) for x in self.cart], label=label)
        for c in r["cards"]:
            if c["type"] == "cart_add":
                for it in c["items"]:
                    line = next((x for x in self.cart if x["id"] == it["id"]), None)
                    if line:
                        line["qty"] += 1
                    else:
                        self.cart.append({**it, "qty": 1})
            elif c["type"] == "cart_remove":
                self.cart = [x for x in self.cart if x["id"] not in c["ids"]]
            elif c["type"] == "cart_clear":
                self.cart = []
        return r

    @property
    def cart_ids(self):
        return [x["id"] for x in self.cart]

    @property
    def cart_total(self):
        return sum(x["price_aed"] * x["qty"] for x in self.cart)


def routine(r):
    return next((c["routine"] for c in r["cards"] if c["type"] == "routine"), None)


def start_like_tester(b):
    b.say()
    b.say(action="area:skin", label="Skin")
    b.say(action="concern:dryness", label="Dryness")
    b.say(action="concern:dark_spots", label="Dark spots & uneven tone")
    b.say(action="concern:sagging", label="Loss of firmness")
    b.say(action="q:routine_size:complete", label="Complete routine")


def test_minimal_price_request_gives_cheapest_single_product():
    b = Browser()
    start_like_tester(b)
    r = b.say("I want thing in minimal prices only.")
    rt = routine(r)
    assert rt and len(rt["steps"]) == 1 and rt["total"] == 269


def test_stated_budget_is_never_exceeded():
    b = Browser()
    start_like_tester(b)
    rt = routine(b.say("Under 300 AED"))
    assert rt["total"] <= 300 and all(a["price_aed"] <= 300 - rt["total"] for a in rt["addons"])
    r = b.say("Proceed with minimal price product.")
    assert routine(r)["total"] <= 300
    r = b.say("But as I have told you my total budget is of 300 AED than how can I afford product of in total 558 AED?")
    assert routine(r)["total"] <= 300


def test_add_only_that_one_adds_only_that_one():
    b = Browser()
    start_like_tester(b)
    b.say("Under 300 AED")
    b.say("Yes add only that one. Not more than that.")
    assert b.cart_ids == ["nn1-day-cream"]


def test_routine_is_never_added_twice():
    b = Browser()
    start_like_tester(b)
    b.say("Under 300 AED")
    b.say(action="add_routine", label="Add routine to cart")
    b.say(action="add_routine", label="Add routine to cart")
    assert b.cart_ids == ["nn1-day-cream"] and b.cart[0]["qty"] == 1


def test_revert_order_empties_cart_and_shows_option_within_budget():
    b = Browser()
    start_like_tester(b)
    b.say("Under 300 AED")
    b.say(action="add_routine", label="Add routine to cart")
    b.say(action="add_item:cana-hydro-serum", label="Add Cana Gold 24K Gold & Caviar Hydro-Boosting Daily Serum")
    assert b.cart_total > 300
    r = b.say("Revert back the order I don't want to need this much of thing as my budget was of only 300 AED. So we provide me the best product under it.")
    assert b.cart == []
    assert routine(r)["total"] <= 300 and routine(r)["tier"] == "standard"


def test_remove_current_products_really_empties_cart():
    b = Browser()
    start_like_tester(b)
    b.say("Under 300 AED")
    b.say(action="add_routine", label="Add routine to cart")
    b.say("Remove the current products from my cart.")
    assert b.cart == []


def test_remove_one_product_from_cart():
    b = Browser()
    b.say("Tell me about the Hair Elixir")
    b.say("add it")
    b.say("show me hair masks under 200")
    b.say("add the first one")
    assert set(b.cart_ids) == {"hair-elixir", "luxliss-argan-mask"}
    b.say("please remove the hair elixir from my cart")
    assert b.cart_ids == ["luxliss-argan-mask"]


def test_cart_remove_without_product_asks_which():
    b = Browser()
    b.say("show me hair masks under 200")
    b.say("add the first one")
    b.say("Tell me about the Hair Elixir")
    b.say("add it")
    r = b.say("remove something from my cart")
    assert any(q["action"].startswith("cart_remove:") for q in r["quick_replies"]) and len(b.cart) == 2


def test_complaint_with_it_does_not_trigger_product_info():
    b = Browser()
    start_like_tester(b)
    b.say("Under 300 AED")
    r = b.say("I have already told you that product should be under 300 AED as It was my budget than how you have done this mistake?")
    assert r["kind"] == "routine" and routine(r)["total"] <= 300


def test_best_under_budget_is_not_premium():
    b = Browser()
    start_like_tester(b)
    r = b.say("give me the best product under 300")
    assert routine(r)["tier"] == "standard" and routine(r)["total"] <= 300


# ---------- the AI must not claim actions that did not happen
class LyingLLM(LLMProvider):
    name = "liar"

    def __init__(self, reply):
        self.reply = reply

    def _complete(self, system, user, json_mode):
        if json_mode:
            return '{"area": null, "concerns": [], "budget_aed": null, "sensitivity": null, "intents": [], "medical": false}'
        return self.reply


def with_ai(reply):
    p = FallbackProvider("rule")
    p.primary = LyingLLM(reply)
    return p


def test_ai_cannot_claim_cart_change_when_nothing_happened():
    b = Browser(with_ai("I've cleared everything out of your cart so we can start fresh."))
    b.say("hello")
    r = b.say("what can you do?")
    assert "cleared" not in r["text"].lower()
    assert any("claimed an action" in e for e in b.provider.errors)


def test_ai_may_describe_a_real_action():
    b = Browser(with_ai("Lovely, I've added the Hair Elixir to your cart."))
    b.say("Tell me about the Hair Elixir")
    r = b.say("add it")
    assert "added" in r["text"] and b.cart_ids == ["hair-elixir"]


def test_action_claim_detector():
    assert _claims_action("I have just corrected your cart to keep only the Day Cream")
    assert _claims_action("I've cleared everything out of your cart")
    assert _claims_action("لقد أزلت المنتج من سلتكِ")
    assert _claims_action("I've made sure your cart contains only the Anti-Aging Day Cream")
    assert not _claims_action("Would you like me to add it to your cart?")
    assert not _claims_action("I can remove it for you if you like.")


def test_other_brand_question_describes_ours_only():
    r = Browser().say("is your day cream better than Nivea?")
    assert r["kind"] == "info" and "other brands" in r["text"]
    assert next(c for c in r["cards"] if c["type"] == "product")["product"]["id"] == "nn1-day-cream"
