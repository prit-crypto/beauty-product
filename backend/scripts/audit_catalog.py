"""Ask Gemini to check our curation (summary, concern tags) against each product's real store description.

Writes data/catalog_audit.json for a human to review. Nothing is changed automatically.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from app.config import DATA_DIR
from app.engine.catalog import get_catalog
from app.providers.gemini import GeminiProvider

cat = get_catalog()
ALLOWED = {a: list(cs) for a, cs in cat.concerns.items()}
raw = {p["id"]: p for p in json.load(open(DATA_DIR / "catalog.json"))["products"]}
SYSTEM = (
    "You audit a beauty shop's product data. Given a product's ORIGINAL store description and our curated SUMMARY and "
    "CONCERN TAGS, check that (1) every claim in SUMMARY is supported by the original description, (2) each concern tag "
    "is something the original description says the product is for, and (3) no important use in the description is "
    "missing from the tags. Concern tags allowed for skin: " + json.dumps(ALLOWED["skin"]) + "; hair: " +
    json.dumps(ALLOWED["hair"]) + "; supplements: " + json.dumps(ALLOWED["supplement"]) + ". "
    "Return JSON: {\"summary_ok\": bool, \"summary_issue\": str, \"better_summary\": str (max 18 words, only claims from "
    "the description, no medical or cure claims, never 'whitening'), \"tags_ok\": bool, \"wrong_tags\": [..], "
    "\"missing_tags\": [..], \"main_use\": str (max 12 words), \"not_suitable_for\": str (from the description only, or '')}"
)
g = GeminiProvider()


def audit(p):
    user = (f"PRODUCT: {p['original_name']} ({p['line']})\nAREA: {p['area']}\nORIGINAL DESCRIPTION: "
            f"{p['details_en']} {p['how_to_use']}\nOUR SUMMARY: {p['summary']}\nOUR CONCERN TAGS: {p['concerns']}")
    out = g._complete(SYSTEM, user, json_mode=True)
    out = re.sub(r"^```(?:json)?|```$", "", out.strip())
    return p["id"], json.loads(out)


with ThreadPoolExecutor(8) as ex:
    results = dict(ex.map(audit, raw.values()))
json.dump(results, open(DATA_DIR / "catalog_audit.json", "w"), indent=1, ensure_ascii=False)
bad = {k: v for k, v in results.items() if not v["summary_ok"] or not v["tags_ok"]}
print(f"audited {len(results)}; flagged {len(bad)}")
for k, v in bad.items():
    print(f"\n{k}: summary_ok={v['summary_ok']} {v['summary_issue'][:150]}\n   better: {v['better_summary']}"
          f"\n   wrong={v['wrong_tags']} missing={v['missing_tags']} use={v['main_use']} not_for={v['not_suitable_for']}")
