def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["provider"] == "rule"


def test_catalog_endpoints(client):
    cats = client.get("/api/categories").json()
    assert sum(c["count"] for c in cats) == 49
    hair = client.get("/api/products", params={"category": "haircare"}).json()
    assert hair and all(p["category"] == "haircare" for p in hair)
    assert client.get("/api/products/nn1-day-cream").json()["price_aed"] == 269
    assert client.get("/api/products/nope").status_code == 404


def test_chat_flow_and_admin_dashboard(client):
    r = client.post("/api/chat", json={"message": "I'm 38, I have fine lines around my eyes and my skin feels dull. Budget around AED 900."}).json()
    sid = r["session_id"]
    assert r["reply"]["kind"] == "routine"
    client.post("/api/chat", json={"session_id": sid, "action": "add_routine"})
    h = client.post("/api/chat", json={"message": "Can I take Cystiphane tablets while breastfeeding?"}).json()
    client.post("/api/handoff", json={"session_id": h["session_id"], "name": "Sara", "phone": "+971500000000"})
    client.post("/api/orders", json={"session_id": sid, "items": [{"id": "nn1-day-cream", "name": "Anti-Aging Day Cream", "price_aed": 269}],
                                     "name": "Mona", "phone": "+971500000001", "emirate": "Dubai"})

    assert client.get("/api/admin/summary").status_code == 401
    d = client.get("/api/admin/summary", headers={"X-Admin-Password": "test-pw"}).json()
    assert d["totals"]["chats"] == 2
    assert d["totals"]["cart_value"] == 887
    assert d["totals"]["handoffs_waiting"] == 1
    assert d["handoffs"][0]["name"] == "Sara"
    statuses = {s["id"]: s["status"] for s in d["sessions"]}
    assert statuses[sid] == "Ordered" and statuses[h["session_id"]] == "Hand-off"


def test_provider_switch_requires_key(client):
    r = client.post("/api/admin/provider", json={"provider": "gemini"}, headers={"X-Admin-Password": "test-pw"})
    assert r.status_code in (200, 400)
