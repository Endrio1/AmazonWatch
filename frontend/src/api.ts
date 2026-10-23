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
