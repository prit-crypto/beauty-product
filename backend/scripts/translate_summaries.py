"""One-off: Arabic versions of the product summaries, written to data/summaries_ar.json (review before the demo)."""
import json

from app.config import DATA_DIR
from app.providers.gemini import GeminiProvider

products = json.load(open(DATA_DIR / "catalog.json"))["products"]
src = {p["id"]: p["summary"] for p in products}
system = ("Translate each product summary into natural, simple Modern Standard Arabic for a UAE beauty shop. Keep brand "
          "and product names in Latin letters, keep every claim exactly as strong as the English (never stronger, no "
          "medical or cure claims, say 'تفتيح' not 'تبييض'). Return JSON {id: arabic_summary}.")
out = json.loads(GeminiProvider()._complete(system, json.dumps(src, ensure_ascii=False), json_mode=True))
missing = [k for k in src if not out.get(k)]
json.dump({k: out[k] for k in src if out.get(k)}, open(DATA_DIR / "summaries_ar.json", "w"), ensure_ascii=False, indent=1)
print(f"translated {len(src) - len(missing)} of {len(src)}; missing: {missing}")
