import Image from "next/image";

const LINE_LOGO: Record<string, { src: string; w: number; h: number }> = {
  "Cana Gold 24K": { src: "/brand/canagold.png", w: 366, h: 137 },
  IvyBears: { src: "/brand/ivybears.png", w: 311, h: 162 },
};

/** Brand-styled placeholder until real product photos are added (catalog.json `image` field). */
export default function ProductVisual({
  line,
  name,
  size,
  image,
  compact = false,
}: {
  line: string;
  name: string;
  size?: string;
  image?: string | null;
  compact?: boolean;
}) {
  if (image) {
    return (
      <div className="relative aspect-square bg-cream rounded-md overflow-hidden">
        <Image src={image} alt={name} fill className="object-contain p-4" sizes="(max-width: 768px) 50vw, 25vw" />
      </div>
    );
  }
  const logo = LINE_LOGO[line];
  const premium = line === "Cana Gold 24K";
  return (
    <div
      className={`relative aspect-square rounded-md overflow-hidden grid place-items-center text-center ${
        premium ? "bg-[#14110b]" : "gold-sheen"
      } border border-line`}
      aria-label={`${name}, ${line}`}
      role="img"
    >
      <div className="absolute inset-3 border border-gold/40 rounded-sm pointer-events-none" />
      <div className="px-4">
        {logo && !compact ? (
          <Image src={logo.src} alt={line} width={logo.w} height={logo.h} className="mx-auto w-[62%] h-auto opacity-95" />
        ) : (
          <div
            className={`mx-auto ${compact ? "w-10 h-10 text-sm" : "w-16 h-16 text-xl"} rounded-full border-2 border-gold grid place-items-center font-serif font-bold text-gold`}
          >
            DR
          </div>
        )}
        {!compact && (
          <>
            <p className={`mt-3 uppercase tracking-[0.18em] text-[10px] ${premium ? "text-gold-light" : "text-gold-dark"}`}>{line}</p>
            {size && <p className={`text-[11px] mt-1 ${premium ? "text-[#bfb6a3]" : "text-muted"}`}>{size}</p>}
          </>
        )}
      </div>
    </div>
  );
}
