"""Provider portability: AI wording is validated, failures fall back to rules, live tests run only with keys."""
import os

import pytest


@pytest.fixture(autouse=True)
def _no_cooldown():
    factory._cooldown_until.clear()
    yield
    factory._cooldown_until.clear()

from app.engine import claims
from app.engine.state import Session, handle
from app.providers import factory
from app.providers.factory import FallbackProvider
from app.providers.llm import LLMProvider


class FakeLLM(LLMProvider):
    name = "fake"

    def __init__(self, reply_text="", extract_json=None, medical=False, fail=False):
        self.reply_text, self.extract_json, self.medical, self.fail = reply_text, extract_json, medical, fail

    def _complete(self, system, user, json_mode):
        if self.fail:
            raise TimeoutError("simulated outage")
        if json_mode:
            return self.extract_json or ('{"area": null, "concerns": [], "budget_aed": null, "sensitivity": null, "intents": [], "medical": %s}'
                                         % ("true" if self.medical else "false"))
        return self.reply_text


def with_fake(fake) -> FallbackProvider:
    p = FallbackProvider("rule")
    p.primary = fake
    return p


def test_ai_rewording_used_when_valid():
    fake = FakeLLM(reply_text="Lovely! Your routine comes to AED 857 for 3 products. Shall I add it to your cart?")
    s = Session(id="x")
    r = handle(s, "fine lines and dull skin, budget AED 900", provider=with_fake(fake))
    assert r["text"].startswith("Lovely!")
    assert next(c for c in r["cards"] if c["type"] == "routine")["routine"]["total"] == 857


def test_ai_invented_price_rejected():
    fake = FakeLLM(reply_text="Your routine costs only AED 499 today!")
    prov = with_fake(fake)
    r = handle(Session(id="x"), "fine lines and dull skin, budget AED 900", provider=prov)
    assert "499" not in r["text"] and "AED 857" in r["text"]
    assert any("rejected" in e for e in prov.errors)


def test_ai_blocked_claim_softened():
    fake = FakeLLM(reply_text="This routine cures wrinkles, guaranteed. Total AED 887.")
    r = handle(Session(id="x"), "fine lines and dull skin, budget AED 900", provider=with_fake(fake))
    assert not claims.violations(r["text"])


def test_ai_failure_falls_back_to_rules():
    prov = with_fake(FakeLLM(fail=True))
    r = handle(Session(id="x"), "I'm 38, fine lines around my eyes and dull skin. Budget AED 900.", provider=prov)
    assert r["kind"] == "routine" and "AED 887" in r["text"]
    assert prov.used == "rule" and prov.errors


def test_failure_pauses_ai_so_next_turn_is_fast():
    fake = FakeLLM(fail=True)
    calls = {"n": 0}
    orig = fake._complete

    def counting(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    fake._complete = counting
    handle(Session(id="c1"), "my hair is frizzy", provider=with_fake(fake))
    first = calls["n"]
    prov2 = with_fake(fake)
    handle(Session(id="c2"), "my skin is dull, budget AED 900", provider=prov2)
    assert calls["n"] == first and "fake: cooling down" in prov2.errors


def test_ai_extract_adds_what_rules_missed():
    fake = FakeLLM(extract_json='{"area": "skin", "concerns": [{"concern": "sagging", "words": "losing its bounce"}], "budget_aed": 1500, "sensitivity": null, "intents": []}')
    s = Session(id="x")
    handle(s, "my face is losing its bounce lately, spending up to fifteen hundred", provider=with_fake(fake))
    assert s.area == "skin" and "sagging" in s.concerns and s.budget == 1500


def test_ai_safety_classifier_adds_handoff():
    fake = FakeLLM(medical=True)
    r = handle(Session(id="x"), "my GP put me on something new last week, can I use the serum?", provider=with_fake(fake))
    assert r["kind"] == "handoff"


def test_missing_key_uses_rule():
    if os.getenv("GEMINI_API_KEY") or factory.settings.gemini_api_key:
        pytest.skip("a Gemini key is configured")
    factory._cache.clear()
    p = FallbackProvider("gemini")
    assert p.name == "rule" and p.primary is None
    r = handle(Session(id="k"), "my hair is frizzy", provider=p)
    assert r["kind"] == "routine"


@pytest.mark.parametrize("name,key", [("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY")])
def test_live_provider_demo_script(name, key):
    if not os.getenv(key):
        pytest.skip(f"{key} not set")
    factory._cache.clear()
    prov = FallbackProvider(name)
    r = handle(Session(id="live"), "I'm 38, I have fine lines around my eyes and my skin feels dull. Budget around AED 900.", provider=prov)
    rt = next(c for c in r["cards"] if c["type"] == "routine")["routine"]
    assert rt["total"] == 887
    assert prov.used == name, f"{name} did not answer; errors: {prov.errors}"
    assert not claims.violations(r["text"])
    r2 = handle(Session(id="live2"), "Can I take Cystiphane tablets while breastfeeding?", provider=prov)
    assert r2["kind"] == "handoff"
    # a medical topic the keyword list does not contain: only the AI can catch it
    prov3 = FallbackProvider(name)
    r3 = handle(Session(id="live3"), "I started a new treatment from my endocrinologist last week, is the serum fine with it?", provider=prov3)
    assert prov3.used == name, f"{name} did not answer; errors: {prov3.errors}"
    assert r3["kind"] == "handoff"


def test_ai_concern_without_quoted_words_is_dropped():
    fake = FakeLLM(extract_json='{"area": "hair", "concerns": [{"concern": "hair_fall", "words": "my hair keeps falling"},'
                                ' {"concern": "dandruff", "words": "flakes"}], "intents": ["premium"]}')
    s = Session(id="q", area="hair", concerns=["curly"], concerns_done=True, stage="recommended")
    handle(s, "my budget is more, add premium things and I get flakes", provider=with_fake(fake))
    assert "hair_fall" not in s.concerns and "dandruff" in s.concerns


def test_ai_alone_cannot_add_to_cart():
    fake = FakeLLM(extract_json='{"area": null, "concerns": [], "intents": ["add_to_cart", "premium"]}')
    s = Session(id="a", area="hair", concerns=["dandruff", "curly"], concerns_done=True, stage="recommended", budget=750)
    handle(s, "", action="area:hair", provider=with_fake(fake))
    r = handle(s, "You can buy the necessary things only and also my budget is more, add more premium things", provider=with_fake(fake))
    assert not any(c["type"] == "cart_add" for c in r["cards"])
