"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { aed } from "@/lib/api";
import { askDrBeauty, useCart } from "@/lib/cart";
import { NAV } from "@/lib/nav";

export default function Header() {
  const { count, total } = useCart();
  const [open, setOpen] = useState(false);
  const [bump, setBump] = useState(false);

  useEffect(() => {
    const on = () => {
      setBump(true);
      setTimeout(() => setBump(false), 600);
    };
    window.addEventListener("cart-bump", on);
    return () => window.removeEventListener("cart-bump", on);
  }, []);

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-line">
      <div className="mx-auto max-w-6xl px-4 flex items-center gap-4 h-[76px]">
        <Link href="/" className="shrink-0" aria-label="Dr. Beauty Care home">
          <Image src="/brand/logo.png" alt="Dr. Beauty Care" width={92} height={71} priority className="h-[60px] w-auto" />
        </Link>
        <nav className="hidden lg:flex items-center gap-6 mx-auto text-[13px] uppercase tracking-[0.12em]">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className="hover:text-gold transition-colors">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto lg:ml-0 flex items-center gap-3">
          <button onClick={() => askDrBeauty()} className="hidden sm:inline-flex btn-outline rounded-full px-4 py-2 text-[13px]">
            Ask Dr. Beauty
          </button>
          <Link
            href="/cart"
            className={`flex items-center gap-2 text-[13px] ${bump ? "scale-110" : ""} transition-transform`}
            aria-label={`Cart, ${count} items`}
          >
            <span className="text-gold-dark font-semibold">{aed(total)}</span>
            <span className="relative inline-flex">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
                <path d="M6 7h12l-1 13H7L6 7Z" />
                <path d="M9 7a3 3 0 0 1 6 0" />
              </svg>
              <span className="absolute -top-1.5 -right-2 bg-gold text-white rounded-full text-[10px] min-w-[18px] h-[18px] grid place-items-center px-1">
                {count}
              </span>
            </span>
          </Link>
          <button className="lg:hidden p-2" onClick={() => setOpen(!open)} aria-label="Menu" aria-expanded={open}>
            <svg width="22" height="22" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.6" aria-hidden>
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
        </div>
      </div>
      {open && (
        <nav className="lg:hidden border-t border-line bg-white px-4 py-3 grid gap-3 text-sm uppercase tracking-[0.1em]">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} onClick={() => setOpen(false)}>
              {n.label}
            </Link>
          ))}
          <button
            className="btn-gold rounded-full px-4 py-2 text-sm normal-case tracking-normal"
            onClick={() => {
              setOpen(false);
              askDrBeauty();
            }}
          >
            Ask Dr. Beauty
          </button>
        </nav>
      )}
    </header>
  );
}
