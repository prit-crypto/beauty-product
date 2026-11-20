"""Replay a conversation like the browser does, for debugging and demos.

One line per turn on stdin:
  (open)                      the chat widget opens
  btn:<action>|<label>        a button click, e.g.  btn:area:hair|Hair
  any other text              a typed message
Cart cards (add / remove / clear) are applied to a simulated cart, shown after every turn.

Usage:  MODE=gemini PYTHONPATH=. python scripts/replay.py < conversation.txt
"""
import os
import sys
import time

from app.engine.state import Session, handle
from app.providers.factory import FallbackProvider, _cache

_cache.clear()
mode = os.environ.get("MODE", "rule")
s = Session(id="replay")
cart: list[dict] = []


def apply_cart(cards: list[dict]) -> None:
    global cart
    for c in cards:
        if c["type"] == "cart_add":
            for it in c["items"]:
                line = next((x for x in cart if x["id"] == it["id"]), None)
                if line:
                    line["qty"] += 1
                else:
                    cart.append({**it, "qty": 1})
        elif c["type"] == "cart_remove":
            cart = [x for x in cart if x["id"] not in c["ids"]]
        elif c["type"] == "cart_clear":
            cart = []


def turn(msg: str = "", action: str | None = None, label: str | None = None) -> None:
    prov = FallbackProvider(mode)
    t0 = time.time()
    r = handle(s, msg, action=action, provider=prov, cart=[dict(x) for x in cart], label=label)
    apply_cart(r["cards"])
    text = r["text"].replace("\n", " / ")
    print(f"\n>> {label or msg or '(open)'}")
    print(f"   [{r['kind']} | {prov.used} {time.time() - t0:.1f}s{' | ' + str(prov.errors) if prov.errors else ''}] {text}")
    rt = next((c["routine"] for c in r["cards"] if c["type"] == "routine"), None)
    if rt:
        print(f"   ROUTINE total={rt['total']:.0f} budget={rt['budget']} steps={[x['name'] for x in rt['steps']]}"
              f" extras={[x['name'] for x in rt['addons']]} uncovered={rt.get('uncovered')}")
    print(f"   cards={[c['type'] for c in r['cards']]} qrs={[q['label'] for q in r['quick_replies']]}")
    print(f"   CART={[(x['name'], x['qty']) for x in cart]} = AED {sum(x['price_aed'] * x['qty'] for x in cart):.0f}")


for line in sys.stdin.read().split("\n"):
    line = line.rstrip()
    if line == "(open)":
        turn()
    elif line.startswith("btn:"):
        a, lbl = line[4:].split("|", 1)
        turn(action=a, label=lbl)
    elif line:
        turn(line)
