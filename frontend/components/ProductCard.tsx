import Link from "next/link";

import { aed } from "@/lib/api";
import type { Product } from "@/lib/types";

import { AddToCart } from "./ProductButtons";
import ProductVisual from "./ProductVisual";

export default function ProductCard({ p }: { p: Product }) {
  return (
    <article className="group flex flex-col">
      <Link href={`/product/${p.id}`} className="block">
        <ProductVisual line={p.line} name={p.name} size={p.size} image={p.image} />
      </Link>
      <div className="pt-3 flex-1 flex flex-col">
        <p className="uppercase tracking-[0.14em] text-[10px] text-gold-dark">{p.line}</p>
        <Link href={`/product/${p.id}`} className="font-serif text-[17px] leading-snug mt-1 group-hover:text-gold-dark">
          {p.name}
        </Link>
        {p.origin && <p className="text-[11px] text-muted mt-1">Made in {p.origin}</p>}
        <div className="mt-auto pt-3 flex items-center justify-between gap-2">
          <span className="text-gold-dark font-semibold">{aed(p.price_aed)}</span>
          <AddToCart id={p.id} name={p.name} price={p.price_aed} className="!px-3 !py-1.5 !text-[12px]" />
        </div>
      </div>
    </article>
  );
}
