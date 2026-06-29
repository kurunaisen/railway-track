/** Базовый URL бэкенда. В dev пусто — Vite проксирует /api и /health. */
export function backendOrigin(): string {
  return import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? "";
}

export function apiBase(): string {
  const origin = backendOrigin();
  return origin ? `${origin}/api` : "/api";
}

export function healthUrl(): string {
  const origin = backendOrigin();
  return origin ? `${origin}/health` : "/health";
}
