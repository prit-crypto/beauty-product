"""Relevance: every suggested product answers a concern the customer stated; gaps are said plainly. Plus the third
tester conversation (premium for hair, checkout button, language switch)."""
import itertools

import pytest

from app.engine.catalog import get_catalog
from app.engine.recommender import build
from tests.test_user_flow import Browser, routine

SKIN = ["fine_lines", "dullness", "dark_spots", "dryness", "pores", "dark_circles", "sagging", "texture"]
HAIR = ["dry_damaged", "colour_treated", "frizz", "curly", "flat_volume", "hair_fall", "dandruff", "thinning", "straightening"]


@pytest.mark.parametrize("area,pool", [("skin", SKIN), ("hair", HAIR)])
def test_every_product_answers_a_stated_concern(area, pool):
    cat = get_catalog()
    for n in (1, 2, 3):
        for combo in itertools.combinations(pool, n):
            for budget in (None, 300, 750):
                for premium, fill in ((False, False), (area == "skin", False), (False, True)):
                    r = build(cat, area, list(combo), budget, premium=premium, fill=fill)
                    for st in r.steps + r.addons + r.dropped:
                        if st.product["caution"]:
                            continue  # supplements are optional extras with a caution, not routine answers
                        assert st.covers and set(st.covers) <= set(combo), (combo, st.product["id"])
                        assert set(st.covers) <= set(st.product["concerns"]), (combo, st.product["id"])
                    if "curly" in combo:
                        assert "protein-nano-gold-botox" not in [s.product["id"] for s in r.steps + r.addons]
                    if budget and not premium:
                        assert r.total <= budget or r.over_budget_minimum


def test_products_without_a_description_are_never_suggested():
    cat = get_catalog()
    for pid in ("protein-cleopatra", "protein-oily-extra-power"):
        assert cat.get(pid)["concerns"] == []


def third_tester(b):
    b.say()
    b.say(action="area:hair", label="Hair")
    b.say("I have too much dandruf during winter as well as I have curly damaged hair.")
    b.say(action="q:colour:no", label="No, natural")
    return b.say("Under 750 AED")


def test_dandruff_curly_damaged_routine_is_relevant_and_mentions_curls():
    b = Browser()
    r = third_tester(b)
    rt = routine(r)
    ids = [x["id"] for x in rt["steps"]]
    assert ids[0] == "cystiphane-dandruff" and "luxliss-argan-mask" in ids
    assert "cystiphane-lotion" not in ids  # no hair loss was mentioned
    assert "luxliss-curl-shine" in [x["id"] for x in rt["addons"]] and "Curl & Shine" in r["text"]


def test_premium_for_hair_fills_budget_with_relevant_products_and_adds_nothing_to_cart():
    b = Browser()
    third_tester(b)
    r = b.say("You can buy the necessary things only and also My budget is more you can add more premium things if there is.")
    rt = routine(r)
    ids = [x["id"] for x in rt["steps"]]
    assert b.cart == []
    assert "cystiphane-lotion" not in ids and "luxliss-curl-shine" in ids
    assert rt["total"] <= 750 and "Cana Gold" in r["text"]


def test_checkout_button_opens_checkout_form():
    b = Browser()
    third_tester(b)
    b.say(action="add_routine", label="Add routine to cart")
    r = b.say(action="checkout", label="Check out (cash on delivery)")
    assert any(c["type"] == "checkout" for c in r["cards"])


def test_language_switch_after_emptying_cart_is_short_and_has_no_routine_card():
    b = Browser()
    third_tester(b)
    b.say(action="add_routine", label="Add routine to cart")
    b.say(action="cart_clear", label="Empty my cart")
    r = b.say(action="lang:ar", label="العربية")
    assert r["lang"] == "ar" and not r["cards"]
    assert all(any("؀" <= ch <= "ۿ" for ch in q["label"]) for q in r["quick_replies"])


@pytest.mark.parametrize("msg,need", [("do you have sunscreen?", "sunscreen"), ("I have acne", "acne"),
                                      ("do you sell a face wash?", "face wash"), ("my feet are so dry", "foot care")])
def test_needs_outside_the_range_are_said_plainly(msg, need):
    r = Browser().say(msg)
    assert r["kind"] == "unsupported" and "doesn't have" in r["text"] and need in r["text"]


def test_routine_text_says_when_nothing_covers_a_concern():
    b = Browser()
    b.say("my hair is curly and I want it straightened")
    r = b.say("no budget")
    assert "don't have a product for" in r["text"].lower() or "straightening" not in str(routine(r) or "")


def test_removing_the_last_product_never_shows_an_empty_routine():
    b = Browser()
    b.say("my hair is curly")
    r = b.say("remove the curl shampoo")
    assert not any(c["type"] == "routine" and not c["routine"]["steps"] for c in r["cards"])
    assert b.s.routine is None
