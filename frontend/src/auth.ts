import { apiBase, healthUrl } from "./config";

const TOKEN_KEY = "railway_token";
const USER_KEY = "railway_user";

export interface AuthUser {
  id?: number;
  username: string;
  role: string;
  avatar_id?: string;
}

export interface UserProfile {
  id: number;
  username: string;
  name: string;
  role: string;
  avatar_id: string;
  email: string;
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setAuth(token: string, user: AuthUser): void {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function updateStoredUser(patch: Partial<AuthUser>): AuthUser | null {
  const current = getUser();
  if (!current) return null;
  const next = { ...current, ...patch };
  sessionStorage.setItem(USER_KEY, JSON.stringify(next));
  return next;
}

export function clearAuth(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function getUser(): AuthUser | null {
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function profileToAuthUser(profile: UserProfile): AuthUser {
  return {
    id: profile.id,
    username: profile.username || profile.name,
    role: profile.role,
    avatar_id: profile.avatar_id,
  };
}

export async function fetchMe(): Promise<AuthUser | null> {
  const token = getToken();
  if (!token) return getUser();
  const res = await fetch(`${apiBase()}/auth/me`, { headers: authHeaders() });
  if (!res.ok) return getUser();
  const profile = (await res.json()) as UserProfile;
  const user = profileToAuthUser(profile);
  const existing = getUser();
  if (existing) {
    setAuth(token, { ...existing, ...user });
  }
  return user;
}

export async function updateProfileAvatar(avatarId: string): Promise<UserProfile> {
  const res = await fetch(`${apiBase()}/auth/profile`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ avatar_id: avatarId }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text.includes("detail") ? JSON.parse(text).detail : "Не удалось сохранить профиль");
  }
  const profile = (await res.json()) as UserProfile;
  updateStoredUser(profileToAuthUser(profile));
  return profile;
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${apiBase()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text.includes("detail") ? JSON.parse(text).detail : "Ошибка входа");
  }
  const data = await res.json();
  const user = { username: data.username, role: data.role };
  setAuth(data.access_token, user);
  const profile = await fetchMe();
  return profile ?? user;
}

export async function checkHealth(): Promise<{ auth_required: boolean }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(healthUrl(), { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } finally {
    clearTimeout(timer);
  }
}
