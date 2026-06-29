/** Базовый URL бэкенда. В dev пусто — Vite проксирует /api и /health. */
function isVercelProduction(): boolean {
  if (typeof window === "undefined") return false;
  const h = window.location.hostname;
  return h.endsWith(".vercel.app") || h.endsWith(".vercel.sh");
}

export function backendOrigin(): string {
  // На Vercel запросы идут на тот же домен → vercel.json проксирует на Railway (без CORS)
  if (isVercelProduction()) {
    return window.location.origin;
  }

  const raw = import.meta.env.VITE_API_URL?.trim().replace(/\/$/, "") ?? "";
  if (!raw) return "";
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  return `https://${raw}`;
}

export function apiBase(): string {
  const origin = backendOrigin();
  return origin ? `${origin}/api` : "/api";
}

export function healthUrl(): string {
  const origin = backendOrigin();
  return origin ? `${origin}/health` : "/health";
}
