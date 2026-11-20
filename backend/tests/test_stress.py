"""Random conversations (rule mode): no crashes, and the rules that matter always hold."""
import random

from app.engine import claims
from app.engine.state import Session, handle
from app.providers.factory import FallbackProvider

MSGS = ["asdfgh", "?", "123", "😊", "ok", "no", "yes", "hmm", "300", "no budget", "٣٠٠ درهم", "x" * 1500,
        "actually what about my hair?", "my hair is frizzy", "my skin is dry", "dark spots too", "budget 150", "budget 5000",
        "start over", "remove the day cream", "add the night cream too", "add it", "add the first one", "show me serums",
        "show me something under 100", "compare the first and the second", "what did you suggest?", "what's in my cart?",
        "clear my cart", "remove the serum from my cart", "cheaper please", "premium", "add more premium things",
        "how do I use it?", "do you deliver?", "talk to a person", "thank you", "I'm Sara", "what's the weather?",
        "شعري يتساقط", "اعرضي لي شامبو", "أضيفي الروتين", "احذفي كل شيء من السلة", "will it cure my wrinkles?",
        "tell me about cana gold", "I want vitamins for sleep", "place my order", "where is my order?", "cancel my order",
        "do you have my previous history?", "add this to my cart", "add those again", "do you have sunscreen?",
        "my feet are dry", "I have acne", "curly hair with dandruff", "I want it straightened", "buy the necessary things only",
        "tell me a joke", "who won the world cup?", "كيف الطقس اليوم؟", "اكتب لي قصيدة", "what can you do?", "ماذا تستطيعين أن تفعلي؟",
        "من فاز في المباراة؟ وكم سعر كريم الليل؟", "بكم السيروم؟", "هل الدفع عند الاستلام متاح؟", "no it's not sensitive",
        "بشرتي ليست حساسة", "how do I use the mask?", "hi"]
ACTIONS = ["area:skin", "area:hair", "area:supplement", "concern:dryness", "concern:frizz", "concern:curly", "concerns_done",
           "sens:none", "budget:500", "budget:none", "add_routine", "premium", "cheaper", "how_to_use", "restart", "recap",
           "cart_status", "cart_clear", "checkout", "add_item:nn1-toner", "lang:ar", "lang:en", "continue"]


def test_random_conversations_keep_the_rules():
    rng = random.Random(7)
    for run in range(300):
        s, cart = Session(id=f"r{run}"), []
        prov = FallbackProvider("rule")
        handle(s, "", provider=prov, cart=cart)
        for _ in range(rng.randint(3, 14)):
            if rng.random() < 0.35:
                a = rng.choice(ACTIONS)
                r = handle(s, "", action=a, provider=prov, cart=[dict(x) for x in cart], label=a)
            else:
                r = handle(s, rng.choice(MSGS), provider=prov, cart=[dict(x) for x in cart])
            before = [x["id"] for x in cart]
            for c in r["cards"]:
                if c["type"] == "cart_add":
                    for it in c["items"]:
                        assert not any(x["id"] == it["id"] for x in cart), "added twice"
                        cart.append({**it, "qty": 1})
                elif c["type"] == "cart_remove":
                    cart = [x for x in cart if x["id"] not in c["ids"]]
                elif c["type"] == "cart_clear":
                    cart = []
                elif c["type"] == "routine":
                    rt = c["routine"]
                    assert rt["steps"], "empty routine shown"
                    if rt["budget"] and rt["tier"] != "premium" and not rt["over_budget_minimum"]:
                        assert rt["total"] <= rt["budget"], "over budget"
                    for st in rt["steps"] + rt["addons"]:
                        assert st["caution"] or (st["covers"] and set(st["covers"]) <= set(s.concerns)), "irrelevant product"
            changed = before != [x["id"] for x in cart]
            assert changed == any(c["type"] in ("cart_add", "cart_remove", "cart_clear") for c in r["cards"])
            assert not claims.violations(r["text"]) and r["text"].strip()
            if r["kind"] in ("off_topic", "capabilities"):
                assert not r["cards"] and r["quick_replies"], "a side reply must offer a way back"
