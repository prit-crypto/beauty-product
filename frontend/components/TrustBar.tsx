const ITEMS = [
  { title: "Global Shipping", text: "Delivering worldwide with reliable shipping options.", icon: "M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z" },
  { title: "Best Natural Quality", text: "Premium natural products for your health & wellness.", icon: "M12 21c-4-3-7-6.5-7-10a7 7 0 0 1 14 0c0 3.5-3 7-7 10Z M12 7v8" },
  { title: "Best Offers", text: "Unbeatable deals on top-quality items.", icon: "M4 12V4h8l8 8-8 8-8-8Z M8 8h.01" },
  { title: "Cash on Delivery", text: "Convenient payment upon delivery at your doorstep.", icon: "M3 7h18v10H3z M12 12m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0" },
];

export default function TrustBar() {
  return (
    <section className="bg-cream border-y border-line">
      <div className="mx-auto max-w-6xl px-4 py-10 grid grid-cols-2 md:grid-cols-4 gap-8">
        {ITEMS.map((i) => (
          <div key={i.title} className="text-center">
            <svg className="mx-auto mb-3 text-gold" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden>
              <path d={i.icon} />
            </svg>
            <h3 className="uppercase tracking-[0.14em] text-[13px] font-bold text-ink">{i.title}</h3>
            <p className="text-[13px] text-muted mt-1">{i.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
