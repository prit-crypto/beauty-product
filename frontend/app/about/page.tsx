import { AskStart } from "@/components/ProductButtons";
import TrustBar from "@/components/TrustBar";

export default function About() {
  return (
    <>
      <section className="gold-sheen border-b border-line">
        <div className="mx-auto max-w-4xl px-4 py-16">
          <p className="uppercase tracking-[0.2em] text-[12px] text-gold-dark">About us</p>
          <h1 className="font-serif text-[44px] mt-2">Who We Are</h1>
        </div>
      </section>
      <section className="mx-auto max-w-4xl px-4 py-14 space-y-6 text-[16px] leading-relaxed">
        <p>
          Dr. Shaymaa Abdel Nabi is the founder of Dr. Beauty Care, a company focused on effective, natural skincare
          products, hair care solutions and supplements that are safe and sustainable.
        </p>
        <p>
          She is a medical analyst with a background in clinical chemistry, hematology, biochemistry and physiology, and
          holds a Master&apos;s degree in public health management. She brings that expertise to natural and sustainable
          solutions in the beauty industry.
        </p>
        <p>
          Dr. Beauty Care specialises in hair care, skin care and supplements, all aimed at promoting holistic
          well-being, with a commitment to high-quality, safe products made with natural ingredients.
        </p>
        <div className="rounded-xl border border-gold/40 bg-cream p-6 flex flex-wrap items-center justify-between gap-4">
          <p className="font-serif text-[20px]">Get guidance in Dr. Shaymaa&apos;s approach, any time.</p>
          <AskStart label="Ask Dr. Beauty" className="btn-gold rounded-full px-6 py-3 text-[14px]" />
        </div>
        <p className="text-[12px] text-muted">Text adapted from the archived drbeautycare.org About page for this concept demo.</p>
      </section>
      <TrustBar />
    </>
  );
}
