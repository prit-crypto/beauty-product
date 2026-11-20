"use client";

import Link from "next/link";
import { useState } from "react";

import { aed } from "@/lib/api";
import { useCart } from "@/lib/cart";
import type { CardProduct, Routine, RoutineStep } from "@/lib/types";

const L = {
  en: { routine: "Your routine", premium: "Premium routine", total: "Total", left: "Left out to fit your budget", extras: "Optional extras",
        add: "Add routine to cart", addOne: "Add", inCart: "In cart", allIn: "Routine is in your cart · View cart", caution: "Supplement: check with Dr. Shaymaa's team first", view: "View",
        price: "Price", size: "Size", when: "When", madeIn: "Made in", what: "What it does",
        time: { am: "Morning", pm: "Evening", both: "Morning & evening", weekly: "Once or twice a week" } },
  ar: { routine: "روتينكِ", premium: "الروتين الفاخر", total: "المجموع", left: "مستبعد لتناسب الميزانية", extras: "إضافات اختيارية",
        add: "أضيفي الروتين للسلة", addOne: "أضيفي", inCart: "في السلة", allIn: "الروتين في سلتكِ · عرض السلة", caution: "مكمل: يُرجى التأكد مع فريق الدكتورة شيماء أولاً", view: "عرض",
        price: "السعر", size: "الحجم", when: "متى", madeIn: "بلد الصنع", what: "الفائدة",
        time: { am: "صباحاً", pm: "مساءً", both: "صباحاً ومساءً", weekly: "مرة أو مرتين أسبوعياً" } },
};

type AddFn = (id: string, name: string) => void;

/** Products already in the cart show "✓ In cart" instead of a buy button. */
function useInCart() {
  const { items } = useCart();
  return (id: string) => items.some((i) => i.id === id);
}

/** Product description in the chat's language (Arabic summaries were reviewed for claims). */
const desc = (p: { summary: string; summary_ar?: string | null }, lang: "en" | "ar") => (lang === "ar" && p.summary_ar) || p.summary;

/** Product photo thumbnail, or the gold DR placeholder until a photo is added to public/products/. */
function Thumb({ src, size = 48 }: { src?: string | null; size?: number }) {
  if (src)
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={src} alt="" width={size} height={size} loading="lazy" className="shrink-0 rounded-md object-cover bg-cream border border-line" style={{ width: size, height: size }} />
    );
  return (
    <div className="shrink-0 rounded-md gold-sheen border border-line grid place-items-center font-serif text-gold font-bold text-[11px]" style={{ width: size, height: size }}>
      DR
    </div>
  );
}

function Step({ s, lang, muted = false, onAddItem }: { s: RoutineStep; lang: "en" | "ar"; muted?: boolean; onAddItem?: AddFn }) {
  const inCart = useInCart()(s.id);
  const [added, setAdded] = useState(false);
  return (
    <li className={`py-2.5 flex gap-3 ${muted ? "opacity-60" : ""}`}>
      {s.image && <Thumb src={s.image} size={40} />}
      <span className="shrink-0 mt-0.5 text-[10px] uppercase tracking-wider bg-cream border border-line text-gold-dark rounded px-1.5 py-0.5 h-fit">
        {s.slot_label}
      </span>
      <div className="flex-1 min-w-0">
        <Link href={`/product/${s.id}`} className={`font-semibold text-[13.5px] leading-snug hover:text-gold-dark ${muted ? "line-through" : ""}`} dir="ltr">
          {s.name}
        </Link>
        <p className="text-[12px] text-muted leading-snug mt-0.5" dir="auto">{desc(s, lang)}</p>
        {(s.for_labels?.length || s.note_label) ? (
          <p className="text-[11px] text-gold-dark mt-1">
            {s.for_labels?.length ? `${lang === "ar" ? "لـ" : "For"}: ${s.for_labels.join(lang === "ar" ? "، " : ", ")}` : ""}
            {s.for_labels?.length && s.note_label ? " · " : ""}
            {s.note_label}
          </p>
        ) : null}
        {s.caution && <p className="text-[11px] text-[#8a5a00] mt-1">{L[lang].caution}</p>}
      </div>
      <div className="text-end shrink-0">
        <p className="text-[13px] text-gold-dark font-semibold whitespace-nowrap">{aed(s.price_aed)}</p>
        {onAddItem && !s.handoff && inCart && <p className="mt-1 text-[11px] text-[#2f4a32]">✓ {L[lang].inCart}</p>}
        {onAddItem && !s.handoff && !inCart && (
          <button
            className="mt-1 text-[11px] btn-outline rounded-full px-2 py-0.5 disabled:opacity-60"
            disabled={added}
            onClick={() => {
              setAdded(true);
              onAddItem(s.id, s.name);
            }}
          >
            {added ? "✓" : `+ ${L[lang].addOne}`}
          </button>
        )}
      </div>
    </li>
  );
}

export function RoutineCard({ routine, lang, onAdd, onAddItem }: { routine: Routine; lang: "en" | "ar"; onAdd: () => void; onAddItem: AddFn }) {
  const t = L[lang];
  const inCart = useInCart();
  const allIn = routine.steps.length > 0 && routine.steps.every((s) => inCart(s.id));
  return (
    <div className="ms-9 bg-white border border-gold/50 rounded-xl overflow-hidden">
      <div className={`px-3.5 py-2 flex items-center justify-between ${routine.tier === "premium" ? "bg-[#14110b] text-gold-light" : "bg-cream text-gold-dark"}`}>
        <span className="font-serif text-[15px]">{routine.tier === "premium" ? t.premium : t.routine}</span>
        <span className="text-[13px] font-semibold">{t.total}: {aed(routine.total)}</span>
      </div>
      <ul className="px-3.5 divide-y divide-line">
        {routine.steps.map((s) => (
          <Step key={s.id + s.slot} s={s} lang={lang} />
        ))}
      </ul>
      {routine.dropped.length > 0 && (
        <div className="px-3.5 pb-1">
          <p className="text-[11px] uppercase tracking-wider text-muted pt-2">{t.left}</p>
          <ul className="divide-y divide-line">
            {routine.dropped.map((s) => (
              <Step key={s.id} s={s} lang={lang} muted onAddItem={onAddItem} />
            ))}
          </ul>
        </div>
      )}
      {routine.addons.length > 0 && (
        <div className="px-3.5 pb-1 bg-cream/60">
          <p className="text-[11px] uppercase tracking-wider text-muted pt-2">{t.extras}</p>
          <ul className="divide-y divide-line">
            {routine.addons.map((s) => (
              <Step key={s.id + s.slot} s={s} lang={lang} onAddItem={onAddItem} />
            ))}
          </ul>
        </div>
      )}
      <div className="p-3 border-t border-line">
        {allIn ? (
          <Link href="/cart" className="block text-center w-full rounded-full py-2 text-[14px] bg-[#eef3ee] border border-[#c9d8c9] text-[#2f4a32]">
            ✓ {t.allIn}
          </Link>
        ) : (
          <button onClick={onAdd} className="w-full btn-gold rounded-full py-2 text-[14px]">
            {t.add} · {aed(routine.total)}
          </button>
        )}
      </div>
    </div>
  );
}

function AddOrView({ p, lang, onAdd, small = false }: { p: CardProduct; lang: "en" | "ar"; onAdd: AddFn; small?: boolean }) {
  const inCart = useInCart()(p.id);
  const [added, setAdded] = useState(false);
  const cls = small ? "px-2.5 py-1 text-[11px]" : "px-3 py-1.5 text-[12px]";
  if (inCart && !added)
    return <Link href="/cart" className={`rounded-full whitespace-nowrap bg-[#eef3ee] border border-[#c9d8c9] text-[#2f4a32] ${cls}`}>✓ {L[lang].inCart}</Link>;
  if (p.handoff || p.caution)
    return <Link href={`/product/${p.id}`} className={`btn-outline rounded-full ${cls}`}>{L[lang].view}</Link>;
  return (
    <button
      disabled={added}
      className={`btn-gold rounded-full ${cls} disabled:opacity-60`}
      onClick={() => {
        setAdded(true);
        onAdd(p.id, p.name);
      }}
    >
      {added ? "✓" : L[lang].addOne}
    </button>
  );
}

export function ProductMini({ product, lang, onAdd }: { product: CardProduct; lang: "en" | "ar"; onAdd: AddFn }) {
  return (
    <div className="ms-9 bg-white border border-line rounded-xl p-3 flex gap-3 items-center">
      <Thumb src={product.image} />
      <div className="flex-1 min-w-0" dir="ltr">
        <p className="text-[10px] uppercase tracking-wider text-gold-dark">{product.line}</p>
        <Link href={`/product/${product.id}`} className="text-[13.5px] font-semibold leading-snug hover:text-gold-dark">{product.name}</Link>
        <p className="text-[13px] text-gold-dark font-semibold">{aed(product.price_aed)}</p>
      </div>
      <AddOrView p={product} lang={lang} onAdd={onAdd} />
    </div>
  );
}

export function ProductList({ items, lang, onAdd }: { items: CardProduct[]; lang: "en" | "ar"; onAdd: AddFn }) {
  return (
    <ol className="ms-9 bg-white border border-line rounded-xl divide-y divide-line overflow-hidden">
      {items.map((p, i) => (
        <li key={p.id} className="px-3 py-2.5 flex gap-3 items-center">
          <span className="shrink-0 w-6 h-6 rounded-full border border-gold text-gold text-[11px] grid place-items-center font-semibold">{i + 1}</span>
          {p.image && <Thumb src={p.image} size={40} />}
          <div className="flex-1 min-w-0" dir="ltr">
            <Link href={`/product/${p.id}`} className="text-[13px] font-semibold leading-snug hover:text-gold-dark">{p.name}</Link>
            <p className="text-[11.5px] text-muted leading-snug" dir="auto">{desc(p, lang)}</p>
          </div>
          <div className="text-end shrink-0 space-y-1">
            <p className="text-[12.5px] text-gold-dark font-semibold whitespace-nowrap">{aed(p.price_aed)}</p>
            <AddOrView p={p} lang={lang} onAdd={onAdd} small />
          </div>
        </li>
      ))}
    </ol>
  );
}

export function CompareCard({ items, lang, onAdd }: { items: CardProduct[]; lang: "en" | "ar"; onAdd: AddFn }) {
  const t = L[lang];
  const rows: [string, (p: CardProduct) => React.ReactNode][] = [
    [t.price, (p) => <span className="text-gold-dark font-semibold">{aed(p.price_aed)}</span>],
    [t.when, (p) => t.time[p.time as keyof typeof t.time] ?? "—"],
    [t.size, (p) => p.size || "—"],
    [t.madeIn, (p) => p.origin || "—"],
    [t.what, (p) => <span dir="auto">{desc(p, lang)}</span>],
  ];
  return (
    <div className="ms-9 bg-white border border-gold/50 rounded-xl overflow-x-auto">
      <table className="w-full text-[12px] align-top">
        <thead>
          <tr className="bg-cream">
            <th className="w-[70px]" />
            {items.map((p) => (
              <th key={p.id} className="text-start font-semibold px-2 py-2 text-[12.5px] leading-snug" dir="ltr">
                <Link href={`/product/${p.id}`} className="hover:text-gold-dark">{p.name}</Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map(([label, cell]) => (
            <tr key={label}>
              <td className="px-2 py-1.5 text-muted uppercase tracking-wider text-[10px] align-top">{label}</td>
              {items.map((p) => (
                <td key={p.id} className="px-2 py-1.5 align-top leading-snug">{cell(p)}</td>
              ))}
            </tr>
          ))}
          <tr>
            <td />
            {items.map((p) => (
              <td key={p.id} className="px-2 py-2"><AddOrView p={p} lang={lang} onAdd={onAdd} small /></td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

const EMIRATES = ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"];

/** Cash-on-delivery order form inside the chat. Places the order, then empties the cart. */
export function CheckoutCard({ items, total, sessionId, lang, onPlaced, placed = false }: {
  items: { id: string; name: string; price_aed: number; qty?: number }[]; total: number; sessionId: string | null;
  lang: "en" | "ar"; onPlaced: (message: string) => void; placed?: boolean;
}) {
  const t = lang === "ar"
    ? { title: "إتمام الطلب", name: "الاسم الكامل", phone: "رقم الهاتف", area: "المنطقة / المبنى", place: "تأكيد الطلب", cod: "الدفع نقداً عند الاستلام", err: "تعذر إرسال الطلب، حاولي مجدداً.", total: "المجموع", demo: "عرض تجريبي: لا يتم إرسال طلب حقيقي.", placed: "تم تأكيد الطلب" }
    : { title: "Check out", name: "Full name", phone: "Phone (e.g. +971 50 000 0000)", area: "Area / building", place: "Place order", cod: "Cash on delivery", err: "Couldn't place the order. Please try again.", total: "Total", demo: "Concept demo: no real order is placed.", placed: "Order placed" };
  const [form, setForm] = useState({ name: "", phone: "", emirate: "Dubai", area: "" });
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">(placed ? "done" : "idle");
  const [msg, setMsg] = useState("");
  // the full confirmation is added as a chat message; the form itself just collapses
  if (state === "done")
    return <p className="ms-9 bg-[#eef3ee] border border-[#c9d8c9] text-[#2f4a32] rounded-xl px-3.5 py-2 text-[13px]" title={msg}>✓ {t.placed}</p>;
  return (
    <form
      className="ms-9 bg-white border border-gold/50 rounded-xl overflow-hidden"
      onSubmit={async (e) => {
        e.preventDefault();
        setState("sending");
        try {
          const r = await fetch("/api/orders", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, items: items.map((i) => ({ ...i, qty: i.qty ?? 1 })), ...form }),
          });
          if (!r.ok) throw new Error();
          const d = await r.json();
          setMsg(d.message);
          setState("done");
          onPlaced(d.message);
        } catch {
          setState("error");
        }
      }}
    >
      <div className="bg-cream px-3.5 py-2 flex justify-between items-center">
        <span className="font-serif text-[15px] text-gold-dark">{t.title}</span>
        <span className="text-[13px] font-semibold text-gold-dark">{t.total}: {aed(total)}</span>
      </div>
      <ul className="px-3.5 py-2 text-[12.5px] divide-y divide-line" dir="ltr">
        {items.map((i) => (
          <li key={i.id} className="py-1 flex justify-between gap-2">
            <span>{i.name}{(i.qty ?? 1) > 1 ? ` ×${i.qty}` : ""}</span>
            <span className="text-gold-dark whitespace-nowrap">{aed(i.price_aed * (i.qty ?? 1))}</span>
          </li>
        ))}
      </ul>
      <div className="p-3 space-y-2 border-t border-line">
        <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={t.name} className="w-full rounded-md border border-line px-3 py-2 text-[13px]" />
        <input required minLength={5} inputMode="tel" dir="ltr" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder={t.phone} className="w-full rounded-md border border-line px-3 py-2 text-[13px]" />
        <div className="flex gap-2">
          <select value={form.emirate} onChange={(e) => setForm({ ...form, emirate: e.target.value })} aria-label="Emirate" className="flex-1 rounded-md border border-line px-2 py-2 text-[13px] bg-white">
            {EMIRATES.map((x) => <option key={x}>{x}</option>)}
          </select>
          <input value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} placeholder={t.area} className="flex-1 min-w-0 rounded-md border border-line px-3 py-2 text-[13px]" />
        </div>
        {state === "error" && <p className="text-[12px] text-red-700">{t.err}</p>}
        <button disabled={state === "sending"} className="w-full btn-gold rounded-full py-2 text-[13.5px] disabled:opacity-60">{t.place} · {t.cod}</button>
        <p className="text-[10.5px] text-muted text-center">{t.demo}</p>
      </div>
    </form>
  );
}

export function HandoffCard({ sessionId, lang }: { sessionId: string | null; lang: "en" | "ar" }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  const t = lang === "ar"
    ? { title: "تواصل مع فريق الدكتورة شيماء", name: "الاسم", phone: "رقم الهاتف", note: "ملاحظة (اختياري)", send: "إرسال", err: "تعذر الإرسال، حاولي مجدداً." }
    : { title: "Talk to Dr. Shaymaa's team", name: "Name", phone: "Phone number", note: "Note (optional)", send: "Send to the team", err: "Couldn't send. Please try again." };

  if (state === "done") return <p className="ms-9 bg-[#eef3ee] border border-[#c9d8c9] text-[#2f4a32] rounded-xl px-3.5 py-2.5 text-[13.5px]">{msg}</p>;
  return (
    <form
      className="ms-9 bg-[#f4f4f1] border border-[#d9d6cc] rounded-xl p-3 space-y-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!sessionId) return;
        setState("sending");
        try {
          const r = await fetch("/api/handoff", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, name, phone, note }) });
          if (!r.ok) throw new Error();
          const d = await r.json();
          setMsg(d.message);
          setState("done");
        } catch {
          setState("error");
        }
      }}
    >
      <p className="text-[13px] font-semibold text-ink flex items-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden><path d="M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10Z" /></svg>
        {t.title}
      </p>
      <input required value={name} onChange={(e) => setName(e.target.value)} placeholder={t.name} className="w-full rounded-md border border-[#d9d6cc] px-3 py-2 text-[13px] bg-white" />
      <input required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={t.phone} inputMode="tel" minLength={5} className="w-full rounded-md border border-[#d9d6cc] px-3 py-2 text-[13px] bg-white" dir="ltr" />
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t.note} className="w-full rounded-md border border-[#d9d6cc] px-3 py-2 text-[13px] bg-white" />
      {state === "error" && <p className="text-[12px] text-red-700">{t.err}</p>}
      <button disabled={state === "sending"} className="w-full rounded-full bg-ink text-white py-2 text-[13px] disabled:opacity-60">{t.send}</button>
    </form>
  );
}
