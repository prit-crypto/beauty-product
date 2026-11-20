"use client";

import { useCallback, useEffect, useState } from "react";

import { aed } from "@/lib/api";

type Session = {
  id: string; updated_at: number; lang: string; provider: string; area: string | null; concerns: string[] | null;
  budget: number | null; cart_value: number; routine_total: number | null; routine_items: string[]; messages: number;
  last_message: string; status: string; handoff_topic: string;
};
type Handoff = { id: number; session_id: string; category: string; message: string; name: string | null; phone: string | null; note: string | null; status: string; created_at: number };
type Order = { id: number; session_id: string | null; items: { name: string; qty: number }[]; total: number; name: string; emirate: string; area: string; created_at: number };
type Summary = {
  sessions: Session[]; handoffs: Handoff[]; orders: Order[]; top_concerns: [string, number][];
  totals: { chats: number; routines: number; cart_value: number; orders: number; order_value: number; handoffs_waiting: number };
  provider: { active: string; available: Record<string, boolean> };
};

const PW_KEY = "drbeauty-admin-pw";
const when = (t: number) => new Date(t * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const STATUS_STYLE: Record<string, string> = {
  "Hand-off": "bg-[#f4e6e6] text-[#7a2e2e]", Ordered: "bg-[#e5f0e5] text-[#2f5a32]", "Added to cart": "bg-[#f6ecd6] text-[#7a5410]",
  "Routine shown": "bg-cream text-gold-dark", Browsing: "bg-[#efefef] text-[#555]",
};

export default function Admin() {
  const [pw, setPw] = useState("");
  const [data, setData] = useState<Summary | null>(null);
  const [err, setErr] = useState("");

  const load = useCallback(async (password: string) => {
    const r = await fetch("/api/admin/summary", { headers: { "X-Admin-Password": password } });
    if (r.status === 401) {
      setErr("Wrong password");
      setData(null);
      return;
    }
    if (!r.ok) {
      setErr("Couldn't load the dashboard. Is the backend running?");
      return;
    }
    setErr("");
    setData(await r.json());
    try { sessionStorage.setItem(PW_KEY, password); } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    let saved = "";
    try { saved = sessionStorage.getItem(PW_KEY) || ""; } catch { /* ignore */ }
    if (saved) { setPw(saved); load(saved); }
  }, [load]);

  useEffect(() => {
    if (!data) return;
    const t = setInterval(() => load(pw), 8000);
    return () => clearInterval(t);
  }, [data, pw, load]);

  const switchProvider = async (name: string) => {
    const r = await fetch("/api/admin/provider", { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Password": pw }, body: JSON.stringify({ provider: name }) });
    if (!r.ok) setErr((await r.json()).detail || "Couldn't switch");
    load(pw);
  };

  if (!data)
    return (
      <section className="mx-auto max-w-sm px-4 py-24">
        <h1 className="font-serif text-[32px]">Owner dashboard</h1>
        <p className="text-muted text-[14px] mt-2">Ask Dr. Beauty conversations, routines, carts and hand-offs.</p>
        <form className="mt-6 space-y-3" onSubmit={(e) => { e.preventDefault(); load(pw); }}>
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Password" className="w-full rounded-md border border-line px-3 py-2.5" />
          {err && <p className="text-[13px] text-red-700">{err}</p>}
          <button className="w-full btn-gold rounded-full py-2.5">Open dashboard</button>
        </form>
      </section>
    );

  const t = data.totals;
  const maxC = Math.max(1, ...data.top_concerns.map(([, n]) => n));
  const waiting = data.handoffs.filter((h) => h.status === "waiting");

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="uppercase tracking-[0.2em] text-[12px] text-gold-dark">Dr. Beauty Care · Owner view</p>
          <h1 className="font-serif text-[36px]">Today with Ask Dr. Beauty</h1>
        </div>
        <div className="flex items-center gap-2 text-[13px]">
          <span className="text-muted">AI mode</span>
          {Object.entries(data.provider.available).map(([name, ok]) => (
            <button key={name} disabled={!ok} onClick={() => switchProvider(name)}
              title={ok ? `Switch to ${name}` : `No API key configured for ${name}`}
              className={`rounded-full px-3 py-1 border ${data.provider.active === name ? "bg-gold text-white border-gold" : "border-line"} disabled:opacity-40`}>
              {name}
            </button>
          ))}
        </div>
      </div>
      {err && <p className="mt-3 text-[13px] text-red-700">{err}</p>}

      <div className="mt-8 grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          ["Conversations", String(t.chats)],
          ["Routines shown", String(t.routines)],
          ["Added to cart", aed(t.cart_value)],
          ["Orders (COD)", `${t.orders} · ${aed(t.order_value)}`],
          ["Hand-offs waiting", String(t.handoffs_waiting)],
        ].map(([k, v]) => (
          <div key={k} className={`rounded-xl border p-4 ${k === "Hand-offs waiting" && t.handoffs_waiting ? "border-[#d9a0a0] bg-[#fbf1f1]" : "border-line bg-white"}`}>
            <p className="text-[12px] uppercase tracking-[0.12em] text-muted">{k}</p>
            <p className="font-serif text-[26px] mt-1 text-ink">{v}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 grid lg:grid-cols-[1fr_320px] gap-6">
        <div className="rounded-xl border border-line overflow-hidden">
          <h2 className="px-4 py-3 bg-cream font-serif text-[18px] border-b border-line">Hand-offs for Dr. Shaymaa&apos;s team</h2>
          {waiting.length === 0 ? <p className="px-4 py-6 text-muted text-[14px]">No hand-offs waiting.</p> : (
            <ul className="divide-y divide-line">
              {waiting.map((h) => (
                <li key={h.id} className="px-4 py-3 text-[14px]">
                  <div className="flex justify-between gap-3">
                    <span className="font-semibold">{h.name || "Contact details not left yet"} {h.phone && <span className="font-normal text-muted">· {h.phone}</span>}</span>
                    <span className="text-[12px] text-muted shrink-0">{when(h.created_at)}</span>
                  </div>
                  <p className="text-[12px] uppercase tracking-wider text-[#7a2e2e] mt-1">Topic: {h.category}</p>
                  <p className="mt-1 text-muted" dir="auto">&ldquo;{h.message}&rdquo;</p>
                  {h.note && <p className="mt-1 text-[13px]">Note: {h.note}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-line p-4">
          <h2 className="font-serif text-[18px]">Top customer concerns</h2>
          {data.top_concerns.length === 0 ? <p className="text-muted text-[14px] mt-3">No data yet.</p> : (
            <ul className="mt-3 space-y-2">
              {data.top_concerns.map(([label, n]) => (
                <li key={label} className="text-[13px]">
                  <div className="flex justify-between"><span>{label}</span><span className="text-muted">{n}</span></div>
                  <div className="h-2 bg-cream rounded-full mt-1"><div className="h-2 bg-gold rounded-full" style={{ width: `${(n / maxC) * 100}%` }} /></div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-8 rounded-xl border border-line overflow-x-auto">
        <h2 className="px-4 py-3 bg-cream font-serif text-[18px] border-b border-line">Conversations</h2>
        <table className="w-full text-[13px] min-w-[860px]">
          <thead className="text-left text-muted uppercase text-[11px] tracking-wider">
            <tr className="border-b border-line">
              <th className="px-4 py-2">When</th><th className="px-2">Status</th><th className="px-2">Area · concerns</th>
              <th className="px-2">Routine offered</th><th className="px-2 text-right">Routine</th><th className="px-2 text-right">Cart</th>
              <th className="px-2">Lang</th><th className="px-2">AI</th><th className="px-4">Last message</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.sessions.map((s) => (
              <tr key={s.id} className="align-top">
                <td className="px-4 py-2.5 whitespace-nowrap text-muted">{when(s.updated_at)}</td>
                <td className="px-2 py-2.5"><span className={`rounded-full px-2 py-0.5 text-[11px] whitespace-nowrap ${STATUS_STYLE[s.status] || ""}`}>{s.status}</span></td>
                <td className="px-2 py-2.5">{s.area ? <><b className="capitalize">{s.area}</b> · {(s.concerns || []).join(", ").replace(/_/g, " ")}</> : "—"}</td>
                <td className="px-2 py-2.5 max-w-[220px]">{s.routine_items.join(", ") || "—"}</td>
                <td className="px-2 py-2.5 text-right whitespace-nowrap">{s.routine_total ? aed(s.routine_total) : "—"}</td>
                <td className="px-2 py-2.5 text-right whitespace-nowrap">{s.cart_value ? aed(s.cart_value) : "—"}</td>
                <td className="px-2 py-2.5 uppercase">{s.lang}</td>
                <td className="px-2 py-2.5">{s.provider}</td>
                <td className="px-4 py-2.5 max-w-[240px] truncate" dir="auto" title={s.last_message}>{s.last_message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.orders.length > 0 && (
        <div className="mt-8 rounded-xl border border-line overflow-hidden">
          <h2 className="px-4 py-3 bg-cream font-serif text-[18px] border-b border-line">Cash-on-delivery orders (demo)</h2>
          <ul className="divide-y divide-line">
            {data.orders.map((o) => (
              <li key={o.id} className="px-4 py-3 text-[14px] flex flex-wrap justify-between gap-2">
                <span><b>#{o.id}</b> · {o.name} · {o.area ? `${o.area}, ` : ""}{o.emirate}</span>
                <span className="text-muted">{o.items.map((i) => `${i.name} ×${i.qty}`).join(", ")}</span>
                <span className="font-semibold text-gold-dark">{aed(o.total)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-6 text-[12px] text-muted">Refreshes every 8 seconds. Concept demo data only.</p>
    </section>
  );
}
