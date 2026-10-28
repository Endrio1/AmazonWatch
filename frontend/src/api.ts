import type { PlumeDetail, SatelliteFrame, StatsSummary } from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

export async function fetchStats(hours: number = 6): Promise<StatsSummary> {
  const res = await fetch(`${API_BASE}/stats?hours=${hours}`);
  if (!res.ok) throw new Error("Falha ao carregar estatísticas");
  return res.json();
}

export async function fetchRegion(): Promise<any> {
  const res = await fetch(`${API_BASE}/region`);
  if (!res.ok) throw new Error("Falha ao carregar limite da região");
  return res.json();
}

export async function fetchTimeline(hours: number = 6): Promise<string[]> {
  const res = await fetch(`${API_BASE}/plumes/timeline?hours=${hours}`);
  if (!res.ok) throw new Error("Falha ao carregar linha do tempo");
  return res.json();
}

export async function fetchPlumes(scanTime?: string): Promise<any> {
  const url = scanTime
    ? `${API_BASE}/plumes?scan_time=${encodeURIComponent(scanTime)}&min_area_km2=5`
    : `${API_BASE}/plumes?min_area_km2=5&limit=300`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Falha ao carregar plumas");
  return res.json();
}

export async function fetchPlumeDetail(plumeId: number): Promise<PlumeDetail> {
  const res = await fetch(`${API_BASE}/plumes/${plumeId}`);
  if (!res.ok) throw new Error("Falha ao carregar detalhes da pluma");
  return res.json();
}

export async function fetchHotspots(start?: string, end?: string): Promise<any> {
  let url = `${API_BASE}/hotspots?limit=3000`;
  if (start) url += `&start=${encodeURIComponent(start)}`;
  if (end) url += `&end=${encodeURIComponent(end)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Falha ao carregar focos de incêndio");
  return res.json();
}

export async function fetchFrames(): Promise<SatelliteFrame[]> {
  const res = await fetch(`${API_BASE}/frames?limit=36`);
  if (!res.ok) throw new Error("Falha ao carregar quadros de satélite");
  return res.json();
}

// --- Autenticação e Usuário ---

const TOKEN_KEY = "amazonwatch_auth_token";

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function registerUser(name: string, email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao registrar usuário");
  }
  const data = await res.json();
  if (data.access_token) setAuthToken(data.access_token);
  return data;
}

export async function loginUser(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao efetuar login");
  }
  const data = await res.json();
  if (data.access_token) setAuthToken(data.access_token);
  return data;
}

export async function fetchCurrentUser() {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    clearAuthToken();
    throw new Error("Sessão expirada");
  }
  return res.json();
}

// --- Localizações Monitoradas (50km) ---

export async function fetchUserLocations() {
  const res = await fetch(`${API_BASE}/user/locations`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Erro ao carregar locais de monitoramento");
  return res.json();
}

export async function createUserLocation(data: {
  label: string;
  lat: number;
  lon: number;
  radius_km?: number;
  notify_fire?: boolean;
  notify_smoke?: boolean;
}) {
  const res = await fetch(`${API_BASE}/user/locations`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Erro ao cadastrar local");
  }
  return res.json();
}

export async function deleteUserLocation(locationId: number) {
  const res = await fetch(`${API_BASE}/user/locations/${locationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Erro ao excluir local");
  return true;
}

// --- Alertas e Notificações ---

export async function fetchUserAlerts(unreadOnly = false) {
  const res = await fetch(`${API_BASE}/user/notifications?unread_only=${unreadOnly}&limit=100`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Erro ao carregar alertas");
  return res.json();
}

export async function markAlertRead(notificationId: number) {
  const res = await fetch(`${API_BASE}/user/notifications/${notificationId}/read`, {
    method: "PATCH",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Erro ao atualizar alerta");
  return res.json();
}

export async function markAllAlertsRead() {
  const res = await fetch(`${API_BASE}/user/notifications/mark-all-read`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Erro ao marcar alertas como lidos");
  return res.json();
}

