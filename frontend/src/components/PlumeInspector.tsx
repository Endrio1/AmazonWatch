import React from "react";
import { X, Wind, Flame, Target, Navigation } from "lucide-react";
import type { PlumeDetail } from "../types";

interface PlumeInspectorProps {
  plume: PlumeDetail | null;
  onClose: () => void;
  onFocusPlume: (plume: PlumeDetail) => void;
}

export const PlumeInspector: React.FC<PlumeInspectorProps> = ({
  plume,
  onClose,
  onFocusPlume,
}) => {
  if (!plume) return null;

  const origins = plume.links.filter((l) => l.is_origin);
  const others = plume.links.filter((l) => !l.is_origin);

  return (
    <aside className="plume-drawer">
      <div className="drawer-header">
        <div className="drawer-title">
          <Wind size={20} color="#38bdf8" />
          <span>Pluma #{plume.id}</span>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            className="btn-control"
            style={{ padding: "4px 8px" }}
            onClick={() => onFocusPlume(plume)}
            title="Aproximar no mapa"
          >
            <Navigation size={14} />
          </button>
          <button className="drawer-close" onClick={onClose} title="Fechar painel">
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="drawer-body">
        {/* Statistics Grid */}
        <div className="plume-stat-grid">
          <div className="stat-card">
            <div className="stat-card-label">Área da Pluma</div>
            <div className="stat-card-val" style={{ color: "#38bdf8" }}>
              {plume.area_km2.toLocaleString()} km²
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-card-label">Confiança NOAA</div>
            <div className="stat-card-val" style={{ color: "#34d399" }}>
              {Math.round(plume.confidence * 100)}%
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-card-label">Pixels Detectados</div>
            <div className="stat-card-val">{plume.pixel_count}</div>
          </div>

          <div className="stat-card">
            <div className="stat-card-label">Focos Associados</div>
            <div className="stat-card-val" style={{ color: "#f87171" }}>
              {plume.links.length} ({origins.length} origens)
            </div>
          </div>
        </div>

        {/* Origin Fires Section */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
            <Target size={16} color="#ef4444" />
            <h4 style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fca5a5" }}>
              Foco(s) de Origem Identificados
            </h4>
          </div>

          {origins.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
              Nenhum foco de calor cadastrado na janela de correlação.
            </p>
          ) : (
            <div className="origin-list">
              {origins.map((link) => (
                <div key={link.hotspot_id} className="origin-item is-origin">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="origin-badge">Origem Provável (Grupo #{link.cluster_id})</span>
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#f59e0b" }}>
                      Score: {(link.score * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="origin-coords">
                    <span>
                      {link.lat.toFixed(4)}°, {link.lon.toFixed(4)}°
                    </span>
                    <span style={{ color: "#fdba74" }}>
                      {link.distance_km === 0 ? "No interior" : `a ${link.distance_km} km`}
                    </span>
                  </div>

                  <div className="origin-meta">
                    <span>Satélite: {link.satellite}</span>
                    <span>
                      {link.age_minutes > 0 ? `${Math.round(link.age_minutes)} min antes` : "Simultâneo"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Other Contributing Hotspots */}
        {others.length > 0 && (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <Flame size={16} color="#fb923c" />
              <h4 style={{ fontSize: "0.85rem", fontWeight: 700, color: "#cbd5e1" }}>
                Focos Contribuintes ({others.length})
              </h4>
            </div>

            <div className="origin-list">
              {others.slice(0, 5).map((link) => (
                <div key={link.hotspot_id} className="origin-item">
                  <div className="origin-coords">
                    <span>
                      {link.lat.toFixed(4)}°, {link.lon.toFixed(4)}°
                    </span>
                    <span style={{ color: "#94a3b8" }}>{link.distance_km} km</span>
                  </div>
                  <div className="origin-meta">
                    <span>Satélite: {link.satellite}</span>
                    <span>{Math.round(link.age_minutes)} min</span>
                  </div>
                </div>
              ))}
              {others.length > 5 && (
                <span style={{ fontSize: "0.7rem", color: "#64748b", textAlign: "center" }}>
                  + {others.length - 5} focos adicionais
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
