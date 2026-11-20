import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import store
from app.engine.state import Session, _mask, handle
from app.engine.templates import t
from app.engine.text import fmt_aed
from app.providers.factory import get_provider

router = APIRouter(prefix="/api")


class CartLine(BaseModel):
    id: str = Field(max_length=64)
    name: str = Field(max_length=200)
    price_aed: float
    qty: int = 1


class ChatIn(BaseModel):
    session_id: str | None = None
    message: str = Field(default="", max_length=2000)
    action: str | None = Field(default=None, max_length=80)
    label: str | None = Field(default=None, max_length=120)  # the button text the customer saw, for history
    lang: str | None = None
    cart: list[CartLine] | None = None
    carry_from: str | None = Field(default=None, max_length=64)  # "New chat": the old session, to keep its placed orders


@router.post("/chat")
def chat(body: ChatIn):
    sid = body.session_id or uuid.uuid4().hex[:12]
    data = store.load_session(sid)
    s = Session.from_dict(data) if data else Session(id=sid, lang=body.lang if body.lang in ("en", "ar") else "en")
    if not data and body.carry_from and body.carry_from != sid:
        old = store.load_session(body.carry_from)
        if old and old.get("orders"):  # a fresh conversation, but "where is my order?" keeps working
            s.orders = list(old["orders"])
    prov = get_provider()
    if body.message:
        store.add_message(sid, "user", body.message)
    elif body.action:
        store.add_message(sid, "user", body.label or body.action, "action")
    cart = [c.model_dump() for c in body.cart] if body.cart is not None else None
    reply = handle(s, body.message, body.action, provider=prov, cart=cart, label=body.label)
    store.add_message(sid, "assistant", reply["text"], reply["kind"], payload=reply)
    if reply["event"] == "handoff":
        store.add_handoff(sid, s.handoff_topic, body.message or body.action or "")
        if s.handoff_topic == "order_cancel" and s.orders:  # we already know who to call
            o = s.orders[-1]
            store.update_handoff_contact(sid, o.get("name", ""), o.get("phone", ""), f"Cancel or change order #{o['id']}")
    store.save_session(s.to_dict(), prov.used)
    return {"session_id": sid, "reply": reply,
            "provider": {"requested": prov.requested, "used": prov.used, "errors": prov.errors}}


@router.get("/chat/history")
def chat_history(session_id: str):
    """Restore the chat after a page reload: every message, with the assistant's cards and buttons."""
    if not store.load_session(session_id):
        return {"session_id": session_id, "messages": []}
    return {"session_id": session_id, "messages": store.history(session_id)}


class HandoffIn(BaseModel):
    session_id: str
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=5, max_length=30)
    note: str = Field(default="", max_length=500)


@router.post("/handoff")
def handoff(body: HandoffIn):
    data = store.load_session(body.session_id)
    lang = (data or {}).get("lang", "en")
    store.update_handoff_contact(body.session_id, body.name, body.phone, body.note)
    msg = t(lang, "handoff_saved", name=body.name)
    store.add_message(body.session_id, "assistant", msg, "handoff_saved")
    return {"ok": True, "message": msg}


class OrderItem(BaseModel):
    id: str
    name: str
    price_aed: float
    qty: int = 1


class OrderIn(BaseModel):
    session_id: str | None = None
    items: list[OrderItem]
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=5, max_length=30)
    emirate: str = Field(min_length=2, max_length=40)
    area: str = Field(default="", max_length=80)
    slot: str = Field(default="", max_length=40)


@router.post("/orders")
def order(body: OrderIn):
    if not body.items:
        raise HTTPException(400, "The cart is empty")
    from app.engine.state import clean_cart
    items = clean_cart([i.model_dump() for i in body.items])  # catalogue prices only, never the browser's
    if not items:
        raise HTTPException(400, "The cart has no valid products")
    total = sum(i["price_aed"] * i["qty"] for i in items)
    oid = store.add_order(body.session_id, items, total,
                          body.name, body.phone, body.emirate, body.area, body.slot)
    lang, message = "en", None
    data = store.load_session(body.session_id) if body.session_id else None
    if data:  # the chat remembers the order: "where is my order?", "cancel my order"
        s = Session.from_dict(data)
        lang = s.lang
        s.orders.append({"id": oid, "ids": [i["id"] for i in items], "items": [i["name"] + (f" x{i['qty']}" if i["qty"] > 1 else "") for i in items],
                         "total": total, "name": body.name, "phone": body.phone, "emirate": body.emirate,
                         "when": time.strftime("%Y-%m-%d %H:%M")})
        s.cart, s.awaiting = [], ""
        if not s.name:
            s.name = body.name.split()[0][:30]
        message = t(lang, "order_placed", id=oid, total=fmt_aed(total, lang), phone=_mask(body.phone),
                    name_part=f", {s.name}" if s.name else "")
        s.history.append({"role": "assistant", "text": message})
        store.save_session(s.to_dict(), "rule")
        store.add_message(body.session_id, "assistant", message, "order",
                          payload={"text": message, "cards": [], "quick_replies": [], "lang": lang,
                                   "dir": "rtl" if lang == "ar" else "ltr", "event": "order", "kind": "order"})
    message = message or t(lang, "order_placed", id=oid, total=fmt_aed(total, lang), phone=_mask(body.phone), name_part="")
    return {"ok": True, "order_id": oid, "total": total, "message": message,
            "payment": "Cash on delivery (demo: no real order is placed)"}
