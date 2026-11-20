"""One-off: Arabic versions of the usage directions, written to data/how_to_use_ar.json (review before the demo).
Then run scripts/build_catalog.py to merge them into data/catalog.json."""
import json

from app.config import DATA_DIR
from app.engine import claims
from app.providers.gemini import GeminiProvider

products = json.load(open(DATA_DIR / "catalog.json"))["products"]
src = {p["id"]: p["how_to_use"] for p in products if p.get("how_to_use")}
system = ("Translate each product's usage directions into natural, simple Modern Standard Arabic for a UAE beauty shop, "
          "addressing the customer in the feminine. Keep brand and product names in Latin letters and keep every number, "
          "amount and frequency exactly. Add nothing, never add claims, say 'تفتيح' not 'تبييض'. Return JSON {id: arabic_text}.")
gp = GeminiProvider()
gp.timeout = 120  # a long job, not a chat reply
out, ids = {}, list(src)
for i in range(0, len(ids), 10):  # small batches stay fast and reliable
    part = {k: src[k] for k in ids[i:i + 10]}
    out.update(json.loads(gp._complete(system, json.dumps(part, ensure_ascii=False), json_mode=True)))
keep = {k: out[k] for k in src if isinstance(out.get(k), str) and out[k].strip() and not claims.violations(out[k])}
json.dump(keep, open(DATA_DIR / "how_to_use_ar.json", "w"), ensure_ascii=False, indent=1)
print(f"translated {len(keep)} of {len(src)}; missing: {[k for k in src if k not in keep]}")
