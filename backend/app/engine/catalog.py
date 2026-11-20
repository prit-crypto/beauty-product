"""Loads the product catalogue and the concern vocabulary."""
import json
import os
import re
from functools import lru_cache

from app.config import DATA_DIR
from app.engine.text import normalize

# Single words too common to identify a product on their own (they count half).
GENERIC = {"cana", "gold", "24k", "caviar", "shampoo", "conditioner", "cream", "serum", "oil", "hair", "skin", "face",
           "anti", "aging", "anti-aging", "luxury", "luxliss", "treatment", "set", "mask", "argan", "loss", "anti-hair",
           "protein", "ivybears", "vitamins", "naturally", "no", "1", "day", "night", "intensive", "moisture", "premium",
           "2in1", "women", "men", "daily", "complex", "solution", "collection", "cystiphane", "eye", "under", "body"}
STOP = {"and", "the", "with", "for", "&", "in", "of", "2", "1"}
BRANDS = {"cana", "luxliss", "ivybears", "cystiphane", "naturally"}


class Catalog:
    def __init__(self, products: list[dict], concerns: dict):
        self.products = products
        self.by_id = {p["id"]: p for p in products}
        self.areas = concerns["areas"]
        self.concerns = concerns["concerns"]
        self._ngrams = []
        for p in products:
            ws = [w for w in re.findall(r"[a-z0-9\-']+", normalize(p["name"]).replace("'s", "")) if w and w not in STOP]
            keys = []
            for size in range(1, 5):
                for i in range(len(ws) - size + 1):
                    gram = ws[i:i + size]
                    if all(w in STOP for w in gram):
                        continue
                    if size == 1:
                        weight = 0.5 if (gram[0] in GENERIC or len(gram[0]) < 3) else 1.0
                    else:
                        weight = 0.6 if all(w in GENERIC | STOP for w in gram) and size == 2 and gram[0] in BRANDS else 1.0
                    keys.append((" ".join(gram), weight))
            self._ngrams.append((p, keys))

    def get(self, pid: str) -> dict:
        return self.by_id[pid]

    def by_category(self, category: str) -> list[dict]:
        return [p for p in self.products if p["category"] == category]

    def concern_label(self, area: str, key: str, lang: str) -> str:
        for a in ([area] if area else []) + list(self.concerns):
            if key in self.concerns.get(a, {}):
                return self.concerns[a][key][lang]
        return key

    def find_mentioned(self, text: str) -> list[dict]:
        """Products the customer names, best match first ('Cystiphane tablets', 'under eye cream', 'day cream vs night cream').

        Every run of words from a product name is a key. Multi-word keys and distinctive single words count fully;
        common single words (cream, gold, hair...) count half, so 'my skin is dull' does not pick a product.
        """
        toks = [w for w in re.sub(r"[^a-z0-9؀-ۿ\- ]+", " ", normalize(text)).split() if w not in STOP]
        n = " " + " ".join(toks) + " "
        n_sing = re.sub(r"(\w{3,})s\b", r"\1", n)  # tolerate plurals: "tablets" ~ "tablet"
        scored = []
        for p, words in self._ngrams:
            hits = sorted((len(key) * weight for key, weight in words if f" {key} " in n or f" {key} " in n_sing), reverse=True)
            if hits and hits[0] >= 4.5:
                # strongest phrase, plus a little for every other matching word ("argan oil" + "mask")
                scored.append((hits[0] + 0.25 * sum(hits[1:]), p))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return []
        top = scored[0][0]
        return [p for sc, p in scored if sc >= max(4.5, top * 0.5)][:4]


IMAGE_EXTS = (".webp", ".jpg", ".jpeg", ".png")


def attach_images(products: list[dict], folder: str) -> int:
    """Link photos named after product ids (e.g. nn1-day-cream.jpg) in the frontend's public/products folder."""
    try:
        files = {f.rsplit(".", 1)[0]: f for f in os.listdir(folder) if f.lower().endswith(IMAGE_EXTS)}
    except FileNotFoundError:
        return 0
    n = 0
    for p in products:
        if p["id"] in files:
            p["image"] = f"/products/{files[p['id']]}"
            n += 1
    return n


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    from app.config import settings
    with open(DATA_DIR / "catalog.json", encoding="utf-8") as fh:
        products = json.load(fh)["products"]
    attach_images(products, settings.product_images_dir)
    with open(DATA_DIR / "concerns.json", encoding="utf-8") as fh:
        concerns = json.load(fh)
    return Catalog(products, concerns)
