"""Build data/catalog.json from the archived store pages plus our curation.

Prices, original text and how-to-use come from the archive (Dec 2024 snapshot of drbeautycare.org).
Line, routine step, concern tags and the one-line summaries are OUR draft, to be validated by Dr. Shaymaa.

Run:  python scripts/build_catalog.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from parse_archive import parse_dir  # noqa: E402

# slug -> (id, display name, line, category, area, step, time, concerns, size, origin, summary, flags)
# step:   toner | serum | day_cream | night_cream | eye | exfoliant | mask | peel | moisturizer | brightening | body | set
#         shampoo_set | shampoo | hair_mask | hair_serum | scalp | protein | supplement
# time:   am | pm | both | weekly
# flags:  premium | caution (supplement) | handoff (always route to the team before use)
C = {
    # ---- Naturally No.1 skincare
    "facial-toner-50-ml-1-69-fl-oz": ("nn1-toner", "Facial Toner", "Naturally No.1", "skincare", "skin", "toner", "both",
        ["pores", "dryness"], "50 ml", "", "Gentle, hydrating toner that cleanses and refines the look of pores.", []),
    "day-cream-50-ml-1-69-fl-oz": ("nn1-day-cream", "Anti-Aging Day Cream", "Naturally No.1", "skincare", "skin", "day_cream", "am",
        ["fine_lines", "sagging", "dryness"], "50 ml", "", "Light day cream with collagen, elastin and hyaluronic acid for firmer, younger-looking skin.", []),
    "night-cream-50-ml-1-69-fl-oz": ("nn1-night-cream", "Anti-Aging Night Cream", "Naturally No.1", "skincare", "skin", "night_cream", "pm",
        ["fine_lines", "dryness"], "50 ml", "", "Plumping night moisturiser that helps smooth the look of wrinkles and fine lines.", []),
    "under-eye-cream-30-ml-1-01-fl-oz": ("nn1-eye-cream", "Anti-Aging Under Eye Cream", "Naturally No.1", "skincare", "skin", "eye", "both",
        ["dark_circles", "fine_lines"], "30 ml", "", "Light eye cream for puffiness, dark circles and fine lines around the eyes.", []),
    "anti-aging-exfoliant-50-ml-1-69-fl-oz": ("nn1-exfoliant", "Anti-Aging Exfoliant", "Naturally No.1", "skincare", "skin", "exfoliant", "weekly",
        ["dullness", "texture"], "50 ml", "", "Gentle arrowroot and fruit-enzyme scrub that exfoliates and hydrates for smoother, more radiant skin, 1-2 times a week.", []),
    "whitening-cream-50-ml-1-69-fl-oz": ("nn1-brightening-cream", "Anti-Aging Brightening Cream", "Naturally No.1", "skincare", "skin", "brightening", "pm",
        ["dark_spots", "dullness"], "50 ml", "", "Licorice, bearberry and rice extracts to gradually even out skin tone and the look of dark spots.", []),
    # ---- Cana Gold 24K
    "cana-gold-24k-toner-rose-water-jasmine-oil120ml-4-0fl-oz": ("cana-toner", "Cana Gold 24K Toner, Rose Water & Jasmine Oil", "Cana Gold 24K", "skincare", "skin", "toner", "both",
        ["dryness", "dullness", "fine_lines"], "120 ml", "USA", "Luxury toner that removes environmental residues, hydrates and brightens the look of skin.", ["premium"]),
    "cana-gold-24k-gold-moisturizer-50ml-1-7fl-oz": ("cana-moisturizer", "Cana Gold 24K Gold Moisturizer", "Cana Gold 24K", "skincare", "skin", "moisturizer", "both",
        ["dryness"], "50 ml", "USA", "Rich 24K gold moisturiser for face, neck and chest that hydrates and adds a healthy sheen.", ["premium"]),
    "cana-gold-24k-gold-caviar-2-in-1-eye-contouring-repair-complex-treatment-serum-50ml-1-7fl-oz-copy": ("cana-eye-serum", "Cana Gold 24K Gold & Caviar Eye Contouring & Repair Serum", "Cana Gold 24K", "skincare", "skin", "eye", "both",
        ["fine_lines", "sagging", "dryness"], "50 ml", "USA", "Gold and caviar eye serum that hydrates and supports elasticity around the eyes.", ["premium"]),
    "cana-gold-24k-gold-caviar-2-in-1-eye-contouring-repair-complex-treatment-serum-50ml-1-7fl-oz": ("cana-hydro-serum", "Cana Gold 24K Gold & Caviar Hydro-Boosting Daily Serum", "Cana Gold 24K", "skincare", "skin", "serum", "both",
        ["dryness", "dullness"], "50 ml", "USA", "Hydro-boosting gold and caviar serum for daily hydration and radiance.", ["premium"]),
    "cana-gold-24k-gold-and-caviar-2in1-gold-brightening-and-whitening-treatment-serum-50ml-1-7fl-oz": ("cana-brightening-serum", "Cana Gold 24K Gold & Caviar Brightening Serum", "Cana Gold 24K", "skincare", "skin", "serum", "both",
        ["dark_spots", "dullness"], "50 ml", "USA", "Gold and caviar brightening serum for the face, neck and under-eye area.", ["premium"]),
    "cana-gold-24k-gold-oxygen-whitening-treatment-50ml-1-7fl-oz": ("cana-oxygen-brightening", "Cana Gold 24K Gold Oxygen Brightening Treatment", "Cana Gold 24K", "skincare", "skin", "serum", "pm",
        ["dark_spots", "dullness", "dryness"], "50 ml", "USA", "Vitamin-rich brightening treatment with intense moisture for a more even, radiant complexion.", ["premium"]),
    "cana-gold-24k-non-surgical-instant-lifting-solution-40ml-1-3fl-oz": ("cana-instant-lifting", "Cana Gold 24K Non-Surgical Instant Lifting Solution", "Cana Gold 24K", "skincare", "skin", "serum", "both",
        ["sagging", "fine_lines"], "40 ml", "USA", "Instant tightening finish for a lifted look on special occasions.", ["premium"]),
    "cana-gold-24k-2-in-1-anti-aging-neck-and-decolletage-treatment-serum-50ml-1-7fl-oz": ("cana-neck-serum", "Cana Gold 24K Gold & Caviar Neck & Decollete Serum", "Cana Gold 24K", "skincare", "skin", "serum", "both",
        ["fine_lines"], "50 ml", "USA", "Anti-aging gold and caviar serum for the neck and chest area.", ["premium"]),
    "cana-gold-24k-gold-collagen-mask-50ml-1-7fl-oz": ("cana-collagen-mask", "Cana Gold 24K Gold Collagen Mask", "Cana Gold 24K", "skincare", "skin", "mask", "weekly",
        ["sagging", "fine_lines"], "50 ml", "USA", "Collagen mask to support skin density and elasticity for a firmer look.", ["premium"]),
    "cana-gold-24k-magnetic-mask-50ml-1-7fl-oz": ("cana-magnetic-mask", "Cana Gold 24K Magnetic Mask", "Cana Gold 24K", "skincare", "skin", "mask", "weekly",
        ["dullness", "texture", "fine_lines"], "50 ml", "USA", "Magnetic mask that lifts away impurities for glowing skin and smoother-looking fine lines.", ["premium"]),
    "cana-gold-24k-deep-facial-peel-50ml-1-7fl-oz": ("cana-deep-peel", "Cana Gold 24K Deep Facial Peel", "Cana Gold 24K", "skincare", "skin", "peel", "weekly",
        ["dullness", "texture", "pores", "fine_lines"], "50 ml", "USA", "Peel mask that gently exfoliates dull surface skin, smooths texture and cleans pores.", ["premium"]),
    "cana-gold-24k-daily-rejuvenating-set": ("cana-rejuvenating-set", "Cana Gold 24K Daily Rejuvenating Set", "Cana Gold 24K", "skincare", "skin", "set", "both",
        ["fine_lines", "dullness", "dryness"], "Set", "USA", "Gentle daily gold set, suitable from your mid-20s.", ["premium"]),
    "cana-gold-24k-gold-caviar-2-in-1-daily-treatment-serum-50ml-1-7fl-oz": ("cana-daily-set", "Cana Gold 24K Gold & Caviar Daily Treatment Set", "Cana Gold 24K", "skincare", "skin", "set", "both",
        ["dryness", "dullness"], "Set", "USA", "Gold and caviar daily treatment for a rejuvenated glow.", ["premium"]),
    "cana-gold-24k-gold-caviar-overnight-application-treatment-set-50ml-1-7fl-oz": ("cana-overnight-set", "Cana Gold 24K Gold & Caviar Overnight Treatment Set", "Cana Gold 24K", "skincare", "skin", "set", "pm",
        ["fine_lines", "sagging"], "3 x 50 ml", "USA", "Overnight serum, eye serum and neck serum in one set.", ["premium"]),
    "cana-gold-non-surgical-instant-lifting-pearl-gold-treatment-set": ("cana-pearl-set", "Cana Gold Non-Surgical Instant Lifting Pearl & Gold Set", "Cana Gold 24K", "skincare", "skin", "set", "both",
        ["fine_lines", "sagging"], "Set", "USA", "The signature pearl and gold lifting collection with a hydrating caviar and gold serum.", ["premium"]),
    "cana-gold-24k-gold-premium-body-butter-250gm-8-8fl-oz": ("cana-body-butter", "Cana Gold 24K Gold Premium Body Butter", "Cana Gold 24K", "skincare", "body", "body", "both",
        ["body_dryness"], "250 g", "USA", "Rich body butter to lock in moisture after showering.", ["premium"]),
    "cana-gold-24k-gold-premium-body-scrub-jasmine-230-gm-8-1-fl-oz": ("cana-body-scrub", "Cana Gold 24K Gold Premium Body Scrub, Jasmine", "Cana Gold 24K", "skincare", "body", "body", "weekly",
        ["body_texture"], "230 g", "USA", "Exfoliating 24K gold jasmine body scrub for a radiant glow.", ["premium"]),
    # ---- Hair care
    "colour-protect-shampoo-and-conditioner": ("luxliss-colour-protect", "Colour Protect Shampoo & Conditioner", "Luxliss", "haircare", "hair", "shampoo_set", "both",
        ["colour_treated", "dry_damaged"], "300 ml + 300 ml", "USA", "Argan, quinoa and rose oil wash that helps colour-treated hair keep its shine.", []),
    "curl-and-shine-shampoo-and-conditioner": ("luxliss-curl-shine", "Curl & Shine Shampoo & Conditioner", "Luxliss", "haircare", "hair", "shampoo_set", "both",
        ["curly"], "300 ml + 300 ml", "USA", "Shea butter, jojoba and keratin to moisturise, detangle and add shine to curls.", []),
    "nourish-and-gloss-shampoo-and-conditioner": ("luxliss-nourish-gloss", "Nourish & Gloss Shampoo & Conditioner", "Luxliss", "haircare", "hair", "shampoo_set", "both",
        ["frizz", "dry_damaged"], "300 ml + 300 ml", "USA", "Smoothing wash that tames frizz for silky, glossy hair.", []),
    "repair-and-restore-shampoo-and-conditioner": ("luxliss-repair-restore", "Repair & Restore Shampoo & Conditioner", "Luxliss", "haircare", "hair", "shampoo_set", "both",
        ["dry_damaged"], "300 ml + 300 ml", "USA", "Coconut, castor oil and hyaluronic acid to rehydrate dry, damaged hair.", []),
    "volume-and-boost-shampoo-and-conditioner": ("luxliss-volume-boost", "Volume & Boost Shampoo & Conditioner", "Luxliss", "haircare", "hair", "shampoo_set", "both",
        ["flat_volume"], "300 ml + 300 ml", "USA", "Lightweight wash that adds body and volume to flat, limp hair.", []),
    "argan-oil-luxury-intensive-moisture-shampoo": ("luxliss-argan-wash", "Argan Oil Luxury Intensive Moisture Shampoo & Conditioner", "Luxliss", "haircare", "hair", "shampoo_set", "both",
        ["dry_damaged", "colour_treated"], "Set", "USA", "Sulfate-free argan oil wash that restores moisture, shine and softness to dry or chemically treated hair.", []),
    "luxliss-argan-oil-luxury-intensive-moisture-mask": ("luxliss-argan-mask", "Luxliss Argan Oil Intensive Moisture Mask", "Luxliss", "haircare", "hair", "hair_mask", "weekly",
        ["dry_damaged", "colour_treated"], "", "USA", "Keratin and argan oil mask that helps restructure damaged and colour-treated hair.", []),
    "luxliss-argan-oil-luxury-serum": ("luxliss-argan-serum", "Luxliss Argan Oil Luxury Serum", "Luxliss", "haircare", "hair", "hair_serum", "both",
        ["dry_damaged"], "", "USA", "Argan oil and keratin finishing serum that conditions and protects hair.", []),
    "luxliss-luxury-argan-oil": ("luxliss-argan-collection", "Luxliss Luxury Argan Oil Collection", "Luxliss", "haircare", "hair", "set", "both",
        ["dry_damaged", "colour_treated"], "Shampoo, conditioner, mask", "USA", "Argan oil shampoo, conditioner and mask to restore moisture and protect colour-treated hair.", []),
    "hair-elixir": ("hair-elixir", "Hair Elixir", "Naturally No.1", "haircare", "hair", "scalp", "both",
        ["thinning", "dry_damaged"], "50 ml", "", "Scalp elixir with vitamins, collagen and keratin for healthier, fuller-looking hair.", []),
    # ---- Hair protein treatments (salon-style)
    "brazilian-cleopatra-hair-protein": ("protein-cleopatra", "Brazilian Cleopatra Hair Protein", "Hair Protein Treatments", "protein", "hair", "protein", "weekly",
        [], "1 L", "Brazil", "Brazilian salon hair protein treatment (1 L). The store gives no details, so ask Dr. Shaymaa's team which hair it suits.", []),
    "machademia-filler": ("protein-macadamia-filler", "Macadamia Filler", "Hair Protein Treatments", "protein", "hair", "protein", "weekly",
        ["frizz", "straightening", "dry_damaged"], "1 L", "Brazil", "Oil-rich straightening treatment that controls frizz and volume.", []),
    "nano-gold-botox": ("protein-nano-gold-botox", "Nano Gold Hair Botox", "Hair Protein Treatments", "protein", "hair", "protein", "weekly",
        ["frizz", "dry_damaged", "straightening"], "500 ml", "Brazil", "Hair 'botox' treatment for split ends, frizz and lack of shine.", []),
    "oily-extra-power-protein": ("protein-oily-extra-power", "Oily Extra Power Protein", "Hair Protein Treatments", "protein", "hair", "protein", "weekly",
        [], "1 L", "Brazil", "Brazilian salon hair protein treatment (1 L). The store gives no details, so ask Dr. Shaymaa's team which hair it suits.", []),
    "original-protein-therapy": ("protein-original-therapy", "Original Protein Therapy", "Hair Protein Treatments", "protein", "hair", "protein", "weekly",
        ["dry_damaged", "frizz", "straightening"], "", "Brazil", "Repairing protein therapy that strengthens and smooths strands.", []),
    "smart-detox-ultra-care-protein": ("protein-smart-detox", "Smart Detox Ultra Care Protein", "Hair Protein Treatments", "protein", "hair", "protein", "weekly",
        ["frizz", "straightening", "dry_damaged"], "1 L", "Brazil", "Progressive treatment with biotin, caviar and Brazilian oils.", []),
    # ---- Cystiphane (anti hair-loss)
    "cystiphane-anti-hair-loss-shampoo": ("cystiphane-shampoo", "Cystiphane Anti-Hair Loss Shampoo", "Cystiphane", "anti-hair-loss", "hair", "shampoo", "both",
        ["hair_fall"], "200 ml", "France", "Vitamin B6, cystine and zinc shampoo for hair that sheds easily.", []),
    "cystiphane-anti-dandruff-shampoo-normal-strength": ("cystiphane-dandruff", "Cystiphane Anti-Dandruff Shampoo", "Cystiphane", "anti-hair-loss", "hair", "shampoo", "both",
        ["dandruff"], "", "France", "Anti-dandruff shampoo for a calmer, flake-free scalp.", []),
    "this-cystiphane-anti-hair-loss-lotion": ("cystiphane-lotion", "Cystiphane Anti-Hair Loss Lotion", "Cystiphane", "anti-hair-loss", "hair", "scalp", "both",
        ["hair_fall", "thinning"], "", "France", "Scalp lotion that helps fortify thinning, weaker hair.", []),
    "cystiphane-anti-hair-loss-tablets": ("cystiphane-tablets", "Cystiphane Anti-Hair Loss Tablets", "Cystiphane", "anti-hair-loss", "supplement", "supplement", "both",
        ["hair_fall"], "", "France", "Oral hair supplement with cystine and zinc for hair that sheds easily.", ["caution", "handoff"]),
    "cystiphane-anti-hair-loss-trio": ("cystiphane-trio", "Cystiphane Anti-Hair Loss Trio", "Cystiphane", "anti-hair-loss", "hair", "set", "both",
        ["hair_fall"], "Set", "France", "Shampoo, lotion and tablets together for hair that sheds easily.", ["caution", "handoff"]),
    # ---- IvyBears supplements
    "dnk-blue-tshirt": ("ivybears-women-hair", "IvyBears Women's Hair Vitamins", "IvyBears", "supplements", "supplement", "supplement", "both",
        ["hair_growth"], "", "", "Keratin, folic acid and B-vitamin gummies for smoother, stronger-looking hair.", ["caution"]),
    "green-tshirt": ("ivybears-hair", "IvyBears Hair Vitamins (Men)", "IvyBears", "supplements", "supplement", "supplement", "both",
        ["hair_growth"], "", "", "Biotin multivitamin gummies for men, for stronger hair.", ["caution"]),
    "buddha-bracelet-2": ("ivybears-vibrant-skin", "IvyBears Vibrant Skin", "IvyBears", "supplements", "supplement", "supplement", "both",
        ["skin_glow"], "", "", "Collagen and hyaluronic acid gummies for glowing skin.", ["caution"]),
    "boho-bangle-bracelet-2": ("ivybears-boost-immune", "IvyBears Boost Immune", "IvyBears", "supplements", "supplement", "supplement", "both",
        ["immunity"], "", "", "B-complex, zinc and vitamins C, D, E gummies.", ["caution"]),
    "orange-tshirt": ("ivybears-restful-sleep", "IvyBears Restful Sleep", "IvyBears", "supplements", "supplement", "supplement", "both",
        ["sleep"], "", "", "Gummies to support relaxation and restful sleep.", ["caution"]),
}

AR_RE = re.compile(r"[؀-ۿ]")


def split_lang(text: str) -> tuple[str, str]:
    m = AR_RE.search(text)
    if not m:
        return text.strip(), ""
    return text[: m.start()].strip(" _-"), text[m.start():].strip()


def how_to_use(text: str) -> str:
    m = re.search(r"How to (?:Use|apply)\??:?\s*(.+?)(?:Why you should|Description|Ingredients|$)", text, re.I | re.S)
    if not m:
        return ""
    text = m.group(1).strip()
    if len(text) <= 420:
        return text
    cut = text[:420]
    return cut[: cut.rfind(".") + 1] if "." in cut else cut.rsplit(" ", 1)[0] + "…"


def main() -> None:
    from_claims = json.load(open(os.path.join(ROOT, "data", "blocked_terms.json"), encoding="utf-8"))
    rewrites = [(re.compile(r["pattern"], re.I), r["replace"]) for r in from_claims["en"]]

    def soften(t: str) -> str:
        for rx, rep in rewrites:
            t = rx.sub(rep, t)
        return t

    raw = parse_dir(os.path.join(ROOT, "data", "raw", "pages"))
    ar_path = os.path.join(ROOT, "data", "summaries_ar.json")
    summaries_ar = json.load(open(ar_path, encoding="utf-8")) if os.path.exists(ar_path) else {}
    how_path = os.path.join(ROOT, "data", "how_to_use_ar.json")
    how_ar = json.load(open(how_path, encoding="utf-8")) if os.path.exists(how_path) else {}
    products = []
    for r in raw:
        if r["slug"] not in C:
            print("WARN: uncurated page", r["slug"], file=sys.stderr)
            continue
        pid, name, line, cat, area, step, time, concerns, size, origin, summary, flags = C[r["slug"]]
        en, ar = split_lang(r["short"])
        products.append({
            "id": pid,
            "name": name,
            "original_name": r["name"],
            "line": line,
            "category": cat,
            "area": area,
            "step": step,
            "time": time,
            "concerns": concerns,
            "price_aed": r["prices_aed"][0] if r["prices_aed"] else None,
            "price_options_aed": r["prices_aed"],
            "size": size,
            "origin": origin,
            "summary": summary,
            "summary_ar": summaries_ar.get(pid),
            "details_en": soften(en)[:900],
            "details_ar": ar[:900],
            "how_to_use": soften(how_to_use(r["short"] + " " + r["description"])),
            "how_to_use_ar": how_ar.get(pid),
            "premium": "premium" in flags,
            "caution": "caution" in flags,
            "handoff": "handoff" in flags,
            "image": None,
            "source": "web.archive.org snapshot of drbeautycare.org, Dec 2024",
        })
    products.sort(key=lambda p: (p["category"], p["price_aed"] or 0))
    out = os.path.join(ROOT, "data", "catalog.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"currency": "AED", "count": len(products), "products": products}, fh, ensure_ascii=False, indent=1)
    print(f"wrote {len(products)} products -> {out}")


if __name__ == "__main__":
    main()
