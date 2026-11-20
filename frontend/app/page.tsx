import Image from "next/image";
import Link from "next/link";

import ProductCard from "@/components/ProductCard";
import { AskStart } from "@/components/ProductButtons";
import TrustBar from "@/components/TrustBar";
import { getCategories, getProducts } from "@/lib/api";

export const dynamic = "force-dynamic";

const FEATURED = ["cana-hydro-serum", "luxliss-argan-collection", "protein-oily-extra-power"];
const CATEGORY_TEXT: Record<string, string> = {
  protein: "Salon-style protein treatments that smooth and strengthen.",
  skincare: "Natural and luxury skincare, from everyday care to Cana Gold 24K.",
  haircare: "Shampoos, conditioners, masks and serums for healthy, vibrant hair.",
  supplements: "Gummies that support hair, skin, immunity and sleep.",
  "anti-hair-loss": "Cystiphane care for hair that sheds easily.",
};

export default async function Home() {
  const [cats, products] = await Promise.all([getCategories(), getProducts()]);
  const featured = FEATURED.map((id) => products.find((p) => p.id === id)).filter(Boolean) as typeof products;

  return (
    <>
      {/* Hero */}
      <section className="gold-sheen border-b border-line">
        <div className="mx-auto max-w-6xl px-4 py-16 md:py-24 grid md:grid-cols-[1.1fr_0.9fr] gap-10 items-center">
          <div>
            <p className="uppercase tracking-[0.22em] text-[12px] text-gold-dark">Dr. Beauty Care · Science-backed beauty</p>
            <h1 className="font-serif text-[44px] md:text-[60px] leading-[1.05] mt-4 text-ink">Elevate Your Wellness</h1>
            <p className="mt-4 text-[18px] text-muted max-w-md">Premium Skincare, Haircare, and Supplements for a Healthier You</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/category/skincare" className="btn-gold rounded-full px-7 py-3 text-[14px] uppercase tracking-[0.14em]">
                Shop now
              </Link>
              <AskStart label="Ask Dr. Beauty" className="btn-outline rounded-full px-7 py-3 text-[14px] uppercase tracking-[0.14em]" />
            </div>
          </div>
          <div className="relative">
            <div className="absolute -inset-4 rounded-full bg-white/50 blur-2xl" aria-hidden />
            <Image src="/brand/logo.png" alt="Dr. Beauty Care crest" width={600} height={463} priority className="relative w-full max-w-[460px] mx-auto h-auto" />
          </div>
        </div>
      </section>

      {/* Ask Dr. Beauty */}
      <section className="mx-auto max-w-6xl px-4 py-16">
        <div className="rounded-2xl border border-gold/40 bg-white p-8 md:p-10 grid md:grid-cols-[1fr_auto] gap-8 items-center">
          <div>
            <p className="uppercase tracking-[0.2em] text-[12px] text-gold-dark">New · Ask Dr. Beauty</p>
            <h2 className="font-serif text-[32px] leading-tight mt-2">Not sure where to start? Get your routine in one minute.</h2>
            <ol className="mt-6 grid sm:grid-cols-3 gap-5 text-[14px]">
              {[
                ["Tell us your concern", "Skin, hair or supplements, in English or Arabic."],
                ["Get a personal routine", "Morning and night steps from Dr. Shaymaa's range, within your budget."],
                ["Order in one tap", "Add the whole routine to your cart and pay on delivery."],
              ].map(([t, d], i) => (
                <li key={t} className="flex gap-3">
                  <span className="w-8 h-8 shrink-0 rounded-full border border-gold text-gold grid place-items-center font-serif font-bold">{i + 1}</span>
                  <span>
                    <span className="block font-bold text-ink">{t}</span>
                    <span className="text-muted">{d}</span>
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-6 text-[13px] text-ink">
              <strong className="font-bold">
                Questions about pregnancy, breastfeeding, medication or health conditions go straight to Dr. Shaymaa&apos;s team.
              </strong>
            </p>
          </div>
          <AskStart label="Start my consultation" className="btn-gold rounded-full px-8 py-4 text-[15px]" />
        </div>
      </section>

      {/* Categories */}
      <section className="mx-auto max-w-6xl px-4 pb-16">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="font-serif text-[34px]">Explore Our Product Categories</h2>
          <div className="gold-rule w-40 mx-auto my-4" />
          <p className="text-muted">
            Dr. Beauty Care offers a comprehensive range of high-quality products designed to cater to your skin, hair, and overall health needs.
          </p>
        </div>
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {cats.map((c) => (
            <Link key={c.slug} href={`/category/${c.slug}`} className="group rounded-xl border border-line bg-cream hover:border-gold p-5 transition-colors">
              <p className="font-serif text-[20px] group-hover:text-gold-dark">{c.en}</p>
              <p className="text-[13px] text-muted mt-2 min-h-[54px]">{CATEGORY_TEXT[c.slug]}</p>
              <p className="text-[12px] uppercase tracking-[0.14em] text-gold-dark mt-3">{c.count} products →</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured */}
      <section className="bg-white border-t border-line">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="font-serif text-[34px] text-center">Customer Favourites</h2>
          <div className="gold-rule w-40 mx-auto my-4" />
          <div className="mt-8 grid sm:grid-cols-3 gap-8">
            {featured.map((p) => (
              <ProductCard key={p.id} p={p} />
            ))}
          </div>
        </div>
      </section>

      {/* About band */}
      <section className="bg-[#14110b] text-[#e9e2d0]">
        <div className="mx-auto max-w-6xl px-4 py-16 grid md:grid-cols-[auto_1fr] gap-10 items-center">
          <div className="w-28 h-28 rounded-full border-2 border-gold grid place-items-center font-serif text-gold text-4xl">DR</div>
          <div>
            <p className="uppercase tracking-[0.2em] text-[12px] text-gold-light">Meet the founder</p>
            <h2 className="font-serif text-[30px] text-white mt-2">Dr. Shaymaa Abdel Nabi</h2>
            <p className="mt-3 max-w-2xl text-[15px] leading-relaxed">
              A medical analyst with a background in clinical chemistry, hematology, biochemistry and physiology, and a
              Master&apos;s degree in public health management. Dr. Beauty Care brings her science-first approach to
              hair care, skincare and supplements.
            </p>
            <Link href="/about" className="inline-block mt-5 text-gold-light underline underline-offset-4">Read her story</Link>
          </div>
        </div>
      </section>

      <TrustBar />
    </>
  );
}
