import type { Category, Product } from "./types";

// Server components call the FastAPI backend directly; the browser goes through the /api rewrite in next.config.ts.
const SERVER_API = process.env.API_URL || "http://127.0.0.1:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${SERVER_API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const getCategories = () => get<Category[]>("/api/categories");
export const getProducts = (category?: string) =>
  get<Product[]>(`/api/products${category ? `?category=${encodeURIComponent(category)}` : ""}`);
export const getProduct = async (id: string): Promise<Product | null> => {
  const res = await fetch(`${SERVER_API}/api/products/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API product failed: ${res.status}`);
  return res.json();
};

export const aed = (v: number) => `${v.toLocaleString("en-US", { maximumFractionDigits: 0 })} د.إ`;
export const aedText = (v: number) => `AED ${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
