import { useState, useEffect, useCallback } from "react";
import {
  MapContainer, TileLayer, Marker, Popup,
  Polyline, CircleMarker, useMap,
} from "react-leaflet";
import L from "leaflet";
import { getCampuses, optimizeRoute, getWeather } from "../services/api";

/* ── Fix icono default de Leaflet con Vite ─────────────────────────── */
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const TRANSPORT_ICONS = {
  WALK: "🚶", BIKE: "🚲", SITP: "🚌", TM: "🚇", CABLE: "🚡",
};

const MODE_OPTIONS = [
  { value: "fastest",  icon: "⚡", label: "Rápido"  },
  { value: "shortest", icon: "📍", label: "Corto"   },
  { value: "eco",      icon: "🌿", label: "Eco"     },
];

/* ── Componente que ajusta el mapa a la ruta ───────────────────────── */
function FlyToRoute({ positions }) {
  const map = useMap();
  useEffect(() => {
    if (positions && positions.length > 1) {
      map.flyToBounds(positions, { padding: [60, 60], duration: 1.2 });
    }
  }, [positions, map]);
  return null;
}

/* ── Icono personalizado para origen y destino ─────────────────────── */
function makeIcon(color, letter) {
  return L.divIcon({
    className: "",
    html: `<div style="
      background:${color};border:2px solid white;
      width:28px;height:28px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:13px;font-weight:700;color:white;
      box-shadow:0 2px 8px rgba(0,0,0,0.5);
      font-family:Inter,sans-serif;
    ">${letter}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

const ORIGIN_ICON = makeIcon("#2f81f7", "A");
const DEST_ICON   = makeIcon("#3fb950", "B");
const NODE_ICON   = makeIcon("#484f58", "·");

/* ════════════════════════════════════════════════════════════════════ */
export default function MapPage() {
  const [campuses, setCampuses] = useState([]);
  const [weather,  setWeather]  = useState(null);
  const [origin,   setOrigin]   = useState("");
  const [dest,     setDest]     = useState("");
  const [mode,     setMode]     = useState("fastest");
  const [rain,     setRain]     = useState(false);
  const [result,   setResult]   = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");

  /* Cargar campus y clima al montar */
  useEffect(() => {
    getCampuses()
      .then(setCampuses)
      .catch(() => setError("No se pudo conectar al backend. Verifica que esté corriendo en localhost:8000"));
    getWeather()
      .then(setWeather)
      .catch(() => {});
  }, []);

  /* Optimizar ruta */
  const handleOptimize = useCallback(async () => {
    if (!origin || !dest) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await optimizeRoute(Number(origin), Number(dest), mode, rain);
      setResult(data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        "Error al calcular la ruta. Verifica que el backend esté activo."
      );
    } finally {
      setLoading(false);
    }
  }, [origin, dest, mode, rain]);

  /* Limpiar resultado */
  const handleClear = () => {
    setResult(null);
    setError("");
    setOrigin("");
    setDest("");
  };

  /* Posiciones para la polilínea */
  const routePositions = result
    ? result.steps.map((s) => [s.latitude, s.longitude])
    : null;

  /* Campus de origen y destino para íconos especiales */
  const originCampus = campuses.find((c) => c.id === Number(origin));
  const destCampus   = campuses.find((c) => c.id === Number(dest));

  return (
    <div className="layout">
      {/* ════════ PANEL LATERAL ════════ */}
      <aside className="panel">
        {/* Header */}
        <div className="panel-header">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="15" fill="#0d2340" stroke="#2f81f7" strokeWidth="1.5"/>
            <path d="M9 23 L16 9 L23 23" stroke="#2f81f7" strokeWidth="2" strokeLinejoin="round"/>
            <path d="M11.5 18.5 H20.5" stroke="#2f81f7" strokeWidth="1.5"/>
            <circle cx="16" cy="9" r="2" fill="#2f81f7"/>
          </svg>
          <div>
            <div className="panel-logo-text">UMOS</div>
            <div className="panel-logo-sub">Universidad Distrital F.J.C.</div>
          </div>
        </div>

        <div className="panel-body">
          {/* Clima */}
          {weather && (
            <div className={`weather-strip ${weather.is_raining ? "raining" : ""}`}>
              <span>{weather.is_raining ? "🌧" : "🌤"}</span>
              <span>
                {weather.is_raining
                  ? `Lluvia activa: ${weather.rain_mm} mm/h`
                  : `Bogotá · ${weather.temp ?? "--"}°C · ${weather.description}`}
              </span>
            </div>
          )}

          {/* Selección de origen */}
          <div>
            <div className="section-label">Punto de Origen</div>
            <div className="campus-select-wrapper">
              <select
                value={origin}
                onChange={(e) => { setOrigin(e.target.value); setResult(null); }}
              >
                <option value="">— Selecciona sede de origen —</option>
                {campuses.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Selección de destino */}
          <div>
            <div className="section-label">Punto de Destino</div>
            <div className="campus-select-wrapper">
              <select
                value={dest}
                onChange={(e) => { setDest(e.target.value); setResult(null); }}
              >
                <option value="">— Selecciona sede de destino —</option>
                {campuses
                  .filter((c) => c.id !== Number(origin))
                  .map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
              </select>
            </div>
          </div>

          {/* Modo */}
          <div>
            <div className="section-label">Optimizar por</div>
            <div className="mode-grid">
              {MODE_OPTIONS.map((m) => (
                <button
                  key={m.value}
                  className={`mode-btn ${mode === m.value ? "active" : ""}`}
                  onClick={() => setMode(m.value)}
                  type="button"
                >
                  <span className="mode-btn-icon">{m.icon}</span>
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Toggle lluvia */}
          <div
            className="toggle-row"
            onClick={() => setRain((r) => !r)}
            style={{ cursor: "pointer" }}
          >
            <span className="toggle-label">🌧 Simular condición de lluvia</span>
            <div className={`toggle ${rain ? "on" : ""}`} />
          </div>

          {/* Error */}
          {error && <div className="error-box">⚠ {error}</div>}

          {/* Botón optimizar */}
          <button
            className="btn-optimize"
            onClick={handleOptimize}
            disabled={loading || !origin || !dest}
          >
            {loading ? (
              <><span className="spinner" /> Calculando ruta...</>
            ) : (
              <>🐜 Optimizar Ruta con ACO</>
            )}
          </button>

          {/* Resultado */}
          {result && (
            <>
              <div className="divider" />
              <div className="result-box">
                {/* Cabecera resultado */}
                <div className="result-header">
                  <span className="result-title">
                    {result.origin} → {result.destination}
                  </span>
                  <span className="result-aco">
                    🐜 {result.aco_iterations} iter.
                  </span>
                </div>

                {/* Stats */}
                <div className="result-stats">
                  <div className="stat-cell">
                    <div className="stat-val">{result.total_time} min</div>
                    <div className="stat-lbl">⏱ Tiempo total</div>
                  </div>
                  <div className="stat-cell">
                    <div className="stat-val">{result.total_distance} km</div>
                    <div className="stat-lbl">📏 Distancia</div>
                  </div>
                  <div className="stat-cell" style={{ borderTop: "1px solid var(--border)" }}>
                    <div className="stat-val" style={{ fontSize: "0.85rem" }}>
                      {result.transport_modes.map((t) => TRANSPORT_ICONS[t] || t).join(" ")}
                    </div>
                    <div className="stat-lbl">🚌 Medios</div>
                  </div>
                  <div className="stat-cell" style={{ borderTop: "1px solid var(--border)" }}>
                    <div className="stat-val" style={{ color: result.rain_penalty_applied ? "#58a6ff" : "var(--success)" }}>
                      {result.rain_penalty_applied ? "Lluvia ⚠" : "Normal ✓"}
                    </div>
                    <div className="stat-lbl">🌤 Condición</div>
                  </div>
                </div>

                {result.rain_penalty_applied && (
                  <div className="rain-applied">
                    🌧 Penalización por lluvia aplicada (+63.2% al tiempo)
                  </div>
                )}

                {/* Pasos */}
                <div className="steps">
                  <div className="section-label" style={{ marginBottom: "0.6rem" }}>
                    Secuencia de la ruta
                  </div>
                  {result.steps.map((step, i) => {
                    const isLast = i === result.steps.length - 1;
                    return (
                      <div className="step-row" key={i}>
                        <div className="step-track">
                          <div className={`step-dot ${isLast ? "end" : ""}`} />
                          {!isLast && <div className="step-line" />}
                        </div>
                        <div className="step-info">
                          <div className="step-name">
                            {step.campus_name}
                            {step.transport && (
                              <span className="chip">
                                {TRANSPORT_ICONS[step.transport]} {step.transport}
                              </span>
                            )}
                          </div>
                          {i > 0 && (
                            <div className="step-meta">
                              {step.cumulative_time} min · {step.cumulative_distance} km
                            </div>
                          )}
                          {i === 0 && (
                            <div className="step-meta" style={{ color: "var(--primary)" }}>
                              Punto de partida
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Botón limpiar */}
              <button className="btn-clear" onClick={handleClear}>
                ✕ Limpiar ruta
              </button>
            </>
          )}
        </div>
      </aside>

      {/* ════════ MAPA ════════ */}
      <div className="map-wrapper">
        {!origin && !dest && (
          <div className="map-hint">
            Selecciona origen y destino para optimizar la ruta
          </div>
        )}

        <MapContainer
          center={[4.620, -74.090]}
          zoom={12}
          className="map-container"
          zoomControl={true}
        >
          {/* Tiles oscuros de CartoDB */}
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://openstreetmap.org" target="_blank">OSM</a> &copy; CARTO'
            maxZoom={19}
          />

          {/* Todos los campus como puntos pequeños */}
          {campuses.map((c) => {
            const isOrigin = c.id === Number(origin);
            const isDest   = c.id === Number(dest);
            if (isOrigin || isDest) return null; // los pintamos aparte
            return (
              <CircleMarker
                key={c.id}
                center={[c.latitude, c.longitude]}
                radius={6}
                pathOptions={{
                  fillColor: "#2f81f7",
                  fillOpacity: 0.7,
                  color: "#fff",
                  weight: 1.5,
                }}
              >
                <Popup>
                  <strong style={{ color: "#000" }}>{c.name}</strong>
                  <br />
                  <small>{c.address}</small>
                </Popup>
              </CircleMarker>
            );
          })}

          {/* Marcador de origen */}
          {originCampus && (
            <Marker
              position={[originCampus.latitude, originCampus.longitude]}
              icon={ORIGIN_ICON}
            >
              <Popup>
                <strong>🔵 Origen</strong><br />{originCampus.name}
              </Popup>
            </Marker>
          )}

          {/* Marcador de destino */}
          {destCampus && (
            <Marker
              position={[destCampus.latitude, destCampus.longitude]}
              icon={DEST_ICON}
            >
              <Popup>
                <strong>🟢 Destino</strong><br />{destCampus.name}
              </Popup>
            </Marker>
          )}

          {/* Ruta optimizada */}
          {routePositions && routePositions.length > 1 && (
            <>
              {/* Sombra de la ruta */}
              <Polyline
                positions={routePositions}
                pathOptions={{
                  color: "#000",
                  weight: 9,
                  opacity: 0.3,
                }}
              />
              {/* Línea principal */}
              <Polyline
                positions={routePositions}
                pathOptions={{
                  color: "#2f81f7",
                  weight: 5,
                  opacity: 1,
                  dashArray: "12 6",
                  lineCap: "round",
                  lineJoin: "round",
                }}
              />
              <FlyToRoute positions={routePositions} />
            </>
          )}
        </MapContainer>
      </div>
    </div>
  );
}
