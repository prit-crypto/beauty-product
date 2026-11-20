"use client";

import Link from "next/link";
import { useState } from "react";

import ProductVisual from "@/components/ProductVisual";
import { aed } from "@/lib/api";
import { askDrBeauty, useCart } from "@/lib/cart";

const EMIRATES = ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"];
const SLOTS = ["Morning (9am to 1pm)", "Afternoon (1pm to 5pm)", "Evening (5pm to 9pm)"];

export default function CartPage() {
  const { items, total, setQty, clear } = useCart();
  const [form, setForm] = useState({ name: "", phone: "", emirate: "Dubai", area: "", slot: SLOTS[0] });
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [orderId, setOrderId] = useState<number | null>(null);

  const placeOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("sending");
    try {
      let session_id: string | null = null;
      try {
        session_id = localStorage.getItem("drbeauty-demo-session"); // same conversation as the chat
      } catch {
        session_id = null;
      }
      const r = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id, items, ...form }),
      });
      if (!r.ok) throw new Error();
      const d = await r.json();
      setOrderId(d.order_id);
      setStatus("done");
      clear();
    } catch {
      setStatus("error");
    }
  };

  if (status === "done")
    return (
      <section className="mx-auto max-w-2xl px-4 py-20 text-center">
        <div className="w-16 h-16 mx-auto rounded-full border-2 border-gold text-gold grid place-items-center text-2xl">✓</div>
        <h1 className="font-serif text-[34px] mt-6">Thank you, {form.name}</h1>
        <p className="text-muted mt-3">
          Demo order #{orderId} recorded with cash on delivery to {form.area ? `${form.area}, ` : ""}{form.emirate}. In the live
          store you would get a confirmation message the day before delivery.
        </p>
        <p className="text-[12px] text-muted mt-6">Concept demo: no real order has been placed.</p>
        <Link href="/" className="inline-block mt-8 btn-gold rounded-full px-6 py-3">Back to the shop</Link>
      </section>
    );

  return (
    <section className="mx-auto max-w-6xl px-4 py-12">
      <h1 className="font-serif text-[40px]">Shopping Cart</h1>
      {items.length === 0 ? (
        <div className="mt-8 rounded-xl border border-line bg-cream p-10 text-center">
          <p className="text-muted">Your cart is empty.</p>
          <div className="mt-6 flex justify-center gap-3 flex-wrap">
            <Link href="/category/skincare" className="btn-gold rounded-full px-6 py-3 text-[14px]">Shop skincare</Link>
            <button onClick={() => askDrBeauty()} className="btn-outline rounded-full px-6 py-3 text-[14px]">Ask Dr. Beauty for a routine</button>
          </div>
        </div>
      ) : (
        <div className="mt-8 grid lg:grid-cols-[1fr_380px] gap-10">
          <ul className="divide-y divide-line border-y border-line">
            {items.map((it) => (
              <li key={it.id} className="py-4 flex items-center gap-4">
                <div className="w-20 shrink-0"><ProductVisual line="" name={it.name} compact /></div>
                <div className="flex-1 min-w-0">
                  <Link href={`/product/${it.id}`} className="font-serif text-[17px] hover:text-gold-dark">{it.name}</Link>
                  <p className="text-[13px] text-muted">{aed(it.price_aed)} each</p>
                </div>
                <div className="flex items-center border border-line rounded-full">
                  <button className="px-3 py-1" onClick={() => setQty(it.id, it.qty - 1)} aria-label={`Fewer ${it.name}`}>−</button>
                  <span className="w-6 text-center text-[14px]">{it.qty}</span>
                  <button className="px-3 py-1" onClick={() => setQty(it.id, it.qty + 1)} aria-label={`More ${it.name}`}>+</button>
                </div>
                <p className="w-24 text-end font-semibold text-gold-dark">{aed(it.price_aed * it.qty)}</p>
              </li>
            ))}
          </ul>
          <form onSubmit={placeOrder} className="rounded-xl border border-line bg-cream p-6 h-fit space-y-3">
            <div className="flex justify-between text-[18px]">
              <span className="font-serif">Total</span>
              <span className="font-semibold text-gold-dark">{aed(total)}</span>
            </div>
            <p className="text-[12px] text-muted">Pay with cash on delivery</p>
            <div className="gold-rule my-2" />
            <input required placeholder="Full name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full rounded-md border border-line px-3 py-2.5 bg-white text-[14px]" />
            <input required minLength={5} placeholder="Phone (e.g. +971 50 000 0000)" inputMode="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full rounded-md border border-line px-3 py-2.5 bg-white text-[14px]" />
            <select value={form.emirate} onChange={(e) => setForm({ ...form, emirate: e.target.value })} className="w-full rounded-md border border-line px-3 py-2.5 bg-white text-[14px]" aria-label="Emirate">
              {EMIRATES.map((x) => <option key={x}>{x}</option>)}
            </select>
            <input placeholder="Area / building" value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })} className="w-full rounded-md border border-line px-3 py-2.5 bg-white text-[14px]" />
            <select value={form.slot} onChange={(e) => setForm({ ...form, slot: e.target.value })} className="w-full rounded-md border border-line px-3 py-2.5 bg-white text-[14px]" aria-label="Delivery time">
              {SLOTS.map((x) => <option key={x}>{x}</option>)}
            </select>
            {status === "error" && <p className="text-[13px] text-red-700">Couldn&apos;t place the order. Please try again.</p>}
            <button disabled={status === "sending"} className="w-full btn-gold rounded-full py-3 text-[14px] uppercase tracking-[0.12em] disabled:opacity-60">
              Place order · Cash on delivery
            </button>
            <p className="text-[11px] text-muted text-center">Concept demo: no real order is placed.</p>
          </form>
        </div>
      )}
    </section>
  );
}
