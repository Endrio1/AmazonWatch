import React, { useEffect, useState, useRef, useCallback } from "react";
import { Header } from "./components/Header";
import { MapView } from "./components/MapView";
import { TimelineDeck } from "./components/TimelineDeck";
import { PlumeInspector } from "./components/PlumeInspector";
import { Legend } from "./components/Legend";
import {
  fetchStats,
  fetchRegion,
  fetchTimeline,
  fetchPlumes,
  fetchHotspots,
  fetchFrames,
  fetchPlumeDetail,
} from "./api";
import type { FocusRequest, PlumeDetail, SatelliteFrame, StatsSummary } from "./types";

// Janela de focos exibida para um scan — igual à janela da associação no backend
// (assoc_window_before_hours / assoc_window_after_minutes).
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
  const [selectedPlume, setSelectedPlume] = useState<PlumeDetail | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  // Cache em memória para troca instantânea de scans durante a reprodução
  const plumesCache = useRef<Map<string, any>>(new Map());
  const hotspotsCache = useRef<Map<string, any>>(new Map());

  // Estados das camadas
  const [showSatellite, setShowSatellite] = useState<boolean>(true);
  const [showPlumes, setShowPlumes] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showOriginsOnly, setShowOriginsOnly] = useState<boolean>(false);

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
        // Pré-carrega todas as imagens de satélite na memória do navegador para troca sem atraso
        frs.forEach((f) => {
          const img = new Image();
          img.src = f.image_url;
        });
      }

      if (times && times.length > 0) {
        // Focos e plumas são carregados pelo efeito que observa o scan atual
        setTimeline(times);
        setCurrentIdx(times.length - 1); // Último scan (mais recente)
      } else {
        // Ainda não há scans no banco: mostra plumas gerais e focos das últimas 6h
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
    // Atualização periódica a cada 2 minutos
    const interval = setInterval(loadInitialData, 120000);
    return () => clearInterval(interval);
  }, [loadInitialData]);

  // 2. Atualiza plumas e focos com cache instantâneo e pré-busca contínua
  const currentScanTime = timeline[currentIdx];
  useEffect(() => {
    if (!currentScanTime) return;
    let cancelled = false;

    const scanTs = new Date(currentScanTime).getTime();
    const start = new Date(scanTs - HOTSPOT_WINDOW_BEFORE_MS).toISOString();
    const end = new Date(scanTs + HOTSPOT_WINDOW_AFTER_MS).toISOString();
    const hKey = `${start}_${end}`;

    // 1. Plumas (usa cache em memória para resposta instantânea)
    if (plumesCache.current.has(currentScanTime)) {
      setPlumesGeoJSON(plumesCache.current.get(currentScanTime));
    } else {
      fetchPlumes(currentScanTime)
        .then((data) => {
          if (!cancelled) {
            plumesCache.current.set(currentScanTime, data);
            setPlumesGeoJSON(data);
          }
        })
        .catch((err) => console.error("Erro ao atualizar plumas do scan:", err));
    }

    // 2. Focos (usa cache em memória)
    if (hotspotsCache.current.has(hKey)) {
      setHotspotsGeoJSON(hotspotsCache.current.get(hKey));
    } else {
      fetchHotspots(start, end)
        .then((data) => {
          if (!cancelled) {
            hotspotsCache.current.set(hKey, data);
            setHotspotsGeoJSON(data);
          }
        })
        .catch((err) => console.error("Erro ao atualizar focos do scan:", err));
    }

    // 3. Pré-busca dos próximos 2 scans para garantir fluidez perfeita a 60 FPS
    if (isPlaying && timeline.length > 0) {
      for (let offset = 1; offset <= 2; offset++) {
        const nextIdx = (currentIdx + offset) % timeline.length;
        const nextTime = timeline[nextIdx];
        if (nextTime && !plumesCache.current.has(nextTime)) {
          fetchPlumes(nextTime)
            .then((data) => plumesCache.current.set(nextTime, data))
            .catch(() => {});
        }
        if (nextTime) {
          const nTs = new Date(nextTime).getTime();
          const nStart = new Date(nTs - HOTSPOT_WINDOW_BEFORE_MS).toISOString();
          const nEnd = new Date(nTs + HOTSPOT_WINDOW_AFTER_MS).toISOString();
          const nKey = `${nStart}_${nEnd}`;
          if (!hotspotsCache.current.has(nKey)) {
            fetchHotspots(nStart, nEnd)
              .then((data) => hotspotsCache.current.set(nKey, data))
              .catch(() => {});
          }
        }
      }
    }

    return () => {
      cancelled = true;
    };
  }, [currentScanTime, timeline, currentIdx, isPlaying]);

  // Quadro de satélite correspondente ao scan atual
  const currentFrame = React.useMemo(() => {
    if (frames.length === 0) return null;
    if (!currentScanTime) return frames[0];

    const targetTs = new Date(currentScanTime).getTime();
    let best: SatelliteFrame | null = null;
    let minDiff = Infinity;

    for (const f of frames) {
      const diff = Math.abs(new Date(f.scan_time).getTime() - targetTs);
      if (diff < minDiff && diff <= FRAME_MAX_DIFF_MS) {
        minDiff = diff;
        best = f;
      }
    }
    // Retorna o frame mais próximo dentro da tolerância, ou o frame mais recente disponível
    return best || frames[0] || null;
  }, [frames, currentScanTime]);

  // 3. Reprodução automática fluida com taxa de quadros e intervalo otimizados
  const timerRef = useRef<number | null>(null);
  useEffect(() => {
    if (isPlaying && timeline.length > 1) {
      const intervalMs = Math.round(650 / playbackSpeed);
      timerRef.current = window.setInterval(() => {
        setCurrentIdx((prev) => (prev + 1) % timeline.length);
      }, intervalMs);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, timeline.length, playbackSpeed]);

  const handleCycleSpeed = () => {
    setPlaybackSpeed((prev) => {
      if (prev === 0.5) return 1;
      if (prev === 1) return 1.5;
      if (prev === 1.5) return 2;
      return 0.5;
    });
  };

  // 4. Seleção de uma pluma para inspeção
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

  return (
    <div className="app-container">
      {/* Cabeçalho com métricas e controles */}
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
      />

      {/* Mapa central Leaflet */}
      <MapView
        regionGeoJSON={regionGeoJSON}
        plumesGeoJSON={plumesGeoJSON}
        hotspotsGeoJSON={hotspotsGeoJSON}
        selectedPlumeDetail={selectedPlume}
        focusRequest={focusRequest}
        currentFrame={currentFrame}
        showSatellite={showSatellite}
        showPlumes={showPlumes}
        showHotspots={showHotspots}
        showOriginsOnly={showOriginsOnly}
        onSelectPlume={handleSelectPlume}
      />

      {/* Painel lateral de detalhes da pluma */}
      <PlumeInspector
        plume={selectedPlume}
        onClose={() => setSelectedPlume(null)}
        onFocusPlume={handleFocusPlume}
      />

      {/* Legenda flutuante */}
      <Legend showSatellite={showSatellite} />

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
    </div>
  );
};

export default App;
