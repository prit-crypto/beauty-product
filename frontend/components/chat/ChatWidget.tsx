"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useCart } from "@/lib/cart";
import type { Card, ChatResponse, QuickReply, Reply } from "@/lib/types";

import { CheckoutCard, CompareCard, HandoffCard, ProductList, ProductMini, RoutineCard } from "./Cards";
import RichText from "./RichText";

type Msg =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "bot"; reply: Reply }
  | { id: number; role: "note"; text: string }; // e.g. "— العربية —" when the language is switched

type HistoryItem = { role: "user" | "assistant"; text: string; kind: string; reply?: Reply };

// localStorage: the conversation survives page reloads and a return visit; "New chat" starts a fresh one.
const SID_KEY = "drbeauty-demo-session";
const BIG_KEY = "drbeauty-chat-large";
const LANG_LABELS = ["English", "العربية"];
let nextId = 1;

const UI = {
  en: { title: "Ask Dr. Beauty", sub: "Your personal beauty advisor", ph: "Type your message…", send: "Send", close: "Close chat",
        typing: "Ask Dr. Beauty is typing", slow: "Just a moment…", mode: "Mode", newChat: "New chat",
        expand: "Larger view", shrink: "Smaller view", where: "Where is my order?", again: "Start a new routine" },
  ar: { title: "اسألي دكتورة بيوتي", sub: "مستشارتكِ الشخصية للجمال", ph: "اكتبي رسالتكِ…", send: "إرسال", close: "إغلاق",
        typing: "جارٍ الكتابة", slow: "لحظة من فضلكِ…", mode: "الوضع", newChat: "محادثة جديدة",
        expand: "عرض أكبر", shrink: "عرض أصغر", where: "أين طلبي؟", again: "روتين جديد" },
};

function readSid(): string | null {
  try {
    return localStorage.getItem(SID_KEY);
  } catch {
    return null;
  }
}
function writeSid(v: string | null) {
  try {
    if (v) localStorage.setItem(SID_KEY, v);
    else localStorage.removeItem(SID_KEY);
  } catch {
    /* storage unavailable: the chat still works for this page view */
  }
}

export default function ChatWidget() {
  const { add, remove, clear, items: cartItems } = useCart();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [provider, setProvider] = useState<string>("");
  const [error, setError] = useState("");
  const [big, setBig] = useState(false);
  const sid = useRef<string | null>(null);
  const genRef = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const started = useRef(false);
  const cartRef = useRef(cartItems);
  const pathname = usePathname();

  cartRef.current = cartItems;

  useEffect(() => {
    sid.current = readSid();
    try {
      setBig(localStorage.getItem(BIG_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);
  const toggleBig = () =>
    setBig((b) => {
      try {
        localStorage.setItem(BIG_KEY, b ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !b;
    });

  // Scroll only the message list (scrollIntoView would also shift the panel sideways in RTL).
  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
  }, [msgs, busy]);

  useEffect(() => {
    if (!busy) return setSlow(false);
    const tm = setTimeout(() => setSlow(true), 3500);
    return () => clearTimeout(tm);
  }, [busy]);

  const send = useCallback(
    async (message: string, action?: string, shown?: string, langOverride?: "en" | "ar", silent = false, carryFrom?: string | null) => {
      const gen = genRef.current; // a reply that arrives after "New chat" belongs to the old chat and is dropped
      if (shown && !silent) setMsgs((m) => [...m, { id: nextId++, role: "user", text: shown }]);
      setBusy(true);
      setError("");
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sid.current,
            message,
            action,
            label: action ? shown : undefined,
            lang: langOverride ?? lang,
            cart: cartRef.current.map(({ id, name, price_aed, qty }) => ({ id, name, price_aed, qty })),
            carry_from: carryFrom ?? undefined,
          }),
        });
        if (gen !== genRef.current) return;
        if (!res.ok) throw new Error(String(res.status));
        const data: ChatResponse = await res.json();
        if (gen !== genRef.current) return;
        sid.current = data.session_id;
        writeSid(data.session_id);
        setProvider(data.provider.used);
        setLang(data.reply.lang);
        // the assistant's cart actions are applied for real, so what it says always matches the cart
        for (const c of data.reply.cards) {
          if (c.type === "cart_add") add(c.items);
          if (c.type === "cart_remove") remove(c.ids);
          if (c.type === "cart_clear") clear();
        }
        setMsgs((m) => [...m, { id: nextId++, role: "bot", reply: data.reply }]);
      } catch {
        if (gen === genRef.current)
          setError(lang === "ar" ? "تعذر الاتصال. حاولي مرة أخرى." : "Couldn't reach the assistant. Please try again.");
      } finally {
        if (gen !== genRef.current) return; // a stale reply: the new chat manages its own state
        setBusy(false);
        // back to the message box, unless the customer is already typing somewhere else (e.g. the checkout form)
        setTimeout(() => {
          const a = document.activeElement;
          if (!a || a === document.body || a.tagName === "BUTTON" || a === inputRef.current) inputRef.current?.focus({ preventScroll: true });
        }, 50);
      }
    },
    [add, remove, clear, lang],
  );

  // Restore an earlier conversation (after a reload or a return visit), otherwise greet.
  const start = useCallback(async () => {
    if (sid.current) {
      try {
        const r = await fetch(`/api/chat/history?session_id=${encodeURIComponent(sid.current)}`);
        const d: { messages: HistoryItem[] } = await r.json();
        if (d.messages.length) {
          // a checkout form followed by a placed order comes back as "Order placed", never as an open form again
          const restored: Msg[] = d.messages.map((m, i): Msg =>
            m.role === "assistant" && m.reply
              ? { id: nextId++, role: "bot", reply: { ...m.reply, placed: d.messages.slice(i + 1).some((x) => x.kind === "order") } }
              : m.kind === "action" && LANG_LABELS.includes(m.text)
                ? { id: nextId++, role: "note", text: m.text }
                : { id: nextId++, role: "user", text: m.text },
          );
          setMsgs(restored);
          const lastBot = [...d.messages].reverse().find((m) => m.reply);
          if (lastBot?.reply) setLang(lastBot.reply.lang);
          return;
        }
      } catch {
        /* fall through to a fresh greeting */
      }
    }
    send("");
  }, [send]);

  // open from anywhere: header button, hero, product pages
  useEffect(() => {
    const on = (e: Event) => {
      const detail = (e as CustomEvent<{ message?: string }>).detail || {};
      setOpen(true);
      if (detail.message) {
        started.current = true;
        send(detail.message, undefined, detail.message);
      }
    };
    window.addEventListener("ask-dr-beauty", on);
    return () => window.removeEventListener("ask-dr-beauty", on);
  }, [send]);

  useEffect(() => {
    if (open && !started.current && msgs.length === 0) {
      started.current = true;
      start();
    }
  }, [open, msgs.length, start]);

  // ↻ New chat: a fresh conversation (no memory of the old one). Only placed orders come along, so
  // "where is my order?" still works. The shop cart stays, as on any shop page.
  const newChat = (l: "en" | "ar" = lang) => {
    const old = sid.current;
    genRef.current += 1;
    sid.current = null;
    writeSid(null);
    setMsgs([]);
    setBusy(false);
    setError("");
    setLang(l);
    started.current = true;
    send("", undefined, undefined, l, false, old);
  };
  // Switch language mid-conversation: same chat, cart and routine; the assistant continues in the new language.
  const switchLang = (l: "en" | "ar") => {
    if (l === lang || busy) return;
    if (!sid.current || msgs.length === 0) return newChat(l);
    const label = l === "ar" ? "العربية" : "English";
    setLang(l);
    // a small divider instead of a fake "you typed العربية" bubble
    setMsgs((m) => [...m, { id: nextId++, role: "note", text: label }]);
    send("", `lang:${l}`, label, l, true);
  };

  // after an order is placed in the chat: empty the cart and add a clear confirmation with the right next steps
  const orderPlaced = (message: string) => {
    clear();
    const u = UI[lang];
    setMsgs((m) => [...m, {
      id: nextId++, role: "bot",
      reply: { text: message, cards: [], lang, dir: lang === "ar" ? "rtl" : "ltr", kind: "order", event: "order",
               quick_replies: [{ label: u.where, action: `say:${u.where}` }, { label: u.again, action: "restart" }] },
    }]);
  };

  const onQuick = (q: QuickReply) =>
    q.action.startsWith("say:") ? send(q.action.slice(4), undefined, q.label) : send("", q.action, q.label);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    send(text, undefined, text);
  };

  if (pathname?.startsWith("/admin")) return null;

  const ui = UI[lang];
  const dir = lang === "ar" ? "rtl" : "ltr";
  const lastBot = [...msgs].reverse().find((m) => m.role === "bot") as Extract<Msg, { role: "bot" }> | undefined;
  const lastIsBot = msgs.length > 0 && msgs[msgs.length - 1].role === "bot";

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed z-40 bottom-5 right-5 flex items-center gap-3 rounded-full shadow-lg btn-gold pl-2 pr-5 py-2"
          aria-label="Open Ask Dr. Beauty chat"
        >
          <span className="w-11 h-11 rounded-full bg-white text-gold grid place-items-center font-serif font-bold text-lg border border-gold-light">
            DR
          </span>
          <span className="text-left leading-tight">
            <span className="block font-serif text-[16px]">Ask Dr. Beauty</span>
            <span className="block text-[11px] opacity-90">Your personal routine in 1 minute</span>
          </span>
        </button>
      )}

      {open && (
        <section
          dir={dir}
          className={`fixed z-50 inset-0 sm:inset-auto sm:bottom-5 sm:right-5 sm:max-h-[calc(100vh-40px)] bg-white sm:rounded-2xl shadow-2xl border border-line flex flex-col overflow-hidden rise transition-[width,height] duration-200 ${
            big ? "sm:w-[min(820px,calc(100vw-40px))] sm:h-[calc(100vh-40px)]" : "sm:w-[460px] sm:h-[720px]"
          }`}
          aria-label="Ask Dr. Beauty chat"
        >
          <header className="bg-gold text-white px-4 py-3 flex items-center gap-3">
            <span className="relative w-10 h-10 rounded-full bg-white text-gold grid place-items-center font-serif font-bold">
              DR
              <span className="absolute bottom-0 end-0 w-2.5 h-2.5 rounded-full bg-[#5fbf73] border-2 border-gold" aria-hidden />
            </span>
            <div className="flex-1 min-w-0">
              <h2 className="font-serif text-[18px] leading-tight">{ui.title}</h2>
              <p className="text-[11px] opacity-90 truncate">{ui.sub}</p>
            </div>
            <button onClick={toggleBig} title={big ? ui.shrink : ui.expand} aria-label={big ? ui.shrink : ui.expand} className="hidden sm:block p-1 opacity-90 hover:opacity-100">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                {big ? <path d="M9 4v5H4M15 20v-5h5M20 9h-5V4M4 15h5v5" /> : <path d="M4 9V4h5M20 15v5h-5M15 4h5v5M9 20H4v-5" />}
              </svg>
            </button>
            <button onClick={() => newChat()} title={ui.newChat} aria-label={ui.newChat} className="p-1 opacity-90 hover:opacity-100">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                <path d="M4 12a8 8 0 1 0 2.3-5.6M4 4v4h4" />
              </svg>
            </button>
            <div className="flex rounded-full bg-white/15 text-[11px] overflow-hidden" dir="ltr">
              <button onClick={() => switchLang("en")} className={`px-2 py-1 ${lang === "en" ? "bg-white text-gold-dark" : ""}`}>EN</button>
              <button onClick={() => switchLang("ar")} className={`px-2 py-1 ${lang === "ar" ? "bg-white text-gold-dark" : ""}`}>ع</button>
            </div>
            <button onClick={() => setOpen(false)} aria-label={ui.close} className="p-1 opacity-90 hover:opacity-100">
              <svg width="20" height="20" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </header>

          <div ref={listRef} className="flex-1 overflow-y-auto bg-cream px-3 py-4 space-y-3" aria-live="polite">
            {msgs.map((m) =>
              m.role === "note" ? (
                <div key={m.id} className="flex items-center gap-3 text-[11.5px] text-muted py-1" role="separator">
                  <span className="flex-1 h-px bg-line" />
                  <span>{m.text}</span>
                  <span className="flex-1 h-px bg-line" />
                </div>
              ) : m.role === "user" ? (
                <div key={m.id} className="flex justify-end rise">
                  <p className="max-w-[82%] bg-ink text-white rounded-2xl rounded-br-sm px-3.5 py-2 text-[14px] whitespace-pre-line" dir="auto">{m.text}</p>
                </div>
              ) : (
                <BotMessage key={m.id} reply={m.reply} sessionId={sid.current} onAction={(a, label) => send("", a, label)} onOrderPlaced={orderPlaced} />
              ),
            )}
            {busy && (
              <div className="flex items-center gap-2 px-3 py-2" aria-label={ui.typing}>
                <span className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="w-2 h-2 rounded-full bg-gold/60 animate-bounce" style={{ animationDelay: `${i * 0.12}s` }} />
                  ))}
                </span>
                {slow && <span className="text-[12px] text-muted">{ui.slow}</span>}
              </div>
            )}
            {error && <p className="text-[13px] text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</p>}
          </div>

          {lastIsBot && lastBot && lastBot.reply.quick_replies.length > 0 && !busy && (
            <div className="bg-white border-t border-line px-3 pt-2.5 pb-1 flex flex-wrap gap-2" dir={lastBot.reply.dir}>
              {lastBot.reply.quick_replies.map((q) => (
                <button
                  key={q.action + q.label}
                  onClick={() => onQuick(q)}
                  className={`rounded-full px-3 py-1.5 text-[13px] ${q.action === "add_routine" ? "btn-gold" : "btn-outline"}`}
                >
                  {q.label}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={submit} className="bg-white border-t border-line p-3 flex gap-2">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={ui.ph}
              dir="auto"
              className="flex-1 min-w-0 rounded-full border border-line px-4 py-2.5 text-[14px] outline-none focus:border-gold"
              aria-label={ui.ph}
              maxLength={2000}
            />
            <button type="submit" disabled={busy || !input.trim()} className="btn-gold rounded-full px-4 text-[14px] disabled:opacity-50">
              {ui.send}
            </button>
          </form>
          <p className="bg-white text-[10px] text-muted text-center pb-2 -mt-1" dir="ltr">
            Concept demo · {ui.mode}: {provider || "…"} · Not medical advice
          </p>
        </section>
      )}
    </>
  );
}

function BotMessage({ reply, sessionId, onAction, onOrderPlaced }: {
  reply: Reply; sessionId: string | null; onAction: (a: string, label: string) => void; onOrderPlaced: (message: string) => void;
}) {
  const addItem = (id: string, name: string) => onAction(`add_item:${id}`, reply.lang === "ar" ? `أضيفي ${name}` : `Add ${name}`);
  return (
    <div className="rise space-y-2" dir={reply.dir}>
      <div className="flex gap-2 items-start">
        <span className="shrink-0 w-7 h-7 rounded-full bg-white border border-gold text-gold grid place-items-center font-serif text-[11px] font-bold">DR</span>
        <div className="max-w-[85%] bg-white border border-line rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-[14px] leading-relaxed">
          <RichText text={reply.text} />
        </div>
      </div>
      {reply.cards.map((c: Card, i: number) => {
        if (c.type === "routine")
          return (
            <RoutineCard key={i} routine={c.routine} lang={reply.lang} onAddItem={addItem}
              onAdd={() => onAction("add_routine", reply.lang === "ar" ? "أضيفي الروتين للسلة" : "Add routine to cart")} />
          );
        if (c.type === "product") return <ProductMini key={i} product={c.product} lang={reply.lang} onAdd={addItem} />;
        if (c.type === "product_list") return <ProductList key={i} items={c.items} lang={reply.lang} onAdd={addItem} />;
        if (c.type === "compare") return <CompareCard key={i} items={c.items} lang={reply.lang} onAdd={addItem} />;
        if (c.type === "handoff") return <HandoffCard key={i} sessionId={sessionId} lang={reply.lang} />;
        if (c.type === "checkout")
          return <CheckoutCard key={i} items={c.items} total={c.total} sessionId={sessionId} lang={reply.lang} onPlaced={onOrderPlaced}
              placed={reply.placed} />;
        if (c.type === "cart_add")
          return (
            <a key={i} href="/cart" className="block ms-9 text-[13px] text-gold-dark underline underline-offset-4">
              {reply.lang === "ar" ? "عرض السلة" : "View cart"}
            </a>
          );
        return null;
      })}
    </div>
  );
}
