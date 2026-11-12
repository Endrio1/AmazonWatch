import React, { useEffect, useState, useRef, useCallback } from "react";
import { Header } from "./components/Header";
import { MapView } from "./components/MapView";
import { TimelineDeck } from "./components/TimelineDeck";
import { PlumeInspector } from "./components/PlumeInspector";
import { Legend } from "./components/Legend";
import { AuthModal } from "./components/AuthModal";
import { AlertsDrawer } from "./components/AlertsDrawer";
import {
  fetchStats,
  fetchRegion,
  fetchTimeline,
  fetchPlumes,
  fetchHotspots,
  fetchFrames,
  fetchPlumeDetail,
  fetchCurrentUser,
  fetchUserLocations,
  fetchUserAlerts,
  clearAuthToken,
  getAuthToken,
} from "./api";
import type {
  AlertNotification,
  FocusRequest,
  MonitoredLocation,
  PlumeDetail,
  SatelliteFrame,
  StatsSummary,
  User,
} from "./types";

// Janela de focos exibida para um scan — igual à janela da associação no backend
const HOTSPOT_WINDOW_BEFORE_MS = 6 * 60 * 60 * 1000;
const HOTSPOT_WINDOW_AFTER_MS = 10 * 60 * 1000;
// Tolerância máxima entre o scan de fumaça e o quadro de satélite exibido
const FRAME_MAX_DIFF_MS = 30 * 60 * 1000;

export const App: React.FC = () => {
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [regionGeoJSON, setRegionGeoJSON] = useState<any>(null);
  const [timeline, setTimeline] = useState<string[]>([]);
  const [currentIdx, setCurrentIdx] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  const [plumesGeoJSON, setPlumesGeoJSON] = useState<any>(null);
  const [hotspotsGeoJSON, setHotspotsGeoJSON] = useState<any>(null);
  const [frames, setFrames] = useState<SatelliteFrame[]>([]);
  const [visibleFrameTime, setVisibleFrameTime] = useState<string | null>(null);
  const [selectedPlume, setSelectedPlume] = useState<PlumeDetail | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  // Estados de Autenticação e Alertas de 50km
  const [user, setUser] = useState<User | null>(null);
  const [locations, setLocations] = useState<MonitoredLocation[]>([]);
  const [alerts, setAlerts] = useState<AlertNotification[]>([]);
  const [isAuthOpen, setIsAuthOpen] = useState<boolean>(false);
  const [isAlertsOpen, setIsAlertsOpen] = useState<boolean>(false);
  const [flyToLocation, setFlyToLocation] = useState<{ lat: number; lon: number; nonce: number } | null>(null);

  // Cache em memória para troca instantânea de scans durante a reprodução
  const plumesCache = useRef<Map<string, any>>(new Map());
  const hotspotsCache = useRef<Map<string, any>>(new Map());

  // Estados das camadas
  const [showSatellite, setShowSatellite] = useState<boolean>(true);
  const [showPlumes, setShowPlumes] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showOriginsOnly, setShowOriginsOnly] = useState<boolean>(false);

  // Carrega usuário autenticado
  const refreshUserSession = useCallback(async () => {
    if (!getAuthToken()) {
      setUser(null);
      setLocations([]);
      setAlerts([]);
      return;
    }
    try {
      const u = await fetchCurrentUser();
      setUser(u);
      const [locs, alts] = await Promise.all([
        fetchUserLocations().catch(() => []),
        fetchUserAlerts().catch(() => []),
      ]);
      setLocations(locs);
      setAlerts(alts);
    } catch {
      setUser(null);
    }
  }, []);

  const refreshAlerts = useCallback(async () => {
    if (!getAuthToken()) return;
    try {
      const alts = await fetchUserAlerts();
      setAlerts(alts);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const refreshLocations = useCallback(async () => {
    if (!getAuthToken()) return;
    try {
      const locs = await fetchUserLocations();
      setLocations(locs);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    refreshUserSession();
  }, [refreshUserSession]);

  // Polling de alertas a cada 30s se logado
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(refreshAlerts, 30000);
    return () => clearInterval(interval);
  }, [user, refreshAlerts]);

  // 1. Carregamento inicial (estatísticas, região, focos gerais e timeline)
  const loadInitialData = useCallback(async () => {
    try {
      const [s, reg, times, frs] = await Promise.all([
        fetchStats(6).catch(() => null),
        fetchRegion().catch(() => null),
        fetchTimeline(6).catch(() => []),
        fetchFrames().catch(() => []),
      ]);

      if (s) setStats(s);
      if (reg) setRegionGeoJSON(reg);
      if (frs && frs.length > 0) {
        setFrames(frs);
        frs.forEach((f) => {
          const img = new Image();
          img.src = f.image_url;
        });
      }

      if (times && times.length > 0) {
        setTimeline(times);
        setCurrentIdx(times.length - 1);
      } else {
        const since = new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString();
        const [generalPlumes, hots] = await Promise.all([
          fetchPlumes().catch(() => null),
          fetchHotspots(since).catch(() => null),
        ]);
        if (generalPlumes) setPlumesGeoJSON(generalPlumes);
        if (hots) setHotspotsGeoJSON(hots);
      }
    } catch (err) {
      console.error("Erro ao carregar dados iniciais:", err);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
    const interval = setInterval(loadInitialData, 120000);
    return () => clearInterval(interval);
  }, [loadInitialData]);

  // 2. Atualiza plumas e focos com cache instantâneo e pré-busca contínua
  const currentScanTime = timeline[currentIdx];
  useEffect(() => {
    if (!currentScanTime) return;
    let cancelled = false;

    if (plumesCache.current.has(currentScanTime)) {
      setPlumesGeoJSON(plumesCache.current.get(currentScanTime));
    } else {
      fetchPlumes(currentScanTime)
        .then((plumesData) => {
          if (cancelled) return;
          plumesCache.current.set(currentScanTime, plumesData);
          setPlumesGeoJSON(plumesData);
        })
        .catch(console.error);
    }

    const scanMs = new Date(currentScanTime).getTime();
    const startStr = new Date(scanMs - HOTSPOT_WINDOW_BEFORE_MS).toISOString();
    const endStr = new Date(scanMs + HOTSPOT_WINDOW_AFTER_MS).toISOString();
    const cacheKey = `${startStr}_${endStr}`;

    if (hotspotsCache.current.has(cacheKey)) {
      setHotspotsGeoJSON(hotspotsCache.current.get(cacheKey));
    } else {
      fetchHotspots(startStr, endStr)
        .then((hotspotsData) => {
          if (cancelled) return;
          hotspotsCache.current.set(cacheKey, hotspotsData);
          setHotspotsGeoJSON(hotspotsData);
        })
        .catch(console.error);
    }

    const nextIdx = (currentIdx + 1) % (timeline.length || 1);
    const nextScan = timeline[nextIdx];
    if (nextScan && !plumesCache.current.has(nextScan)) {
      fetchPlumes(nextScan).then((data) => plumesCache.current.set(nextScan, data)).catch(() => {});
    }

    return () => {
      cancelled = true;
    };
  }, [currentScanTime, currentIdx, timeline]);

  // 3. Controle da reprodução da animação
  useEffect(() => {
    if (!isPlaying || timeline.length === 0) return;
    const baseInterval = 1200;
    const interval = setInterval(() => {
      setCurrentIdx((prev) => (prev + 1) % timeline.length);
    }, baseInterval / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, timeline.length, playbackSpeed]);

  const currentFrame = React.useMemo(() => {
    if (!currentScanTime || frames.length === 0) {
      return frames.length > 0 ? frames[frames.length - 1] : null;
    }
    const targetMs = new Date(currentScanTime).getTime();
    let bestFrame: SatelliteFrame | null = null;
    let minDiff = Infinity;

    for (const frame of frames) {
      const fMs = new Date(frame.scan_time).getTime();
      const diff = Math.abs(fMs - targetMs);
      if (diff < minDiff) {
        minDiff = diff;
        bestFrame = frame;
      }
    }
    return minDiff <= FRAME_MAX_DIFF_MS ? bestFrame : frames[frames.length - 1];
  }, [currentScanTime, frames]);

  const handleCycleSpeed = () => {
    setPlaybackSpeed((prev) => {
      if (prev === 0.5) return 1;
      if (prev === 1) return 1.5;
      if (prev === 1.5) return 2;
      return 0.5;
    });
  };

  const handleSelectPlume = async (plumeId: number) => {
    try {
      const detail = await fetchPlumeDetail(plumeId);
      setSelectedPlume(detail);
    } catch (err) {
      console.error("Erro ao inspecionar pluma:", err);
    }
  };

  const handleFocusPlume = (plume: PlumeDetail) => {
    setFocusRequest({ plume, nonce: Date.now() });
  };

  const handleFocusLocation = (lat: number, lon: number) => {
    setFlyToLocation({ lat, lon, nonce: Date.now() });
  };

  const handleLogout = () => {
    clearAuthToken();
    setUser(null);
    setLocations([]);
    setAlerts([]);
  };

  const unreadAlertsCount = alerts.filter((a) => !a.read_at).length;

  return (
    <div className="app-container">
      {/* Cabeçalho com métricas, controles de camadas, sino de alertas e login */}
      <Header
        stats={stats}
        showSatellite={showSatellite}
        onToggleSatellite={() => setShowSatellite(!showSatellite)}
        showPlumes={showPlumes}
        onTogglePlumes={() => setShowPlumes(!showPlumes)}
        showHotspots={showHotspots}
        onToggleHotspots={() => setShowHotspots(!showHotspots)}
        showOriginsOnly={showOriginsOnly}
        onToggleOriginsOnly={() => setShowOriginsOnly(!showOriginsOnly)}
        user={user}
        unreadAlertsCount={unreadAlertsCount}
        onOpenAlerts={() => setIsAlertsOpen(true)}
        onOpenAuth={() => setIsAuthOpen(true)}
        onLogout={handleLogout}
      />

      {/* Mapa central Leaflet com círculos de monitoramento de 50km */}
      <MapView
        regionGeoJSON={regionGeoJSON}
        plumesGeoJSON={plumesGeoJSON}
        hotspotsGeoJSON={hotspotsGeoJSON}
        selectedPlumeDetail={selectedPlume}
        focusRequest={focusRequest}
        currentFrame={currentFrame}
        onVisibleFrameChange={setVisibleFrameTime}
        showSatellite={showSatellite}
        showPlumes={showPlumes}
        showHotspots={showHotspots}
        showOriginsOnly={showOriginsOnly}
        userLocations={locations}
        flyToLocation={flyToLocation}
        onSelectPlume={handleSelectPlume}
      />

      {/* Painel lateral de detalhes da pluma */}
      <PlumeInspector
        plume={selectedPlume}
        onClose={() => setSelectedPlume(null)}
        onFocusPlume={handleFocusPlume}
      />

      {/* Legenda flutuante */}
      <Legend showSatellite={showSatellite} satelliteScanTime={visibleFrameTime} />

      {/* Linha do tempo inferior com player */}
      <TimelineDeck
        timeline={timeline}
        currentIndex={currentIdx}
        onSelectIndex={(idx) => {
          setIsPlaying(false);
          setCurrentIdx(idx);
        }}
        isPlaying={isPlaying}
        onTogglePlay={() => setIsPlaying(!isPlaying)}
        playbackSpeed={playbackSpeed}
        onCycleSpeed={handleCycleSpeed}
      />

      {/* Modal de Autenticação / Cadastro de Usuário */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onSuccess={(newUser) => {
          setUser(newUser);
          refreshUserSession();
          setIsAlertsOpen(true);
        }}
      />

      {/* Painel lateral de Notificações e Locais Monitorados (50 km) */}
      <AlertsDrawer
        isOpen={isAlertsOpen}
        onClose={() => setIsAlertsOpen(false)}
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
        locations={locations}
        onRefreshLocations={refreshLocations}
        alerts={alerts}
        onRefreshAlerts={refreshAlerts}
        onFocusLocation={handleFocusLocation}
      />
    </div>
  );
};

export default App;
