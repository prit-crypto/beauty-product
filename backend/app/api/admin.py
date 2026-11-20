import secrets
from collections import Counter

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app import store
from app.config import settings
from app.engine.catalog import get_catalog
from app.providers import factory

router = APIRouter(prefix="/api/admin")


def _auth(pw: str | None) -> None:
    if not pw or not secrets.compare_digest(pw, settings.admin_password):
        raise HTTPException(401, "Wrong password")


@router.get("/summary")
def summary(x_admin_password: str | None = Header(default=None)):
    _auth(x_admin_password)
    data = store.summary()
    cat = get_catalog()
    concerns = Counter()
    for s in data["sessions"]:
        for c in s.get("concerns") or []:
            concerns[cat.concern_label(s.get("area"), c, "en")] += 1
    data["top_concerns"] = concerns.most_common(8)
    data["totals"] = {
        "chats": len(data["sessions"]),
        "routines": sum(1 for s in data["sessions"] if s.get("routine_total")),
        "cart_value": sum(s.get("cart_value") or 0 for s in data["sessions"]),
        "orders": len(data["orders"]),
        "order_value": sum(o["total"] for o in data["orders"]),
        "handoffs_waiting": sum(1 for h in data["handoffs"] if h["status"] == "waiting"),
    }
    data["provider"] = {"active": factory.active_name(), "available": factory.available()}
    return data


class ProviderIn(BaseModel):
    provider: str


@router.post("/provider")
def set_provider(body: ProviderIn, x_admin_password: str | None = Header(default=None)):
    _auth(x_admin_password)
    if body.provider not in factory.SUPPORTED:
        raise HTTPException(400, f"Use one of {factory.SUPPORTED}")
    if not factory.available().get(body.provider):
        raise HTTPException(400, f"No API key configured for {body.provider}")
    factory.set_override(body.provider)
    return {"active": factory.active_name()}
