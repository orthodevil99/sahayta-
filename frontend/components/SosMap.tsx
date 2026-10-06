"use client";
/**
 * SosMap — Leaflet map with severity heat layer + SOS pins + shelter markers.
 * Loaded with ssr:false (Leaflet needs window). The adjacent text list is the
 * screen-reader source of truth (design-system §8); the map itself is
 * aria-hidden. OSM tiles default; CartoDB dark_matter in dark mode.
 */
import { useEffect, useRef } from "react";
import type { Shelter, SOSReport } from "../lib/types";
import { severityStyle } from "./SeverityBadge";
import HeatmapLegend from "./HeatmapLegend";

const HEAT_COLOR: Record<number, string> = { 1: "#22C55E", 2: "#65A30D", 3: "#EAB308", 4: "#F97316", 5: "#DC2626" };

export default function SosMap({
  reports, shelters = [], center = [25.5941, 85.1376], zoom = 11,
  showHeatmap = true, height = 320, onPinClick, selectedId,
}: {
  reports: SOSReport[];
  shelters?: Shelter[];
  center?: [number, number];
  zoom?: number;
  showHeatmap?: boolean;
  height?: number;
  onPinClick?: (id: string) => void;
  selectedId?: string | null;
}) {
  const divRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const layerRef = useRef<import("leaflet").LayerGroup | null>(null);
  const cbRef = useRef(onPinClick);
  cbRef.current = onPinClick;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      await import("leaflet/dist/leaflet.css");
      if (cancelled || !divRef.current || mapRef.current) return;
      const dark = document.documentElement.classList.contains("dark");
      const map = L.map(divRef.current, { zoomControl: true, attributionControl: true }).setView(center, zoom);
      mapRef.current = map;
      const tiles = dark
        ? L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { attribution: "&copy; OpenStreetMap &copy; CARTO", maxZoom: 19, className: "map-tiles" })
        : L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap contributors", maxZoom: 19, className: "map-tiles" });
      tiles.addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      // Re-render pins if theme toggles.
      const obs = new MutationObserver(() => {
        const isDark = document.documentElement.classList.contains("dark");
        tiles.setUrl(isDark
          ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png");
      });
      obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
      (map as unknown as { _sahaytaObs: MutationObserver })._sahaytaObs = obs;
    })();
    return () => { cancelled = true; };
  }, []); // mount once

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    (async () => {
      const L = (await import("leaflet")).default;
      layer.clearLayers();
      const withGeo = reports.filter((r) => r.lat != null && r.lon != null);
      if (showHeatmap) {
        for (const r of withGeo) {
          const sev = r.severity ?? 1;
          L.circle([r.lat!, r.lon!], {
            radius: 400 + sev * 500, color: "transparent",
            fillColor: HEAT_COLOR[sev], fillOpacity: 0.22, interactive: false,
          }).addTo(layer);
        }
      }
      for (const r of withGeo) {
        const sev = r.severity ?? 1;
        const st = severityStyle(sev as 1 | 2 | 3 | 4 | 5);
        const size = r.id === selectedId ? 44 : 34;
        const icon = L.divIcon({
          className: "",
          html: `<div class="sos-pin" style="width:${size}px;height:${size}px;background:${sev === 5 ? "#7F1D1D" : st.bg};font-size:${size > 38 ? 16 : 13}px">${sev}</div>`,
          iconSize: [size, size], iconAnchor: [size / 2, size / 2],
        });
        const m = L.marker([r.lat!, r.lon!], { icon, keyboard: false });
        m.on("click", () => cbRef.current?.(r.id));
        m.addTo(layer);
      }
      for (const s of shelters) {
        const icon = L.divIcon({
          className: "",
          html: `<div style="width:30px;height:30px;border-radius:9999px;background:#1D4ED8;border:3px solid #fff;display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;box-shadow:0 2px 8px rgb(0 0 0 / .35)">⛺</div>`,
          iconSize: [30, 30], iconAnchor: [15, 15],
        });
        L.marker([s.lat, s.lon], { icon, keyboard: false, title: s.name }).addTo(layer);
      }
    })();
  }, [reports, shelters, showHeatmap, selectedId]);

  useEffect(() => {
    return () => {
      const map = mapRef.current;
      if (map) {
        (map as unknown as { _sahaytaObs?: MutationObserver })._sahaytaObs?.disconnect();
        map.remove();
        mapRef.current = null;
      }
    };
  }, []);

  return (
    <div className="relative overflow-hidden rounded-card border border-line" aria-hidden="true">
      <div ref={divRef} style={{ height }} className="w-full" />
      {showHeatmap && <HeatmapLegend />}
    </div>
  );
}
