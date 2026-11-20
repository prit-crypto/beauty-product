"""Engine tests in rule mode, including the five demo scripts (acceptance tests)."""
import json

import pytest

from app.config import DATA_DIR
from app.engine import claims, safety
from app.engine.catalog import get_catalog
from app.engine.recommender import build
from app.engine.state import Session, handle
from app.providers.factory import FallbackProvider


def rule():
    return FallbackProvider("rule")


def chat(msgs):
    s = Session(id="t")
    replies = []
    for m in msgs:
        r = handle(s, "", action=m[0], provider=rule()) if isinstance(m, tuple) else handle(s, m, provider=rule())
        replies.append(r)
    return s, replies


def routine_of(r):
    return next(c["routine"] for c in r["cards"] if c["type"] == "routine")


# ---------- catalogue
def test_catalog_integrity():
    data = json.load(open(DATA_DIR / "catalog.json", encoding="utf-8"))
    assert data["count"] == 49 == len(data["products"])
    ids = [p["id"] for p in data["products"]]
    assert len(ids) == len(set(ids))
    for p in data["products"]:
        assert isinstance(p["price_aed"], float) and 100 <= p["price_aed"] <= 9000, p["id"]
        assert p["summary"] and p["line"] and p["category"]
        assert not claims.violations(p["summary"]), p["id"]
        assert "whitening" not in p["name"].lower()


# ---------- recommender
def test_budget_cuts_keep_every_concern_covered():
    r = build(get_catalog(), "skin", ["fine_lines", "dullness", "dark_circles"], 900)
    covered = {c for s in r.steps for c in s.covers}
    assert covered == {"fine_lines", "dullness", "dark_circles"} and r.total == 887
    assert "nn1-eye-cream" in [s.product["id"] for s in r.steps]  # the only product for dark circles is kept


def test_budget_is_a_hard_limit():
    r = build(get_catalog(), "skin", ["dryness", "dark_spots", "sagging"], 300)
    assert [s.product["id"] for s in r.steps] == ["nn1-day-cream"] and r.total <= 300
    assert not r.over_budget_minimum and r.addons == []  # no AED 1,800 upsell on a AED 300 budget


def test_budget_below_every_product_keeps_the_most_affordable_and_flags():
    r = build(get_catalog(), "skin", ["fine_lines"], 150)
    assert len(r.steps) == 1 and r.over_budget_minimum


def test_supplements_always_cautioned():
    r = build(get_catalog(), "supplement", ["sleep"], None)
    assert r.caution and r.steps[0].product["id"] == "ivybears-restful-sleep"


# ---------- safety gate
@pytest.mark.parametrize("msg,cat", [
    ("Can I take Cystiphane tablets while breastfeeding?", "breastfeeding"),
    ("I'm 5 months pregnant, is the night cream ok?", "pregnancy"),
    ("I'm on roaccutane", "medication"),
    ("I have eczema on my face", "condition"),
    ("هل يناسب الحامل؟", "pregnancy"),
    ("أنا مرضعة وشعري يتساقط", "breastfeeding"),
    ("عندي حساسية من العطور", "allergy"),
])
def test_safety_hits(msg, cat):
    res = safety.check(msg)
    assert res.hit and res.category == cat


@pytest.mark.parametrize("msg", [
    "my skin is dull and I have fine lines", "my hair is frizzy after colouring", "budget around AED 900",
    "بشرتي حساسة وباهتة", "شعري جاف ومنفوش بعد الصبغة", "I want a practical routine",
])
def test_safety_no_false_alarm(msg):
    assert not safety.check(msg).hit


def test_safety_mid_conversation_hands_off_without_products():
    s, rs = chat(["my skin is dull, budget AED 900", "actually I just found out I'm pregnant"])
    last = rs[-1]
    assert last["kind"] == "handoff" and s.handoff
    assert all(c["type"] == "handoff" for c in last["cards"])


# ---------- claims filter
def test_claims_soften():
    out = claims.soften("This shampoo stops hair loss and cures dandruff, guaranteed. Whitening cream.")
    assert not claims.violations(out)
    assert "brightening" in out.lower()


# ---------- the five demo scripts
def test_demo1_english_budget_routine_and_cart():
    s, rs = chat(["I'm 38, I have fine lines around my eyes and my skin feels dull. Budget around AED 900.", ("add_routine",)])
    rt = routine_of(rs[0])
    assert [x["id"] for x in rt["steps"]] == ["nn1-day-cream", "nn1-brightening-cream", "nn1-eye-cream"]
    assert rt["total"] == 887 and rt["total"] <= 900
    assert "AED 887" in rs[0]["text"]
    cart = next(c for c in rs[1]["cards"] if c["type"] == "cart_add")
    assert cart["total"] == 887 and s.cart_value == 887


def test_demo2_arabic_hair_rtl():
    s, rs = chat(["شعري جاف ومنفوش بعد الصبغة، ماذا أستخدم؟"])
    r = rs[0]
    assert r["dir"] == "rtl" and r["lang"] == "ar"
    rt = routine_of(r)
    ids = [x["id"] for x in rt["steps"]]
    assert "luxliss-argan-mask" in ids and ids[0] in ("luxliss-colour-protect", "luxliss-nourish-gloss")
    assert all(x["covers"] for x in rt["steps"])  # every product is there for a concern she stated
    assert "protein-nano-gold-botox" not in ids


def test_demo3_breastfeeding_tablets_handoff():
    s, rs = chat(["Can I take Cystiphane tablets while breastfeeding?"])
    r = rs[0]
    assert r["kind"] == "handoff"
    assert not any(c["type"] in ("routine", "product") for c in r["cards"])
    assert "Cystiphane" not in r["text"]


def test_demo4_cure_question_declined():
    s, rs = chat(["Will this cure my hair loss?"])
    r = rs[0]
    assert r["kind"] == "claim"
    assert not claims.violations(r["text"])
    assert "Cystiphane Anti-Hair Loss Shampoo" in r["text"]


def test_button_flow_hair_fall():
    s, rs = chat(["", ("area:hair",), ("concern:hair_fall",), ("concerns_done",), ("q:hair_type:straight",), ("budget:1000",)])
    rt = routine_of(rs[-1])
    assert rt["total"] == 500 and rt["caution"]


def test_premium_then_lighter_restores_budget():
    s, rs = chat(["my skin is dull and dry, budget AED 900", ("premium",), ("cheaper",)])
    prem = routine_of(rs[1])
    assert prem["tier"] == "premium" and all(x["line"] == "Cana Gold 24K" for x in prem["steps"])
    back = routine_of(rs[2])
    assert back["tier"] == "standard" and s.budget == 900


def test_no_reply_contains_blocked_claims():
    msgs = ["hi", "my skin has dark spots", ("budget:none",), "does it whiten my skin permanently?", ("how_to_use",)]
    s, rs = chat(msgs)
    for r in rs:
        assert not claims.violations(r["text"]), r["text"]


def test_question_about_routine_product_answers_instead_of_rebuilding():
    s, rs = chat(["my hair is dry and damaged, budget 300", "can I use the mask on wet hair?"])
    r = rs[-1]
    assert r["kind"] == "info"
    assert r["cards"][0]["product"]["id"] == "luxliss-argan-mask"


def test_blood_pressure_medication_hands_off():
    s, rs = chat(["my GP put me on something new for my blood pressure, can I use the serum?"])
    assert rs[0]["kind"] == "handoff"


def test_product_photos_are_picked_up_by_file_name(tmp_path):
    from app.engine.catalog import attach_images
    (tmp_path / "nn1-day-cream.jpg").write_bytes(b"x")
    (tmp_path / "unknown-product.png").write_bytes(b"x")
    products = [{"id": "nn1-day-cream", "image": None}, {"id": "nn1-night-cream", "image": None}]
    assert attach_images(products, str(tmp_path)) == 1
    assert products[0]["image"] == "/products/nn1-day-cream.jpg" and products[1]["image"] is None
