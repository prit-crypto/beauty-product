import { AskStart } from "@/components/ProductButtons";

export default function Contact() {
  return (
    <section className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="font-serif text-[42px]">Contact Us</h1>
      <div className="gold-rule w-32 my-5" />
      <p className="text-[16px] leading-relaxed">
        Questions about a product, your routine or an order? Ask Dr. Beauty answers instantly in English or Arabic, and
        passes anything medical to Dr. Shaymaa&apos;s team.
      </p>
      <AskStart label="Chat with Ask Dr. Beauty" className="mt-6 btn-gold rounded-full px-6 py-3 text-[14px]" />
      <p className="mt-10 text-[13px] text-muted">
        Concept demo: in the live store this page would also show the brand&apos;s WhatsApp, phone and business details.
      </p>
    </section>
  );
}
