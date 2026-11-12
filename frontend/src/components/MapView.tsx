import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { FocusRequest, MonitoredLocation, PlumeDetail, SatelliteFrame } from "../types";

// Recorte da Amazônia Legal e do entorno mostrado nas imagens de referência.
const MAP_BOUNDS = L.latLngBounds([-18, -82], [10, -39]);
const ZOOM_SNAP = 0.25;

interface MapViewProps {
  regionGeoJSON: any;
  plumesGeoJSON: any;
  hotspotsGeoJSON: any;
  selectedPlumeDetail: PlumeDetail | null;
  focusRequest: FocusRequest | null;
  currentFrame: SatelliteFrame | null;
  onVisibleFrameChange: (scanTime: string | null) => void;
  showSatellite: boolean;
  showPlumes: boolean;
  showHotspots: boolean;
  showOriginsOnly: boolean;
  userLocations?: MonitoredLocation[];
  flyToLocation?: { lat: number; lon: number; nonce: number } | null;
  onSelectPlume: (plumeId: number) => void;
}

export const MapView: React.FC<MapViewProps> = ({
  regionGeoJSON,
  plumesGeoJSON,
  hotspotsGeoJSON,
  selectedPlumeDetail,
  focusRequest,
  currentFrame,
  onVisibleFrameChange,
  showSatellite,
  showPlumes,
  showHotspots,
  showOriginsOnly,
  userLocations = [],
  flyToLocation,
  onSelectPlume,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);

  // Referências para camadas dinâmicas
  const regionLayerRef = useRef<L.GeoJSON | null>(null);
  const satelliteOverlayRef = useRef<L.ImageOverlay | null>(null);
  const previousOverlayRef = useRef<L.ImageOverlay | null>(null);
  const canvasRendererRef = useRef<L.Canvas | null>(null);
  const plumesLayerRef = useRef<L.GeoJSON | null>(null);
  const hotspotsLayerRef = useRef<L.LayerGroup | null>(null);
  const connectorLinesRef = useRef<L.LayerGroup | null>(null);
  const userLocationsLayerRef = useRef<L.LayerGroup | null>(null);


  // Inicialização do mapa Leaflet
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, {
      zoomSnap: ZOOM_SNAP,
      maxZoom: 18,
      maxBounds: MAP_BOUNDS,
      maxBoundsViscosity: 1,
      zoomControl: false,
      attributionControl: false,
    });

    const northWest = map.project(MAP_BOUNDS.getNorthWest(), 0);
    const southEast = map.project(MAP_BOUNDS.getSouthEast(), 0);
    const boundsSize = southEast.subtract(northWest);
    const overviewZoom = () => {
      const { x, y } = map.getSize();
      const scale = Math.max(x / boundsSize.x, y / boundsSize.y);
      return Math.ceil(map.getScaleZoom(scale, 0) / ZOOM_SNAP) * ZOOM_SNAP;
    };
    const initialZoom = overviewZoom();
    map.setMinZoom(initialZoom);
    map.setView(map.unproject(northWest.add(southEast).divideBy(2), 0), initialZoom);
    map.on("resize", () => map.setMinZoom(overviewZoom()));

    // 1. Basemap base escuro de alta performance (sem chave de API e sem marcas d'água)
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 18,
        noWrap: true,
      }
    ).addTo(map);

    // 2. Cria panes personalizadas para renderização das camadas estilo DSAT
    if (!map.getPane("satellite-pane")) {
      const satPane = map.createPane("satellite-pane");
      satPane.style.zIndex = "250";
    }
    if (!map.getPane("boundaries-pane")) {
      const boundPane = map.createPane("boundaries-pane");
      boundPane.style.zIndex = "350";
      boundPane.style.pointerEvents = "none";
    }

    // 3. Camada de fronteiras e divisas estaduais/nacionais sobrepostas (estilo DSAT do CPTEC)
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 18,
        noWrap: true,
        opacity: 0.8,
        pane: "boundaries-pane",
      }
    ).addTo(map);

    // Controles de zoom no canto inferior direito
    L.control.zoom({ position: "bottomright" }).addTo(map);

    canvasRendererRef.current = L.canvas({ padding: 0.5 });
    hotspotsLayerRef.current = L.layerGroup().addTo(map);
    connectorLinesRef.current = L.layerGroup().addTo(map);
    userLocationsLayerRef.current = L.layerGroup().addTo(map);

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // 1. Limite da Amazônia Legal
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (regionLayerRef.current) {
      map.removeLayer(regionLayerRef.current);
      regionLayerRef.current = null;
    }

    if (regionGeoJSON) {
      regionLayerRef.current = L.geoJSON(regionGeoJSON, {
        style: {
          color: "#10b981",
          weight: 1.5,
          opacity: 0.6,
          dashArray: "4, 4",
          fill: false,
        },
      }).addTo(map);
    }
  }, [regionGeoJSON]);

  // 2. Sobreposição do quadro de satélite True Color com Crossfade suave (sem piscar)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (!showSatellite || !currentFrame) {
      if (satelliteOverlayRef.current) {
        map.removeLayer(satelliteOverlayRef.current);
        satelliteOverlayRef.current = null;
      }
      if (previousOverlayRef.current) {
        map.removeLayer(previousOverlayRef.current);
        previousOverlayRef.current = null;
      }
      onVisibleFrameChange(null);
      return;
    }

    // Se já é a mesma imagem, não recria
    if (
      satelliteOverlayRef.current &&
      (satelliteOverlayRef.current as any)._aw_frame_id === currentFrame.id
    ) {
      return;
    }

    const bounds: L.LatLngBoundsExpression = [
      [currentFrame.south, currentFrame.west],
      [currentFrame.north, currentFrame.east],
    ];

    // Guarda a camada atual para fazer o crossfade
    if (satelliteOverlayRef.current) {
      if (satelliteOverlayRef.current.options.opacity === 0) {
        map.removeLayer(satelliteOverlayRef.current);
      } else {
        previousOverlayRef.current = satelliteOverlayRef.current;
      }
    }

    const newOverlay = L.imageOverlay(currentFrame.image_url, bounds, {
      opacity: 0.0,
      className: "satellite-crossfade",
      interactive: false,
      pane: "satellite-pane",
    }).addTo(map);

    (newOverlay as any)._aw_frame_id = currentFrame.id;
    satelliteOverlayRef.current = newOverlay;

    // Quando a imagem carregar, faz o crossfade suave
    const onImgLoad = () => {
      if (satelliteOverlayRef.current !== newOverlay) return;
      newOverlay.setOpacity(0.95);
      onVisibleFrameChange(currentFrame.scan_time);
      if (previousOverlayRef.current) {
        const oldLayer = previousOverlayRef.current;
        previousOverlayRef.current = null;
        setTimeout(() => {
          if (map.hasLayer(oldLayer)) {
            map.removeLayer(oldLayer);
          }
        }, 320);
      }
    };

    const imgEl = newOverlay.getElement();
    if (imgEl instanceof HTMLImageElement && imgEl.complete && imgEl.naturalWidth > 0) {
      onImgLoad();
    } else {
      newOverlay.on("load", onImgLoad);
    }
  }, [showSatellite, currentFrame, onVisibleFrameChange]);

  // 3. Polígonos das plumas de fumaça (NOAA GOES-19)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (plumesLayerRef.current) {
      map.removeLayer(plumesLayerRef.current);
      plumesLayerRef.current = null;
    }

    if (showPlumes && plumesGeoJSON) {
      plumesLayerRef.current = L.geoJSON(plumesGeoJSON, {
        style: (feature) => {
          const isSelected = selectedPlumeDetail?.id === feature?.properties?.id;
          return {
            color: isSelected ? "#f59e0b" : "#38bdf8",
            weight: isSelected ? 2.5 : 1.5,
            fillColor: isSelected ? "#f59e0b" : "#38bdf8",
            fillOpacity: isSelected ? 0.45 : 0.28,
          };
        },
        onEachFeature: (feature, layer) => {
          layer.on({
            click: () => onSelectPlume(feature.properties.id),
            mouseover: () => {
              (layer as L.Path).setStyle({ fillOpacity: 0.55, weight: 2.5 });
            },
            mouseout: () => {
              const isSelected = selectedPlumeDetail?.id === feature.properties.id;
              (layer as L.Path).setStyle({
                fillOpacity: isSelected ? 0.45 : 0.28,
                weight: isSelected ? 2.5 : 1.5,
              });
            },
          });

          const p = feature.properties;
          layer.bindTooltip(
            `<strong>Pluma #${p.id}</strong><br/>Área: ${p.area_km2} km²<br/>Focos: ${p.hotspots_count} (${p.origins_count} origens)`,
            { sticky: true, className: "custom-leaflet-tooltip" }
          );
        },
      }).addTo(map);
    }
  }, [showPlumes, plumesGeoJSON, selectedPlumeDetail, onSelectPlume]);

  // 4. Focos de incêndio (BDQueimadas)
  useEffect(() => {
    const group = hotspotsLayerRef.current;
    if (!group) return;
    group.clearLayers();

    if (!showHotspots || !hotspotsGeoJSON) return;

    const originHotspotIds = new Set(
      selectedPlumeDetail?.links.filter((l) => l.is_origin).map((l) => l.hotspot_id) || []
    );

    hotspotsGeoJSON.features.forEach((feat: any) => {
      const p = feat.properties;
      const isOrigin = originHotspotIds.has(p.id);

      if (showOriginsOnly && !isOrigin) return;

      const [lon, lat] = feat.geometry.coordinates;
      const marker = L.circleMarker([lat, lon], {
        radius: isOrigin ? 7 : 3.5,
        color: isOrigin ? "#ef4444" : "#f97316",
        fillColor: isOrigin ? "#dc2626" : "#ea580c",
        fillOpacity: isOrigin ? 0.95 : 0.7,
        weight: isOrigin ? 2 : 1,
        renderer: canvasRendererRef.current || undefined,
      });

      marker.bindTooltip(
        `<strong>Foco #${p.id}</strong>${isOrigin ? " <span style='color:#ef4444'>(Origem de Pluma)</span>" : ""}<br/>Satélite: ${p.satellite}<br/>Horário: ${new Date(p.detected_at).toLocaleTimeString()}`
      );

      group.addLayer(marker);
    });
  }, [showHotspots, showOriginsOnly, hotspotsGeoJSON, selectedPlumeDetail]);

  // 5. Linhas de conexão animadas (Origem do Foco -> Centróide da Pluma)
  useEffect(() => {
    const group = connectorLinesRef.current;
    if (!group) return;
    group.clearLayers();

    if (!selectedPlumeDetail || !selectedPlumeDetail.centroid) return;

    const [cLon, cLat] = selectedPlumeDetail.centroid.coordinates;

    selectedPlumeDetail.links.forEach((link) => {
      if (!link.is_origin) return;

      const polyline = L.polyline(
        [
          [link.lat, link.lon],
          [cLat, cLon],
        ],
        {
          color: "#f59e0b",
          weight: 2,
          opacity: 0.9,
          className: "origin-connecting-line",
        }
      );

      polyline.bindTooltip(
        `Vínculo de Origem: Foco #${link.hotspot_id} ➔ Pluma #${selectedPlumeDetail.id}<br/>Distância: ${link.distance_km} km | Confiança: ${(link.score * 100).toFixed(0)}%`
      );

      group.addLayer(polyline);
    });
  }, [selectedPlumeDetail]);

  // 6. Enquadramento sob demanda: pluma + focos de origem
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusRequest) return;
    const { plume } = focusRequest;

    let bounds: L.LatLngBounds | null = null;
    if (plume.geometry) {
      const b = L.geoJSON(plume.geometry).getBounds();
      if (b.isValid()) bounds = b;
    }
    for (const link of plume.links) {
      if (!link.is_origin) continue;
      const pt = L.latLng(link.lat, link.lon);
      bounds = bounds ? bounds.extend(pt) : L.latLngBounds(pt, pt);
    }
    if (!bounds) return;

    map.flyToBounds(bounds, {
      paddingTopLeft: [60, 110], // cabeçalho
      paddingBottomRight: [420, 140], // painel lateral + timeline
      maxZoom: 9,
      duration: 0.8,
    });
  }, [focusRequest]);

  // 7. Renderização dos locais monitorados pelo usuário (raio 50km)
  useEffect(() => {
    const group = userLocationsLayerRef.current;
    if (!group) return;
    group.clearLayers();

    userLocations.forEach((loc) => {
      // Círculo translúcido com raio de 50 km (50.000m)
      const circle = L.circle([loc.lat, loc.lon], {
        radius: (loc.radius_km || 50.0) * 1000,
        color: "#06b6d4",
        weight: 1.5,
        opacity: 0.8,
        fillColor: "#0891b2",
        fillOpacity: 0.12,
        dashArray: "6, 6",
      });

      circle.bindTooltip(
        `<strong>📍 ${loc.label}</strong><br/>Raio de Monitoramento: ${loc.radius_km || 50} km<br/>Vigilância ativa para Incêndios e Fumaça`,
        { sticky: true }
      );

      // Marcador central com radar
      const centerMarker = L.circleMarker([loc.lat, loc.lon], {
        radius: 6,
        color: "#ffffff",
        fillColor: "#06b6d4",
        fillOpacity: 1,
        weight: 2,
      });

      centerMarker.bindPopup(
        `<div style="color: #0f172a; font-family: sans-serif;">
          <h4 style="margin: 0 0 4px 0; font-size: 14px;">📍 ${loc.label}</h4>
          <p style="margin: 0; font-size: 12px; color: #475569;">
            Raio de alerta: <strong>${loc.radius_km || 50} km</strong><br/>
            Coordenadas: ${loc.lat.toFixed(4)}, ${loc.lon.toFixed(4)}
          </p>
        </div>`
      );

      group.addLayer(circle);
      group.addLayer(centerMarker);
    });
  }, [userLocations]);

  // 8. Foco em local monitorado
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyToLocation) return;
    map.flyTo([flyToLocation.lat, flyToLocation.lon], 8.5, {
      duration: 1,
    });
  }, [flyToLocation]);

  return <div ref={mapContainerRef} className="map-viewport" id="amazonwatch-map" />;
};

