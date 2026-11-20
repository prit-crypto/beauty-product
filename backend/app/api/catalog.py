from fastapi import APIRouter, HTTPException

from app.engine.catalog import get_catalog

router = APIRouter(prefix="/api")

CATEGORIES = [
    {"slug": "protein", "en": "Protein", "ar": "بروتين الشعر"},
    {"slug": "skincare", "en": "Skincare", "ar": "العناية بالبشرة"},
    {"slug": "haircare", "en": "Haircare", "ar": "العناية بالشعر"},
    {"slug": "supplements", "en": "Supplements", "ar": "المكملات"},
    {"slug": "anti-hair-loss", "en": "Anti Hair-loss", "ar": "ضد تساقط الشعر"},
]


@router.get("/categories")
def categories():
    cat = get_catalog()
    return [{**c, "count": len(cat.by_category(c["slug"]))} for c in CATEGORIES]


@router.get("/products")
def products(category: str | None = None, line: str | None = None):
    cat = get_catalog()
    items = cat.products
    if category:
        items = [p for p in items if p["category"] == category]
    if line:
        items = [p for p in items if p["line"] == line]
    return items


@router.get("/products/{pid}")
def product(pid: str):
    cat = get_catalog()
    if pid not in cat.by_id:
        raise HTTPException(404, "Product not found")
    return cat.by_id[pid]
