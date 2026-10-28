import React, { useState } from "react";
import {
  X,
  Bell,
  MapPin,
  Flame,
  Wind,
  Plus,
  Trash2,
  CheckCheck,
  Navigation,
  Compass,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import type { AlertNotification, MonitoredLocation, User } from "../types";
import { createUserLocation, deleteUserLocation, markAlertRead, markAllAlertsRead } from "../api";

interface AlertsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  onOpenAuth: () => void;
  locations: MonitoredLocation[];
  onRefreshLocations: () => void;
  alerts: AlertNotification[];
  onRefreshAlerts: () => void;
  onFocusLocation: (lat: number, lon: number) => void;
}

export const AlertsDrawer: React.FC<AlertsDrawerProps> = ({
  isOpen,
  onClose,
  user,
  onOpenAuth,
  locations,
  onRefreshLocations,
  alerts,
  onRefreshAlerts,
  onFocusLocation,
}) => {
  const [activeTab, setActiveTab] = useState<"alerts" | "locations">("alerts");
  const [newLabel, setNewLabel] = useState("");
  const [newLat, setNewLat] = useState("");
  const [newLon, setNewLon] = useState("");
  const [savingLocation, setSavingLocation] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleUseCurrentPosition = () => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setNewLat(pos.coords.latitude.toFixed(4));
          setNewLon(pos.coords.longitude.toFixed(4));
        },
        () => {
          setErrorMsg("Não foi possível obter sua localização via GPS.");
        }
      );
    } else {
      setErrorMsg("Geolocalização não suportada no navegador.");
    }
  };

  const handleAddLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLabel.trim()) return;
    const lat = parseFloat(newLat);
    const lon = parseFloat(newLon);
    if (isNaN(lat) || isNaN(lon)) {
      setErrorMsg("Informe latitude e longitude válidas");
      return;
    }

    setSavingLocation(true);
    setErrorMsg(null);
    try {
      await createUserLocation({
        label: newLabel.trim(),
        lat,
        lon,
        radius_km: 50.0,
        notify_fire: true,
        notify_smoke: true,
      });
      setNewLabel("");
      setNewLat("");
      setNewLon("");
      onRefreshLocations();
      onRefreshAlerts();
    } catch (err: any) {
      setErrorMsg(err.message || "Erro ao salvar localização");
    } finally {
      setSavingLocation(false);
    }
  };

  const handleDeleteLocation = async (id: number) => {
    try {
      await deleteUserLocation(id);
      onRefreshLocations();
      onRefreshAlerts();
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkRead = async (id: number) => {
    try {
      await markAlertRead(id);
      onRefreshAlerts();
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllAlertsRead();
      onRefreshAlerts();
    } catch (err) {
      console.error(err);
    }
  };

  const unreadCount = alerts.filter((a) => !a.read_at).length;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="alerts-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="drawer-header">
          <div className="drawer-title-wrap">
            <Bell size={20} className="drawer-icon" />
            <div>
              <h2 className="drawer-title">Alertas e Monitoramento</h2>
              <p className="drawer-subtitle">Vigilância de fogo e fumaça em raio de 50 km</p>
            </div>
          </div>
          <button className="drawer-close-btn" onClick={onClose} title="Fechar painel">
            <X size={20} />
          </button>
        </div>

        {/* Guest prompt if not logged in */}
        {!user ? (
          <div className="drawer-guest-banner">
            <AlertTriangle size={32} color="#f97316" />
            <h3>Monitore sua região</h3>
            <p>
              Cadastre sua localização ou propriedade rural para receber notificações automáticas
              quando houver focos de incêndio a menos de 50 km ou fumaça na região.
            </p>
            <button
              className="btn-primary"
              onClick={() => {
                onClose();
                onOpenAuth();
              }}
            >
              Criar Conta ou Entrar
            </button>
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div className="drawer-tabs">
              <button
                className={`drawer-tab ${activeTab === "alerts" ? "active" : ""}`}
                onClick={() => setActiveTab("alerts")}
              >
                Notificações
                {unreadCount > 0 && <span className="tab-badge">{unreadCount}</span>}
              </button>
              <button
                className={`drawer-tab ${activeTab === "locations" ? "active" : ""}`}
                onClick={() => setActiveTab("locations")}
              >
                Meus Locais ({locations.length})
              </button>
            </div>

            {/* Tab: Alertas */}
            {activeTab === "alerts" && (
              <div className="drawer-content">
                <div className="alerts-toolbar">
                  <span className="alerts-count">
                    {alerts.length} alerta{alerts.length !== 1 ? "s" : ""} registrado
                    {alerts.length !== 1 ? "s" : ""}
                  </span>
                  {unreadCount > 0 && (
                    <button className="btn-mark-all" onClick={handleMarkAllRead}>
                      <CheckCheck size={14} /> Marcar lidos
                    </button>
                  )}
                </div>

                {alerts.length === 0 ? (
                  <div className="empty-state">
                    <Compass size={40} className="empty-icon" />
                    <p className="empty-title">Nenhum alerta recente</p>
                    <p className="empty-desc">
                      Não há registros de incêndio a menos de 50 km ou fumaça densa nas suas
                      localizações monitoradas nas últimas 24h.
                    </p>
                  </div>
                ) : (
                  <div className="alerts-list">
                    {alerts.map((alert) => (
                      <div
                        key={alert.id}
                        className={`alert-card ${alert.read_at ? "read" : "unread"} ${
                          alert.alert_type === "FIRE" ? "fire-border" : "smoke-border"
                        }`}
                        onClick={() => !alert.read_at && handleMarkRead(alert.id)}
                      >
                        <div className="alert-card-top">
                          <span
                            className={`alert-pill ${
                              alert.alert_type === "FIRE" ? "pill-fire" : "pill-smoke"
                            }`}
                          >
                            {alert.alert_type === "FIRE" ? (
                              <>
                                <Flame size={12} /> Incêndio
                              </>
                            ) : (
                              <>
                                <Wind size={12} /> Fumaça
                              </>
                            )}
                          </span>
                          <span className="alert-dist">{alert.distance_km} km de distância</span>
                        </div>
                        <h4 className="alert-card-title">{alert.title}</h4>
                        <p className="alert-card-msg">{alert.message}</p>
                        <div className="alert-card-footer">
                          <span className="alert-time">
                            {new Date(alert.created_at).toLocaleString("pt-BR", {
                              day: "2-digit",
                              month: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                          {!alert.read_at && <span className="unread-dot" title="Não lida" />}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab: Locais Monitorados */}
            {activeTab === "locations" && (
              <div className="drawer-content">
                <form className="add-location-form" onSubmit={handleAddLocation}>
                  <h4 className="form-title">
                    <Plus size={16} /> Monitorar Nova Localização
                  </h4>
                  {errorMsg && <p className="form-error">{errorMsg}</p>}

                  <div className="form-group-compact">
                    <label>Nome / Identificação</label>
                    <input
                      type="text"
                      placeholder="Ex: Fazenda Alvorada, Terra Indígena..."
                      value={newLabel}
                      onChange={(e) => setNewLabel(e.target.value)}
                      required
                    />
                  </div>

                  <div className="form-row">
                    <div className="form-group-compact">
                      <label>Latitude</label>
                      <input
                        type="number"
                        step="any"
                        placeholder="-10.50"
                        value={newLat}
                        onChange={(e) => setNewLat(e.target.value)}
                        required
                      />
                    </div>
                    <div className="form-group-compact">
                      <label>Longitude</label>
                      <input
                        type="number"
                        step="any"
                        placeholder="-55.20"
                        value={newLon}
                        onChange={(e) => setNewLon(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div className="form-helper-bar">
                    <button
                      type="button"
                      className="btn-helper"
                      onClick={handleUseCurrentPosition}
                    >
                      <Navigation size={12} /> Obter GPS
                    </button>
                    <span className="radius-tag">Raio fixo: 50 km</span>
                  </div>

                  <button
                    type="submit"
                    className="btn-save-location"
                    disabled={savingLocation}
                  >
                    {savingLocation ? (
                      <>
                        <Loader2 size={14} className="spin" /> Cadastrando...
                      </>
                    ) : (
                      "Ativar Monitoramento (50 km)"
                    )}
                  </button>
                </form>

                <div className="locations-list-wrap">
                  <h4 className="list-title">Locais Ativos</h4>
                  {locations.length === 0 ? (
                    <p className="empty-locations-text">
                      Nenhum local cadastrado ainda. Adicione uma coordenada acima para começar a
                      vigilância automática.
                    </p>
                  ) : (
                    <div className="locations-list">
                      {locations.map((loc) => (
                        <div key={loc.id} className="location-card">
                          <div className="location-info">
                            <div className="location-title-row">
                              <MapPin size={16} className="loc-pin-icon" />
                              <strong className="location-name">{loc.label}</strong>
                            </div>
                            <div className="location-coords">
                              {loc.lat.toFixed(4)}, {loc.lon.toFixed(4)} • Raio {loc.radius_km} km
                            </div>
                          </div>
                          <div className="location-actions">
                            <button
                              className="btn-loc-action"
                              onClick={() => {
                                onFocusLocation(loc.lat, loc.lon);
                                onClose();
                              }}
                              title="Visualizar no mapa"
                            >
                              <Compass size={16} />
                            </button>
                            <button
                              className="btn-loc-action delete"
                              onClick={() => handleDeleteLocation(loc.id)}
                              title="Remover monitoramento"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </aside>
    </div>
  );
};
