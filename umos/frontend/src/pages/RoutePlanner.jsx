import { useState, useEffect } from "react";
import { MapContainer, TileLayer, Polyline, Circle, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import AppNav from "../components/AppNav.jsx";
import RouteCard from "../components/RouteCard.jsx";
import DataFreshnessBadge from "../components/DataFreshnessBadge.jsx";
import { FacultyDot, AntMarkers, animateAnts } from "../components/TransitSimulation.jsx";
import {
  getCampuses, getWeather, optimizeRoute, getTransmilenioRecommendations,
  getDataFreshness,
} from "../services/api.js";

const MODES = [
  { id: "transit", icon: "🚌", label: "TransMilenio", color: "#e11d48" },
  { id: "driving", icon: "🚗", label: "Carro", color: "#14b8a6" },
  { id: "cycling", icon: "🚲", label: "Bici", color: "#22c55e" },
  { id: "walking", icon: "🚶", label: "A pie", color: "#f59e0b" },
];

const ALT_COLORS = ["#3b82f6", "#e3b341", "#f85149"];

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
  const [mode, setMode] = useState("transit");
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
    getCampuses().then(setCampuses).catch(() => setError("Backend no disponible en localhost:8000"));
    getWeather().then(setWeather).catch(() => {});
    getDataFreshness().then(setFreshness).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 800);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (mode !== "transit" || !origin || !dest || origin === dest || !campuses.length) {
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const allRoutes = route ? [route.selected, ...(route.alternatives || [])] : [];
  const activeRoute = allRoutes[selAlt];
  const routeCoords = activeRoute?.geometry || [];
  const tmRoutes = transit?.recommended_routes || transit?.routes || [];
  const antVehicles = animateAnts(tmRoutes, tick);

  const originCampus = campuses.find((c) => c.id === +origin);
  const destCampus = campuses.find((c) => c.id === +dest);

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
                  {campuses.map((c) => (
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

          {transit?.summary && mode === "transit" && (
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

          {tmRoutes.length > 0 && mode === "transit" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
              <div className="section-label">Rutas TM — ¿en cuál subir? (5 hormigas/ruta)</div>
              {tmRoutes.map((r) => (
                <button
                  key={r.route_id}
                  type="button"
                  onClick={() => setSelTmRoute(r.route_id)}
                  style={{
                    background: selTmRoute === r.route_id ? "#2a0f14" : "var(--surface-2)",
                    border: `2px solid ${selTmRoute === r.route_id ? "#e11d48" : "var(--border)"}`,
                    borderRadius: 8,
                    padding: "0.65rem",
                    textAlign: "left",
                    color: "var(--text)",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong style={{ color: "#e11d48" }}>Ruta {r.short_name}</strong>
                    <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                      ACO {r.aco_score}
                    </span>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{r.long_name}</div>
                  <div style={{ fontSize: "0.72rem", marginTop: 4 }}>
                    Sube: {r.board_at} → Baja: {r.alight_at}
                  </div>
                </button>
              ))}
            </div>
          )}

          {error && <div className="error-box">{error}</div>}

          {allRoutes.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div className="section-label">Ruta ACO ({route.computation_time_ms?.toFixed(0)} ms)</div>
              {allRoutes.map((r, i) => (
                <RouteCard key={i} route={r} selected={selAlt === i} onSelect={() => setSelAlt(i)} index={i} />
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

          {/* Facultades: punto sin icono de pin */}
          {campuses.map((c) => (
            <FacultyDot
              key={c.id}
              campus={c}
              isOrigin={+origin === c.id}
              isDest={+dest === c.id}
            />
          ))}

          {/* Estaciones GTFS cercanas (círculos, sin pin) */}
          {mode === "transit" && transit?.origin_nearby_stations?.map((s) => (
            <Circle
              key={`os-${s.id}`}
              center={[s.lat, s.lon]}
              radius={40}
              pathOptions={{ color: "#e11d48", fillColor: "#e11d48", fillOpacity: 0.35, weight: 1 }}
            >
              <Popup><strong>{s.name}</strong><br />{s.distance_m} m del origen</Popup>
            </Circle>
          ))}

          {/* Trazados GTFS TransMilenio */}
          {mode === "transit" && tmRoutes.map((r) => (
            r.geometry?.length > 1 && (
              <Polyline
                key={`tm-${r.route_id}`}
                positions={r.geometry}
                pathOptions={{
                  color: r.color || "#e11d48",
                  weight: selTmRoute === r.route_id ? 5 : 3,
                  opacity: selTmRoute === r.route_id ? 0.9 : 0.4,
                  lineCap: "round",
                }}
              />
            )
          ))}

          {/* 5 hormigas por ruta TM */}
          {mode === "transit" && <AntMarkers vehicles={antVehicles} />}

          {/* Ruta ACO caminata/conexión */}
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
          {routeCoords.length > 1 && (
            <>
              <Polyline positions={routeCoords} pathOptions={{ color: "#000", weight: 12, opacity: 0.2 }} />
              <Polyline positions={routeCoords} pathOptions={{ color: ALT_COLORS[selAlt], weight: 6, opacity: 0.85 }} />
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
