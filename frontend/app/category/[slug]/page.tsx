import { notFound } from "next/navigation";

import ProductCard from "@/components/ProductCard";
import { AskStart } from "@/components/ProductButtons";
import { getCategories, getProducts } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function CategoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const cats = await getCategories();
  const cat = cats.find((c) => c.slug === slug);
  if (!cat) notFound();
  const products = (await getProducts(slug)).sort((a, b) => a.price_aed - b.price_aed);
  const lines = Array.from(new Set(products.map((p) => p.line)));

  return (
    <>
      <section className="gold-sheen border-b border-line">
        <div className="mx-auto max-w-6xl px-4 py-12">
          <p className="uppercase tracking-[0.2em] text-[12px] text-gold-dark">Shop</p>
          <h1 className="font-serif text-[42px] mt-2">{cat.en}</h1>
          <p className="text-muted mt-2">
            {products.length} products · {lines.join(" · ")}
          </p>
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="mb-10 rounded-xl border border-line bg-white px-5 py-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[14px]">Not sure which one suits you? Ask Dr. Beauty for a routine built around your concern and budget.</p>
          <AskStart label="Ask Dr. Beauty" className="btn-outline rounded-full px-5 py-2 text-[13px]" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-10">
          {products.map((p) => (
            <ProductCard key={p.id} p={p} />
          ))}
        </div>
      </section>
    </>
  );
}
