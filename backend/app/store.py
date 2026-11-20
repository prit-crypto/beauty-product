"""SQLite storage for sessions, messages, hand-offs and mock orders (demo only; no real orders are sent)."""
import json
import sqlite3
import threading
import time
from pathlib import Path

from app.config import settings

_lock = threading.RLock()  # serialises writes (re-entrant: writers call conn() while holding it)
_local = threading.local()  # one connection per thread: a shared connection breaks when two chats arrive at once
_path: str | None = None  # set by reset_for_tests
_ready: set[str] = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, created_at REAL, updated_at REAL, lang TEXT, state_json TEXT, provider TEXT);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, text TEXT, kind TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS handoffs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, category TEXT, message TEXT,
  name TEXT, phone TEXT, note TEXT, status TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, items_json TEXT, total REAL,
  name TEXT, phone TEXT, emirate TEXT, area TEXT, slot TEXT, created_at REAL);
"""


def conn() -> sqlite3.Connection:
    path = _path or settings.db_path
    c = getattr(_local, "conn", None)
    if c is None or getattr(_local, "path", None) != path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=10000")
        with _lock:
            if path not in _ready:
                c.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer
                c.executescript(SCHEMA)
                _migrate(c)
                _ready.add(path)
        _local.conn, _local.path = c, path
    return c


def _migrate(c: sqlite3.Connection) -> None:
    cols = {r[1] for r in c.execute("PRAGMA table_info(messages)")}
    if "payload" not in cols:  # full assistant reply (cards, buttons) so a page reload can restore the chat
        c.execute("ALTER TABLE messages ADD COLUMN payload TEXT")
        c.commit()


def reset_for_tests(path: str) -> None:
    global _path
    _path = path
    _ready.discard(path)


def load_session(sid: str) -> dict | None:
    row = conn().execute("SELECT state_json FROM sessions WHERE id=?", (sid,)).fetchone()
    return json.loads(row["state_json"]) if row else None


def save_session(state: dict, provider: str) -> None:
    now = time.time()
    with _lock:
        c = conn()
        c.execute(
            "INSERT INTO sessions(id, created_at, updated_at, lang, state_json, provider) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, lang=excluded.lang, "
            "state_json=excluded.state_json, provider=excluded.provider",
            (state["id"], now, now, state["lang"], json.dumps(state, ensure_ascii=False), provider))
        c.commit()


def add_message(sid: str, role: str, text: str, kind: str = "text", payload: dict | None = None) -> None:
    with _lock:
        c = conn()
        c.execute("INSERT INTO messages(session_id, role, text, kind, ts, payload) VALUES(?,?,?,?,?,?)",
                  (sid, role, text, kind, time.time(), json.dumps(payload, ensure_ascii=False) if payload else None))
        c.commit()


def history(sid: str, limit: int = 60) -> list[dict]:
    rows = conn().execute("SELECT role, text, kind, payload FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                          (sid, limit)).fetchall()
    out = []
    for r in reversed(rows):
        item = {"role": r["role"], "text": r["text"], "kind": r["kind"]}
        if r["payload"]:
            item["reply"] = json.loads(r["payload"])
        out.append(item)
    return out


def add_handoff(sid: str, category: str, message: str) -> int:
    with _lock:
        c = conn()
        cur = c.execute("INSERT INTO handoffs(session_id, category, message, status, created_at) VALUES(?,?,?,?,?)",
                        (sid, category, message, "waiting", time.time()))
        c.commit()
        return cur.lastrowid


def update_handoff_contact(sid: str, name: str, phone: str, note: str) -> None:
    with _lock:
        c = conn()
        row = c.execute("SELECT id FROM handoffs WHERE session_id=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
        if row:
            c.execute("UPDATE handoffs SET name=?, phone=?, note=? WHERE id=?", (name, phone, note, row["id"]))
        else:
            c.execute("INSERT INTO handoffs(session_id, category, message, name, phone, note, status, created_at) "
                      "VALUES(?,?,?,?,?,?,?,?)", (sid, "request", "", name, phone, note, "waiting", time.time()))
        c.commit()


def add_order(sid: str | None, items: list, total: float, name: str, phone: str, emirate: str, area: str, slot: str) -> int:
    with _lock:
        c = conn()
        cur = c.execute("INSERT INTO orders(session_id, items_json, total, name, phone, emirate, area, slot, created_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?)",
                        (sid, json.dumps(items, ensure_ascii=False), total, name, phone, emirate, area, slot, time.time()))
        c.commit()
        return cur.lastrowid


def summary(limit: int = 50) -> dict:
    c = conn()
    sessions = [dict(r) for r in c.execute("SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,))]
    handoffs = [dict(r) for r in c.execute("SELECT * FROM handoffs ORDER BY created_at DESC LIMIT ?", (limit,))]
    orders = [dict(r) for r in c.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))]
    counts = {r["session_id"]: r["n"] for r in c.execute("SELECT session_id, COUNT(*) n FROM messages GROUP BY session_id")}
    last = {r["session_id"]: r["text"] for r in c.execute(
        "SELECT m.session_id, m.text FROM messages m JOIN (SELECT session_id, MAX(id) mid FROM messages WHERE role='user' "
        "GROUP BY session_id) x ON m.id = x.mid")}
    ordered = {o["session_id"] for o in orders}
    for s in sessions:
        st = json.loads(s.pop("state_json"))
        s.update({k: st.get(k) for k in ("area", "concerns", "budget", "cart_value", "handoff", "handoff_topic", "premium")})
        s["routine_total"] = (st.get("routine") or {}).get("total")
        s["routine_items"] = [x["name"] for x in (st.get("routine") or {}).get("steps", [])]
        s["messages"] = counts.get(s["id"], 0)
        s["last_message"] = last.get(s["id"], "")
        s["status"] = ("Hand-off" if st.get("handoff") else "Ordered" if s["id"] in ordered else
                       "Added to cart" if st.get("cart_value") else "Routine shown" if st.get("routine") else "Browsing")
    for o in orders:
        o["items"] = json.loads(o.pop("items_json"))
    return {"sessions": sessions, "handoffs": handoffs, "orders": orders}
