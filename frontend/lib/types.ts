export type Product = {
  id: string;
  name: string;
  original_name: string;
  line: string;
  category: string;
  area: string;
  step: string;
  time: string;
  concerns: string[];
  price_aed: number;
  price_options_aed: number[];
  size: string;
  origin: string;
  summary: string;
  summary_ar?: string | null;
  details_en: string;
  details_ar: string;
  how_to_use: string;
  premium: boolean;
  caution: boolean;
  handoff: boolean;
  image: string | null;
};

export type Category = { slug: string; en: string; ar: string; count: number };

export type RoutineStep = {
  id: string;
  name: string;
  line: string;
  price_aed: number;
  slot: string;
  slot_label: string;
  summary: string;
  how_to_use: string;
  caution: boolean;
  handoff: boolean;
  category: string;
  image?: string | null;
  summary_ar?: string | null;
  for_labels?: string[];
  note_label?: string;
};

export type Routine = {
  area: string;
  tier: string;
  budget: number | null;
  total: number;
  full_total: number;
  steps: RoutineStep[];
  dropped: RoutineStep[];
  addons: RoutineStep[];
  caution: boolean;
  over_budget_minimum: boolean;
  uncovered?: string[];
};

export type CardProduct = Pick<Product, "id" | "name" | "line" | "price_aed" | "summary" | "how_to_use" | "category" | "caution" | "handoff" | "size" | "origin" | "time" | "image"> & { summary_ar?: string | null };

export type Card =
  | { type: "routine"; routine: Routine }
  | { type: "product"; product: CardProduct }
  | { type: "product_list"; items: CardProduct[] }
  | { type: "compare"; items: CardProduct[] }
  | { type: "handoff"; category: string }
  | { type: "cart_add"; items: { id: string; name: string; price_aed: number }[]; total: number }
  | { type: "cart_remove"; ids: string[] }
  | { type: "cart_clear" }
  | { type: "checkout"; items: { id: string; name: string; price_aed: number; qty?: number }[]; total: number };

export type QuickReply = { label: string; action: string };

export type Reply = {
  text: string;
  cards: Card[];
  quick_replies: QuickReply[];
  lang: "en" | "ar";
  dir: "ltr" | "rtl";
  kind: string;
  event: string | null;
  placed?: boolean; // client only: a restored checkout form whose order was already placed
};

export type ChatResponse = {
  session_id: string;
  reply: Reply;
  provider: { requested: string; used: string; errors: string[] };
};
