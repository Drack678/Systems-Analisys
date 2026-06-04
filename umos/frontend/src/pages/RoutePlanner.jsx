import { useState, useEffect } from "react";
import { MapContainer, TileLayer, Polyline, Circle, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import AppNav from "../components/AppNav.jsx";
import RouteCard from "../components/RouteCard.jsx";
import RouteSegmentsPanel from "../components/RouteSegmentsPanel.jsx";
import RainAlert from "../components/RainAlert.jsx";
import DataFreshnessBadge from "../components/DataFreshnessBadge.jsx";
import { FacultyDot, AntMarkers, animateAnts } from "../components/TransitSimulation.jsx";
import {
  getCampuses, getWeather, optimizeRoute, getTransmilenioRecommendations,
  getDataFreshness,
} from "../services/api.js";

const MODES = [
  { id: "sitp", icon: "🚐", label: "SITP", color: "#14b8a6" },
  { id: "tm", icon: "🚌", label: "TransMilenio", color: "#e11d48" },
  { id: "driving", icon: "🚗", label: "Carro", color: "#64748b" },
  { id: "cycling", icon: "🚲", label: "Bici", color: "#22c55e" },
  { id: "walking", icon: "🚶", label: "A pie", color: "#f59e0b" },
];

const ALT_COLORS = ["#3b82f6", "#e3b341", "#f85149"];

// Filtra paraderos/estaciones del grafo. Sus codes empiezan con TM- o SITP-
// y son nodos internos para el ACO, no deben aparecer en dropdowns ni en el mapa.
function isFaculty(c) {
  return c && !c.code?.startsWith("TM-") && !c.code?.startsWith("SITP-");
}

/**
 * Recorta la geometría completa de un bus a solo el pedazo entre 2 puntos.
 * Encuentra el punto más cercano al inicio y al fin, y devuelve solo
 * el tramo entre ellos. Si los índices vienen al revés (geometría
 * invertida), los corrige automáticamente.
 */
function clipGeometryToSegment(fullGeom, startPoint, endPoint) {
  if (!fullGeom?.length || !startPoint || !endPoint) return fullGeom;

  const distSq = (a, b) => {
    const dx = a[0] - b[0];
    const dy = a[1] - b[1];
    return dx * dx + dy * dy;
  };

  let startIdx = 0, endIdx = 0;
  let minStart = Infinity, minEnd = Infinity;

  for (let i = 0; i < fullGeom.length; i++) {
    const dS = distSq(fullGeom[i], startPoint);
    const dE = distSq(fullGeom[i], endPoint);
    if (dS < minStart) { minStart = dS; startIdx = i; }
    if (dE < minEnd)   { minEnd = dE;   endIdx = i; }
  }

  // Si el "end" está antes que el "start", invertimos la geometría
  if (endIdx < startIdx) {
    return fullGeom.slice(endIdx, startIdx + 1).reverse();
  }
  return fullGeom.slice(startIdx, endIdx + 1);
}

function FitRoute({ coords }) {
  const map = useMap();
  useEffect(() => {
    if (coords?.length > 1) map.fitBounds(coords, { padding: [60, 60], animate: true });
  }, [coords, map]);
  return null;
}

export default function RoutePlanner() {
  const [campuses, setCampuses] = useState([]);
  const [origin, setOrigin] = useState("");
  const [dest, setDest] = useState("");
const [mode, setMode] = useState("sitp");
  const [rain, setRain] = useState(false);
  const [route, setRoute] = useState(null);
  const [selAlt, setSelAlt] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [weather, setWeather] = useState(null);
  const [freshness, setFreshness] = useState([]);
  const [transit, setTransit] = useState(null);
  const [tick, setTick] = useState(0);
  const [selTmRoute, setSelTmRoute] = useState(null);

  useEffect(() => {
    getCampuses().then((data) => {
      setCampuses(data);
      // Si la URL trae parámetros (link compartido), precargamos la ruta
      const params = new URLSearchParams(window.location.search);
      const oid = params.get("o");
      const did = params.get("d");
      const m = params.get("m");
      const r = params.get("r");
      if (oid && data.some((c) => c.id === +oid)) setOrigin(oid);
      if (did && data.some((c) => c.id === +did)) setDest(did);
      if (m && ["sitp", "tm", "driving", "cycling", "walking"].includes(m)) setMode(m);
      if (r === "1") setRain(true);
    }).catch(() => setError("Backend no disponible en localhost:8000"));
    getWeather().then(setWeather).catch(() => {});
    getDataFreshness().then(setFreshness).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 800);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!["sitp", "tm"].includes(mode) || !origin || !dest || origin === dest || !campuses.length) {
      setTransit(null);
      return;
    }
    const o = campuses.find((c) => c.id === +origin);
    const d = campuses.find((c) => c.id === +dest);
    if (!o || !d) return;
    getTransmilenioRecommendations(o, d)
      .then((data) => {
        setTransit(data);
        setSelTmRoute(data.recommended_routes?.[0]?.route_id || null);
      })
      .catch(() => setTransit(null));
  }, [mode, origin, dest, campuses]);

  async function handleOptimize(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setRoute(null);
    setSelAlt(0);
    try {
      const data = await optimizeRoute(+origin, +dest, mode, rain);
      setRoute(data);
      // Guardar la ruta en localStorage para modo offline
      try {
        localStorage.setItem("umos_last_route", JSON.stringify({
          route: data,
          origin_id: +origin,
          dest_id: +dest,
          mode,
          rain,
          saved_at: Date.now(),
        }));
      } catch {
        // localStorage puede fallar si está lleno o deshabilitado, ignoramos
      }
    } catch (err) {
      setError(err.message);
      // Si el backend falla, intentar cargar la última ruta guardada
      try {
        const saved = localStorage.getItem("umos_last_route");
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed.origin_id === +origin && parsed.dest_id === +dest && parsed.mode === mode) {
            setRoute(parsed.route);
            const ageMin = Math.round((Date.now() - parsed.saved_at) / 60000);
            setError(`Sin conexión al backend. Mostrando ruta guardada hace ${ageMin} min.`);
          }
        }
      } catch {}
    } finally {
      setLoading(false);
    }
  }

  const allRoutes = route ? [route.selected, ...(route.alternatives || [])] : [];
  const activeRoute = allRoutes[selAlt];
  const routeCoords = activeRoute?.geometry || [];
  const baseSegments = activeRoute?.segments || [];

  // Enriquecemos segmentos TM con datos reales de la recomendación GTFS
  // para que el panel "Paso a paso" mencione la ruta y estaciones reales.
const tmRecommendation = transit?.recommended_routes?.[0];
  const tmOriginStop = transit?.origin_stop?.name;
  const tmDestStop = transit?.dest_stop?.name;

// Track del primer segmento TM para usar el origen del GTFS solo ahí.
  let firstTmFound = false;
  const tmSegmentsTotal = baseSegments.filter((s) => s.mode === "TM").length;
  let currentTmIdx = 0;

  const routeSegments = baseSegments.map((seg) => {
    if (seg.mode !== "TM" || !tmRecommendation) {
      return seg;
    }
    currentTmIdx += 1;
    const isFirstTm = !firstTmFound;
    const isLastTm = currentTmIdx === tmSegmentsTotal;
    if (!firstTmFound) firstTmFound = true;

    const shortName = tmRecommendation.short_name || tmRecommendation.route_id || "TM";
    const boardAt = isFirstTm
      ? (tmOriginStop || seg.from_name)
      : seg.from_name;
    const alightAt = seg.to_name;

    // Reemplazamos la geometría OSRM (que sigue calles vehiculares) por la
    // geometría real del bus del GTFS, que va por la troncal exclusiva.
    let enrichedGeometry = seg.geometry;
    if (tmRecommendation.geometry?.length > 2) {
      enrichedGeometry = clipGeometryToSegment(
        tmRecommendation.geometry,
        seg.geometry[0],
        seg.geometry[seg.geometry.length - 1]
      );
    }

    return {
      ...seg,
      instruction: `Toma Ruta ${shortName} desde ${boardAt} hasta ${alightAt}`,
      mode: shortName,
      color: tmRecommendation.color || seg.color,
      geometry: enrichedGeometry,
    };
  });

  const tmRoutes = transit?.recommended_routes || transit?.routes || [];
  const antVehicles = animateAnts(tmRoutes, tick);

  // Solo facultades para selectores y dots del mapa
  const facultyCampuses = campuses.filter(isFaculty);
  const originCampus = facultyCampuses.find((c) => c.id === +origin);
  const destCampus = facultyCampuses.find((c) => c.id === +dest);

  return (
    <div className="layout">
      <aside className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-logo-text">UMOS</div>
            <div className="panel-logo-sub">GTFS TransMilenio + ACO</div>
          </div>
        </div>
        <AppNav />

        <div className="panel-body">
	        <RainAlert
            weather={weather}
            rainActive={rain}
            onActivateRain={() => setRain(true)}
          />

          {weather && (
            <div className={`weather-strip ${weather.is_raining ? "raining" : ""}`}>
              {weather.is_raining
                ? `Lluvia ${weather.rain_mm} mm/h`
                : `${weather.description || "Despejado"} · ${weather.temp}°C`}
            </div>
          )}

          <div>
            <div className="section-label">Modo</div>
            <div className="mode-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
              {MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className={`mode-btn ${mode === m.id ? "active" : ""}`}
                  onClick={() => setMode(m.id)}
                  style={mode === m.id ? { borderColor: m.color, color: m.color } : {}}
                >
                  <span className="mode-btn-icon">{m.icon}</span>
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleOptimize} style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
            {[["Origen", origin, setOrigin], ["Destino", dest, setDest]].map(([lbl, val, set]) => (
              <div key={lbl}>
                <label className="section-label">{lbl}</label>
                <select value={val} onChange={(e) => set(e.target.value)} required>
                  <option value="">Facultad...</option>
                  {facultyCampuses.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            ))}
            <label className="toggle-row">
              <span className="toggle-label">Simular lluvia</span>
              <div className={`toggle ${rain ? "on" : ""}`} onClick={() => setRain((r) => !r)} role="switch" />
            </label>
            <button type="submit" className="btn-optimize" disabled={loading || !origin || !dest || origin === dest}>
              {loading ? <span className="spinner" /> : "Calcular ruta ACO"}
            </button>
          </form>

          {transit?.summary && ["sitp", "tm"].includes(mode) && (
            <div className="result-box" style={{ padding: "0.75rem", borderColor: "#e11d48" }}>
              <div className="section-label" style={{ color: "#e11d48" }}>Recomendación GTFS</div>
              <p style={{ fontSize: "0.8rem", lineHeight: 1.45 }}>{transit.summary}</p>
              {transit.origin_stop && (
                <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 6 }}>
                  Estación origen: {transit.origin_stop.name} ({transit.origin_stop.distance_m} m)
                </p>
              )}
            </div>
          )}

          {error && (
            <div
              className="error-box"
              style={error.includes("Sin conexión") ? {
                background: "#3d2914",
                borderColor: "#f59e0b",
                color: "#f59e0b",
              } : undefined}
            >
              {error.includes("Sin conexión") ? "📡 " : "⚠ "}
              {error}
            </div>
          )}

          {allRoutes.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div className="section-label">Ruta ACO ({route.computation_time_ms?.toFixed(0)} ms)</div>
              {allRoutes.map((r, i) => (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  <RouteCard route={r} selected={selAlt === i} onSelect={() => setSelAlt(i)} index={i} />
                  {selAlt === i && <RouteSegmentsPanel route={r} />}
                  {selAlt === i && (
                    <ShareRouteButton
                      route={r}
                      origin={originCampus}
                      dest={destCampus}
                      mode={mode}
                      rain={rain}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      <div className="map-wrapper">
        <MapContainer center={[4.62, -74.08]} zoom={12} className="map-container">
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution="© OpenStreetMap © CARTO"
          />

          {/* Facultades: punto sin icono de pin (paraderos quedan ocultos) */}
          {facultyCampuses.map((c) => (
            <FacultyDot
              key={c.id}
              campus={c}
              isOrigin={+origin === c.id}
              isDest={+dest === c.id}
            />
          ))}


          {/* Rutas alternativas (no seleccionadas) en líneas punteadas */}
          {allRoutes.map((alt, i) =>
            i !== selAlt && alt.geometry?.length > 1 ? (
              <Polyline
                key={`alt-${i}`}
                positions={alt.geometry}
                pathOptions={{ color: ALT_COLORS[i], weight: 4, opacity: 0.3, dashArray: "8 6" }}
                eventHandlers={{ click: () => setSelAlt(i) }}
              />
            ) : null
          )}

          {/* Ruta activa: cada segmento con su color del modo (estilo Moovit) */}
          {routeCoords.length > 1 && (
            <>
              {/* Halo negro de fondo, le da contraste a los colores */}
              <Polyline
                positions={routeCoords}
                pathOptions={{ color: "#000", weight: 12, opacity: 0.25 }}
              />

              {/* Un Polyline por cada segmento, con su color del modo */}
              {routeSegments.length > 0 ? (
                <>
                  {routeSegments.map((seg, i) =>
                    seg.geometry?.length > 1 ? (
                      <Polyline
                        key={`seg-${i}`}
                        positions={seg.geometry}
                        pathOptions={{
                          color: seg.color || ALT_COLORS[selAlt],
                          weight: 6,
                          opacity: 0.9,
                          lineCap: "round",
                          lineJoin: "round",
                        }}
                      >
                        <Popup>
                          <strong>{seg.icon} {seg.mode}</strong>
                          <br />
                          {seg.instruction}
                          <br />
                          <small>
                            {seg.duration_min} min · {(seg.distance_km * 1000).toFixed(0)}m
                          </small>
                        </Popup>
                      </Polyline>
                    ) : null
                  )}

                  {/* Marcadores de paradas en cada segmento de transporte (no WALK).
                      Dibujamos un círculo blanco con borde del color del modo, estilo Moovit. */}
                  {routeSegments.map((seg, i) => {
                    const isTransport = !["WALK", ""].includes(seg.mode?.toUpperCase?.());
                    if (!isTransport || !seg.geometry || seg.geometry.length < 2) return null;
                    const startPoint = seg.geometry[0];
                    const endPoint = seg.geometry[seg.geometry.length - 1];
                    const color = seg.color || ALT_COLORS[selAlt];
                    return (
                      <>
                        <CircleMarker
                          key={`stop-start-${i}`}
                          center={startPoint}
                          radius={7}
                          pathOptions={{
                            color: color,
                            fillColor: "#ffffff",
                            fillOpacity: 1,
                            weight: 3,
                          }}
                        >
                          <Popup>
                            <strong>🚏 Sube aquí</strong>
                            <br />
                            {seg.from_name}
                            <br />
                            <small style={{ color: color }}>{seg.mode}</small>
                          </Popup>
                        </CircleMarker>
                        <CircleMarker
                          key={`stop-end-${i}`}
                          center={endPoint}
                          radius={7}
                          pathOptions={{
                            color: color,
                            fillColor: "#ffffff",
                            fillOpacity: 1,
                            weight: 3,
                          }}
                        >
                          <Popup>
                            <strong>🚏 Bájate aquí</strong>
                            <br />
                            {seg.to_name}
                            <br />
                            <small style={{ color: color }}>{seg.mode}</small>
                          </Popup>
                        </CircleMarker>
                      </>
                    );
                  })}
                </>
              ) : (
                /* Fallback: si por alguna razón no vienen segmentos,
                   dibuja la línea única como antes */
                <Polyline
                  positions={routeCoords}
                  pathOptions={{ color: ALT_COLORS[selAlt], weight: 6, opacity: 0.85 }}
                />
              )}

              <FitRoute coords={routeCoords} />
            </>
          )}
        </MapContainer>

        <div style={{
          position: "absolute", bottom: 16, right: 16, zIndex: 1000,
          background: "rgba(18,24,32,0.92)", border: "1px solid var(--border)",
          borderRadius: 8, padding: "0.6rem 0.8rem", fontSize: "0.68rem", color: "var(--text-muted)",
        }}>
          <div style={{ color: "var(--text)", fontWeight: 700, marginBottom: 4 }}>Leyenda</div>
          <div>● Facultad · <span style={{ color: "#3b82f6" }}>●</span> Origen · <span style={{ color: "#22c55e" }}>●</span> Destino</div>
          <div style={{ color: "#e11d48" }}>━ Ruta TransMilenio (GTFS)</div>
          <div>TM = bus simulado (5 hormigas/ruta)</div>
        </div>
      </div>
    </div>
  );
}

// ───── Botón compartir por WhatsApp ─────

function ShareRouteButton({ route, origin, dest, mode, rain }) {
  if (!origin || !dest || !route) return null;

  const handleShare = () => {
    // Armar URL con parámetros
    const params = new URLSearchParams();
    params.set("o", origin.id);
    params.set("d", dest.id);
    params.set("m", mode);
    if (rain) params.set("r", "1");
    const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;

    // Iconos por modo
    const modeIcons = {
      transit: "🚌",
      driving: "🚗",
      cycling: "🚲",
      walking: "🚶",
    };
    const modeLabels = {
      transit: "TransMilenio",
      driving: "Carro",
      cycling: "Bici",
      walking: "A pie",
    };

    // Armar mensaje pre-formateado
    const message = [
      "🗺️ *Te comparto mi ruta UMOS:*",
      "",
      `📍 ${origin.name} → ${dest.name}`,
      `${modeIcons[mode] || "🚌"} ${modeLabels[mode] || mode} · ~${Math.round(route.total_time)} min · $${route.total_cost_cop?.toLocaleString("es-CO") || 0} COP`,
      `📊 ${route.transfers || 0} ${route.transfers === 1 ? "transbordo" : "transbordos"} · ${route.total_distance?.toFixed(1) || 0} km`,
      "",
      `Mira los detalles aquí: ${url}`,
    ].join("\n");

    const waUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(waUrl, "_blank");
  };

  const handleCopyLink = async () => {
    const params = new URLSearchParams();
    params.set("o", origin.id);
    params.set("d", dest.id);
    params.set("m", mode);
    if (rain) params.set("r", "1");
    const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
    try {
      await navigator.clipboard.writeText(url);
      alert("Link copiado al portapapeles ✅");
    } catch {
      // Fallback si clipboard no funciona (HTTP en algunos navegadores)
      prompt("Copia este link:", url);
    }
  };

  return (
    <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.25rem" }}>
      <button
        type="button"
        onClick={handleShare}
        style={{
          flex: 1,
          background: "#25d366",
          border: "none",
          borderRadius: 8,
          padding: "0.55rem 0.75rem",
          color: "#fff",
          fontWeight: 700,
          fontSize: "0.78rem",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "0.4rem",
          transition: "filter 0.2s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(1.1)")}
        onMouseLeave={(e) => (e.currentTarget.style.filter = "brightness(1)")}
        title="Abrir WhatsApp con el mensaje pre-armado"
      >
        <span>💬</span>
        <span>Compartir por WhatsApp</span>
      </button>
      <button
        type="button"
        onClick={handleCopyLink}
        style={{
          background: "var(--surface-2)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: "0.55rem 0.75rem",
          color: "var(--text)",
          fontSize: "0.78rem",
          cursor: "pointer",
        }}
        title="Copiar link al portapapeles"
      >
        🔗
      </button>
    </div>
  );
}