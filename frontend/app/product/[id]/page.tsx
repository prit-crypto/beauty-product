import Link from "next/link";
import { notFound } from "next/navigation";

import ProductCard from "@/components/ProductCard";
import { AddToCart, AskAbout } from "@/components/ProductButtons";
import ProductVisual from "@/components/ProductVisual";
import { aed, getProduct, getProducts } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const p = await getProduct(id);
  if (!p) notFound();
  const related = (await getProducts(p.category)).filter((x) => x.id !== p.id && x.line === p.line).slice(0, 4);

  return (
    <>
      <section className="mx-auto max-w-6xl px-4 py-10">
        <nav className="text-[12px] text-muted mb-6">
          <Link href="/" className="hover:text-gold-dark">Home</Link> / <Link href={`/category/${p.category}`} className="hover:text-gold-dark capitalize">{p.category.replace(/-/g, " ")}</Link>
        </nav>
        <div className="grid md:grid-cols-2 gap-10">
          <ProductVisual line={p.line} name={p.name} size={p.size} image={p.image} />
          <div>
            <p className="uppercase tracking-[0.18em] text-[12px] text-gold-dark">{p.line}</p>
            <h1 className="font-serif text-[34px] leading-tight mt-2">{p.name}</h1>
            <p className="text-[24px] text-gold-dark font-semibold mt-3">
              {p.price_options_aed.length > 1 ? p.price_options_aed.map(aed).join(" – ") : aed(p.price_aed)}
            </p>
            <div className="flex flex-wrap gap-2 mt-3 text-[12px]">
              {p.size && <span className="border border-line rounded-full px-3 py-1">{p.size}</span>}
              {p.origin && <span className="border border-line rounded-full px-3 py-1">Made in {p.origin}</span>}
            </div>
            <p className="mt-5 text-[16px] leading-relaxed">{p.summary}</p>
            {p.caution && (
              <p className="mt-4 text-[13px] bg-[#fbf3e3] border border-[#ecd9ad] rounded-md px-3 py-2">
                This is a supplement. If you are pregnant, breastfeeding or taking medication, please check with Dr. Shaymaa&apos;s team before use.
              </p>
            )}
            <div className="mt-6 flex flex-wrap gap-3">
              <AddToCart id={p.id} name={p.name} price={p.price_aed} className="!px-6 !py-3 !text-[14px]" />
              <AskAbout name={p.name} className="!px-6 !py-3 !text-[14px]" />
            </div>
            <div className="gold-rule my-8" />
            {p.how_to_use && (
              <div className="mb-6">
                <h2 className="uppercase tracking-[0.14em] text-[13px] font-bold">How to use</h2>
                <p className="mt-2 text-[14px] leading-relaxed text-muted">{p.how_to_use}</p>
              </div>
            )}
            {p.details_en && (
              <details className="group" open>
                <summary className="uppercase tracking-[0.14em] text-[13px] font-bold cursor-pointer">Description</summary>
                <p className="mt-2 text-[14px] leading-relaxed text-muted">{p.details_en}</p>
              </details>
            )}
            {p.details_ar && (
              <details className="mt-4">
                <summary className="uppercase tracking-[0.14em] text-[13px] font-bold cursor-pointer">الوصف بالعربية</summary>
                <p className="mt-2 text-[15px] leading-loose text-muted" dir="rtl" lang="ar">{p.details_ar}</p>
              </details>
            )}
          </div>
        </div>
      </section>
      {related.length > 0 && (
        <section className="bg-cream border-t border-line">
          <div className="mx-auto max-w-6xl px-4 py-12">
            <h2 className="font-serif text-[28px]">More from {p.line}</h2>
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-6">
              {related.map((r) => (
                <ProductCard key={r.id} p={r} />
              ))}
            </div>
          </div>
        </section>
      )}
    </>
  );
}
