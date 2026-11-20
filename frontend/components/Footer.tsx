import Image from "next/image";
import Link from "next/link";

import { NAV } from "@/lib/nav";

export default function Footer() {
  return (
    <footer className="bg-[#111] text-[#d8d2c4] mt-0">
      <div className="mx-auto max-w-6xl px-4 py-12 grid gap-10 md:grid-cols-3">
        <div>
          <div className="bg-white inline-block rounded-md p-2">
            <Image src="/brand/logo.png" alt="Dr. Beauty Care" width={110} height={85} className="h-[64px] w-auto" />
          </div>
          <p className="mt-4 text-sm leading-relaxed max-w-xs">
            Skincare, haircare, protein and supplements, selected with Dr. Shaymaa Abdel Nabi&apos;s scientific approach.
          </p>
        </div>
        <div>
          <h4 className="text-white uppercase tracking-[0.14em] text-[13px] mb-4">Products</h4>
          <ul className="grid gap-2 text-sm">
            {NAV.slice(0, 5).map((n) => (
              <li key={n.href}>
                <Link href={n.href} className="hover:text-gold-light">
                  {n.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-white uppercase tracking-[0.14em] text-[13px] mb-4">Useful links</h4>
          <ul className="grid gap-2 text-sm">
            <li><Link href="/about" className="hover:text-gold-light">About</Link></li>
            <li><Link href="/cart" className="hover:text-gold-light">Cart</Link></li>
            <li><Link href="/contact" className="hover:text-gold-light">Contact Us</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-6xl px-4 py-4 text-[12px] text-[#9a9384]">
          Concept demo prepared for Dr. Beauty Care. Not affiliated with or endorsed by Dr. Beauty Care. Brand names and
          logos belong to their owners.
        </p>
      </div>
    </footer>
  );
}
