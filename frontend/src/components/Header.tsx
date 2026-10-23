import React from "react";
import { Flame, Wind, Layers, Activity, Eye, EyeOff } from "lucide-react";
import type { StatsSummary } from "../types";

interface HeaderProps {
  stats: StatsSummary | null;
  showSatellite: boolean;
  onToggleSatellite: () => void;
  showPlumes: boolean;
  onTogglePlumes: () => void;
  showHotspots: boolean;
  onToggleHotspots: () => void;
  showOriginsOnly: boolean;
  onToggleOriginsOnly: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  stats,
  showSatellite,
  onToggleSatellite,
  showPlumes,
  onTogglePlumes,
  showHotspots,
  onToggleHotspots,
  showOriginsOnly,
  onToggleOriginsOnly,
}) => {
  return (
    <header className="top-header">
      {/* Brand & Status */}
      <div className="brand-section">
        <div className="brand-icon-box">
          <Flame size={24} color="#f97316" />
        </div>
        <div className="brand-title-wrap">
          <h1 className="brand-title">AmazonWatch</h1>
          <div className="brand-subtitle">
            <span>Amazônia Legal</span>
            <span className="badge-live">
              <span className="pulse-dot"></span> Ao Vivo
            </span>
          </div>
        </div>
      </div>

      {/* Real-time Telemetry Metrics */}
      <div className="header-metrics">
        <div className="metric-pill">
          <div className="metric-icon">
            <Flame size={18} color="#ef4444" />
          </div>
          <div className="metric-data">
            <span className="metric-label">Focos 6h</span>
            <span className="metric-val">{stats?.total_hotspots?.toLocaleString() ?? "—"}</span>
          </div>
        </div>

        <div className="metric-pill">
          <div className="metric-icon">
            <Wind size={18} color="#38bdf8" />
          </div>
          <div className="metric-data">
            <span className="metric-label">Plumas Ativas</span>
            <span className="metric-val">{stats?.total_plumes ?? "—"}</span>
          </div>
        </div>

        <div className="metric-pill">
          <div className="metric-icon">
            <Layers size={18} color="#a78bfa" />
          </div>
          <div className="metric-data">
            <span className="metric-label">Área de Fumaça</span>
            <span className="metric-val">
              {stats?.total_smoke_area_km2 ? `${Math.round(stats.total_smoke_area_km2).toLocaleString()} km²` : "—"}
            </span>
          </div>
        </div>

        <div className="metric-pill">
          <div className="metric-icon">
            <Activity size={18} color="#f59e0b" />
          </div>
          <div className="metric-data">
            <span className="metric-label">Origens de Incêndio</span>
            <span className="metric-val">{stats?.active_origins ?? "—"}</span>
          </div>
        </div>
      </div>

      {/* Layer Toggles */}
      <div className="header-controls">
        <button
          className={`btn-control ${showSatellite ? "active" : ""}`}
          onClick={onToggleSatellite}
          title="Alternar imagem de satélite GOES-19 True Color"
        >
          {showSatellite ? <Eye size={16} /> : <EyeOff size={16} />}
          Satélite
        </button>

        <button
          className={`btn-control ${showPlumes ? "active" : ""}`}
          onClick={onTogglePlumes}
          title="Alternar polígonos de fumaça"
        >
          <Wind size={16} />
          Fumaça
        </button>

        <button
          className={`btn-control ${showHotspots ? "active" : ""}`}
          onClick={onToggleHotspots}
          title="Alternar focos de calor"
        >
          <Flame size={16} />
          Focos
        </button>

        <button
          className={`btn-control ${showOriginsOnly ? "active" : ""}`}
          onClick={onToggleOriginsOnly}
          title="Destacar somente focos identificados como origem de plumas"
        >
          <Activity size={16} />
          Apenas Origens
        </button>
      </div>
    </header>
  );
};
