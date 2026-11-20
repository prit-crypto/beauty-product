"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type CartItem = { id: string; name: string; price_aed: number; qty: number };

type CartCtx = {
  items: CartItem[];
  count: number;
  total: number;
  add: (items: Omit<CartItem, "qty">[]) => void;
  setQty: (id: string, qty: number) => void;
  remove: (ids: string[]) => void;
  clear: () => void;
};

const Ctx = createContext<CartCtx | null>(null);
const KEY = "drbeauty-demo-cart";

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setItems(JSON.parse(raw));
    } catch {
      /* storage unavailable: cart works for this page view only */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch {
      /* ignore */
    }
  }, [items]);

  const add = useCallback((newItems: Omit<CartItem, "qty">[]) => {
    setItems((cur) => {
      let next = cur;
      for (const it of newItems) {
        next = next.some((x) => x.id === it.id)
          ? next.map((x) => (x.id === it.id ? { ...x, qty: x.qty + 1 } : x))
          : [...next, { ...it, qty: 1 }];
      }
      return next;
    });
    window.dispatchEvent(new CustomEvent("cart-bump"));
  }, []);

  const setQty = useCallback((id: string, qty: number) => {
    setItems((cur) => (qty <= 0 ? cur.filter((x) => x.id !== id) : cur.map((x) => (x.id === id ? { ...x, qty } : x))));
  }, []);

  const remove = useCallback((ids: string[]) => setItems((cur) => cur.filter((x) => !ids.includes(x.id))), []);
  const clear = useCallback(() => setItems([]), []);

  const value = useMemo(
    () => ({
      items,
      count: items.reduce((s, x) => s + x.qty, 0),
      total: items.reduce((s, x) => s + x.qty * x.price_aed, 0),
      add,
      setQty,
      remove,
      clear,
    }),
    [items, add, setQty, remove, clear],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useCart must be used inside CartProvider");
  return c;
}

/** Opens the chat widget, optionally sending a first message (e.g. "Tell me about Hair Elixir"). */
export function askDrBeauty(message?: string) {
  window.dispatchEvent(new CustomEvent("ask-dr-beauty", { detail: { message } }));
}
