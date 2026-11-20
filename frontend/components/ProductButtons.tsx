"use client";

import { useState } from "react";

import { askDrBeauty, useCart } from "@/lib/cart";

export function AddToCart({ id, name, price, className = "" }: { id: string; name: string; price: number; className?: string }) {
  const { add } = useCart();
  const [done, setDone] = useState(false);
  return (
    <button
      className={`btn-gold rounded-full px-4 py-2 text-[13px] ${className}`}
      onClick={() => {
        add([{ id, name, price_aed: price }]);
        setDone(true);
        setTimeout(() => setDone(false), 1400);
      }}
    >
      {done ? "Added" : "Add to cart"}
    </button>
  );
}

export function AskAbout({ name, className = "" }: { name: string; className?: string }) {
  return (
    <button className={`btn-outline rounded-full px-4 py-2 text-[13px] ${className}`} onClick={() => askDrBeauty(`Tell me about ${name}`)}>
      Ask Dr. Beauty
    </button>
  );
}

export function AskStart({ label = "Ask Dr. Beauty", className = "" }: { label?: string; className?: string }) {
  return (
    <button className={className} onClick={() => askDrBeauty()}>
      {label}
    </button>
  );
}
