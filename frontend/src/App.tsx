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

  // Estados das camadas
  const [showSatellite, setShowSatellite] = useState<boolean>(true);
  const [showPlumes, setShowPlumes] = useState<boolean>(true);
  const [showHotspots, setShowHotspots] = useState<boolean>(true);
  const [showOriginsOnly, setShowOriginsOnly] = useState<boolean>(false);

  // 1. Carregamento inicial (estatísticas, região, focos gerais e timeline)
  const loadInitialData = useCallback(async () => {
    try {
      const [s, reg, times, frs] = await Promise.all([
        fetchStats(24).catch(() => null),
        fetchRegion().catch(() => null),
        fetchTimeline().catch(() => []),
        fetchFrames().catch(() => []),
      ]);

      if (s) setStats(s);
      if (reg) setRegionGeoJSON(reg);
      if (frs) setFrames(frs);

      if (times && times.length > 0) {
        // Focos e plumas são carregados pelo efeito que observa o scan atual
        setTimeline(times);
        setCurrentIdx(times.length - 1); // Último scan (mais recente)
      } else {
        // Ainda não há scans no banco: mostra plumas gerais e focos das últimas 24h
        const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
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

  // 2. Atualiza plumas e focos quando o scan selecionado na timeline muda
  const currentScanTime = timeline[currentIdx];
  useEffect(() => {
    if (!currentScanTime) return;
    let cancelled = false; // descarta respostas atrasadas durante a reprodução

    const scanTs = new Date(currentScanTime).getTime();
    const start = new Date(scanTs - HOTSPOT_WINDOW_BEFORE_MS).toISOString();
    const end = new Date(scanTs + HOTSPOT_WINDOW_AFTER_MS).toISOString();

    fetchPlumes(currentScanTime)
      .then((data) => !cancelled && setPlumesGeoJSON(data))
      .catch((err) => console.error("Erro ao atualizar plumas do scan:", err));
    fetchHotspots(start, end)
      .then((data) => !cancelled && setHotspotsGeoJSON(data))
      .catch((err) => console.error("Erro ao atualizar focos do scan:", err));

    return () => {
      cancelled = true;
    };
    // `timeline` entra nas dependências para recarregar no refresh periódico
  }, [currentScanTime, timeline]);

  // Quadro de satélite correspondente ao scan atual
  const currentFrame = React.useMemo(() => {
    if (frames.length === 0) return null;
    // Sem timeline: usa o quadro mais recente (a API ordena por scan_time desc)
    if (!currentScanTime) return frames[0];

    const targetTs = new Date(currentScanTime).getTime();
    // Frame mais próximo dentro da tolerância; se nenhum existir, não exibe
    // imagem de outro horário (evita fumaça e fundo dessincronizados)
    let best: SatelliteFrame | null = null;
    let minDiff = Infinity;

    for (const f of frames) {
      const diff = Math.abs(new Date(f.scan_time).getTime() - targetTs);
      if (diff < minDiff && diff <= FRAME_MAX_DIFF_MS) {
        minDiff = diff;
        best = f;
      }
    }
    return best;
  }, [frames, currentScanTime]);

  // 3. Reprodução automática da linha do tempo
  const timerRef = useRef<number | null>(null);
  useEffect(() => {
    if (isPlaying && timeline.length > 1) {
      timerRef.current = window.setInterval(() => {
        setCurrentIdx((prev) => (prev + 1) % timeline.length);
      }, 2400);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, timeline.length]);

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
      />
    </div>
  );
};

export default App;
