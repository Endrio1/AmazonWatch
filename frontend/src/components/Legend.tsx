import React from "react";

interface LegendProps {
  showSatellite?: boolean;
}

export const Legend: React.FC<LegendProps> = ({ showSatellite = true }) => {
  return (
    <div className="floating-legend">
      <div style={{ fontWeight: 700, color: "#fff", marginBottom: 6 }}>Legenda</div>

      {showSatellite && (
        <div style={{ marginBottom: 10, paddingBottom: 8, borderBottom: "1px solid rgba(255,255,255,0.12)" }}>
          <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginBottom: 4, display: "flex", justifyContent: "space-between" }}>
            <span>CPTEC/DSAT — 10.35µm</span>
            <span>Temp. Brilho</span>
          </div>
          <div
            style={{
              height: 9,
              borderRadius: 3,
              background: "linear-gradient(to right, #ec4899 0%, #3b82f6 20%, #06b6d4 40%, #eab308 60%, #f97316 80%, #ef4444 95%, #f8fafc 100%)",
              marginBottom: 3,
              boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
            }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
            <span>-80°C</span>
            <span>-40°C</span>
            <span>0°C</span>
            <span>+40°C</span>
          </div>
        </div>
      )}

      <div className="legend-item">
        <span
          className="legend-indicator"
          style={{ background: "rgba(56, 189, 248, 0.45)", border: "1px solid #38bdf8" }}
        />
        <span>Pluma de Fumaça (NOAA GOES-19)</span>
      </div>

      <div className="legend-item">
        <span
          className="legend-indicator"
          style={{
            background: "#ef4444",
            borderRadius: "50%",
            boxShadow: "0 0 6px #ef4444",
          }}
        />
        <span>Foco de Origem Provável (INPE)</span>
      </div>

      <div className="legend-item">
        <span
          className="legend-indicator"
          style={{ background: "#f97316", borderRadius: "50%" }}
        />
        <span>Foco de Calor Contribuinte</span>
      </div>

      <div className="legend-item">
        <span
          className="legend-indicator"
          style={{
            background: "none",
            borderBottom: "2px dashed #f59e0b",
            height: 0,
            width: 14,
          }}
        />
        <span>Vínculo de Origem (Incêndio ➔ Pluma)</span>
      </div>

      <div className="legend-item">
        <span
          className="legend-indicator"
          style={{
            background: "none",
            border: "1px dashed #10b981",
          }}
        />
        <span>Limite da Amazônia Legal (IBGE)</span>
      </div>
    </div>
  );
};
