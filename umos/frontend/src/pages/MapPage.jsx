import { useState, useEffect } from "react";
import {
  MapContainer, TileLayer, Marker, Popup,
  Polyline, Circle, useMap
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  getCampuses, getWeather, getTrafficEvents,
  createTrafficEvent, resolveTrafficEvent, optimizeRoute, simulateTraffic,
  getTransmilenioRecommendations
} from "../services/api.js?v=tm";

// ── Fix iconos Leaflet con Vite ──────────────────────────────────────────────
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// ── Constantes ───────────────────────────────────────────────────────────────
const TRANSPORT_MODES = [
  { id: "driving", icon: "🚗", label: "Carro",              color: "#4f98a3" },
  { id: "transit", icon: "🚌", label: "Transporte público", color: "#e3b341" },
  { id: "cycling", icon: "🚲", label: "Bicicleta",          color: "#6daa45" },
  { id: "walking", icon: "🚶", label: "A pie",              color: "#a86fdf" },
];

const ALT_COLORS  = ["#4f98a3", "#e3b341", "#f85149"];
const SEV_COLOR   = { LOW: "#e3b341", MEDIUM: "#ff7b00", HIGH: "#f85149", CRITICAL: "#8b0000" };
const EV_ICON     = { PROTEST: "📢", ACCIDENT: "🚨", MINOR_CRASH: "💥", ROAD_CLOSED: "🚧", CONGESTION: "🚗", RAIN: "🌧" };

// ── Helpers ──────────────────────────────────────────────────────────────────
function FitRoute({ coords }) {
  const map = useMap();
  useEffect(() => {
    if (coords?.length > 1) map.fitBounds(coords, { padding: [60, 60], animate: true });
  }, [coords]);
  return null;
}

const mkIcon = (label, bg) =>
  L.divIcon({
    className: "",
    iconAnchor: [16, 16],
    html: `<div style="
      background:${bg};color:#fff;font-weight:800;
      width:32px;height:32px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      border:3px solid #fff;box-shadow:0 2px 10px #0009;font-size:13px
    ">${label}</div>`,
  });

const tmStationIcon = L.divIcon({
  className: "",
  iconAnchor: [8, 8],
  html: `<div style="
    width:16px;height:16px;border-radius:50%;background:#e11d48;
    border:3px solid #fff;box-shadow:0 1px 8px #0008
  "></div>`,
});

const tmBusIcon = (label) => L.divIcon({
  className: "",
  iconAnchor: [13, 13],
  html: `<div style="
    width:26px;height:26px;border-radius:50%;background:#ef4444;color:#fff;
    display:flex;align-items:center;justify-content:center;font-size:10px;
    font-weight:800;border:2px solid #fff;box-shadow:0 2px 10px #000a
  " title="${label}">TM</div>`,
});

function pointAlong(points, progress) {
  if (!points?.length) return null;
  const index = Math.min(Math.floor(progress * (points.length - 1)), points.length - 1);
  return points[index];
}

// ── Estilos base (sin archivo CSS externo) ───────────────────────────────────
const G = {
  wrap:    { display:"flex", height:"100dvh", background:"#0f1117",
             width:"100%", minWidth:0,
             color:"#e2e4f0", fontFamily:"Inter,system-ui,sans-serif", overflow:"hidden" },
  side:    { width:320, minWidth:320, background:"#1a1d27",
             borderRight:"1px solid #2e3248", display:"flex",
             flexDirection:"column", height:"100dvh", overflowY:"auto" },
  head:    { padding:"1rem 1rem 0.5rem", borderBottom:"1px solid #2e3248",
             display:"flex", flexDirection:"column", gap:"0.5rem" },
  logo:    { display:"flex", alignItems:"center", gap:"0.6rem",
             fontWeight:700, fontSize:"1.05rem" },
  tabs:    { display:"flex", borderBottom:"1px solid #2e3248" },
  tab:     (a) => ({ flex:1, padding:"0.6rem", background:"none", border:"none",
                     cursor:"pointer", fontSize:"0.8rem", fontWeight:600,
                     color: a ? "#4f98a3" : "#7b809a",
                     borderBottom: a ? "2px solid #4f98a3" : "2px solid transparent" }),
  body:    { flex:1, padding:"0.9rem", display:"flex", flexDirection:"column", gap:"0.75rem" },
  lbl:     { fontSize:"0.7rem", color:"#7b809a", textTransform:"uppercase",
             letterSpacing:"0.05em", marginBottom:"0.2rem", display:"block" },
  inp:     { background:"#22263a", border:"1px solid #2e3248", color:"#e2e4f0",
             padding:"0.5rem 0.7rem", borderRadius:8, fontSize:"0.87rem",
             outline:"none", width:"100%" },
  btn:     (bg, dis) => ({ background: dis ? "#2a2d3a" : bg, color:"#fff",
                           border:"none", padding:"0.65rem", borderRadius:8,
                           fontWeight:700, cursor: dis ? "not-allowed" : "pointer",
                           fontSize:"0.88rem", width:"100%", opacity: dis ? 0.5 : 1,
                           transition:"background 0.15s" }),
  card:    { background:"#22263a", border:"1px solid #2e3248",
             borderRadius:10, padding:"0.85rem",
             display:"flex", flexDirection:"column", gap:"0.6rem" },
  stat:    { background:"#1a1d27", borderRadius:6, padding:"0.45rem 0.6rem" },
  badge:   (bg, c) => ({ display:"inline-block", padding:"0.2rem 0.55rem",
                          borderRadius:20, fontSize:"0.72rem",
                          fontWeight:600, background:bg, color:c||"#fff" }),
  divider: { height:"1px", background:"#2e3248", margin:"0.1rem 0" },
  err:     { background:"#2a0f0f", color:"#f85149", padding:"0.6rem 0.8rem",
             borderRadius:8, fontSize:"0.82rem" },
  mapWrap: { flex:"1 1 auto", minWidth:0, position:"relative", height:"100dvh" },
};

// ── Componente principal ─────────────────────────────────────────────────────
export default function MapPage() {
  const [campuses, setCampuses] = useState([]);
  const [origin,   setOrigin]   = useState("");
  const [dest,     setDest]     = useState("");
  const [mode,     setMode]     = useState("driving");
  const [rain,     setRain]     = useState(false);
  const [route,    setRoute]    = useState(null);
  const [selAlt,   setSelAlt]   = useState(0);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [weather,  setWeather]  = useState(null);
  const [events,   setEvents]   = useState([]);
  const [transit,  setTransit]  = useState(null);
  const [tmTick,   setTmTick]   = useState(0);
  const [tab,      setTab]      = useState("route");
  const [showForm, setShowForm] = useState(false);
  const [newEv,    setNewEv]    = useState({
    event_type:"ACCIDENT", severity:"MEDIUM",
    latitude:"", longitude:"", radius_m:500, description:""
  });

  const refreshEvents = () =>
    getTrafficEvents().then(setEvents).catch(() => {});

  useEffect(() => {
    getCampuses()
      .then(setCampuses)
      .catch(() => setError("No se pudo conectar al backend. Verifica que esté corriendo en localhost:8000"));
    getWeather().then(setWeather).catch(() => {});
    refreshEvents();
  }, []);

  useEffect(() => {
    if (mode !== "transit" || !origin || !dest || origin === dest || campuses.length === 0) {
      setTransit(null);
      return;
    }
    const originCampus = campuses.find(c => c.id === +origin);
    const destCampus = campuses.find(c => c.id === +dest);
    if (!originCampus || !destCampus) return;
    getTransmilenioRecommendations(originCampus, destCampus)
      .then(setTransit)
      .catch(() => setTransit(null));
  }, [mode, origin, dest, campuses]);

  useEffect(() => {
    const timer = setInterval(() => setTmTick(t => t + 1), 1400);
    return () => clearInterval(timer);
  }, []);

  async function handleOptimize(e) {
    e.preventDefault();
    if (!origin || !dest || origin === dest) return;
    setLoading(true); setError(null); setRoute(null); setSelAlt(0);
    try {
      const data = await optimizeRoute(+origin, +dest, mode, rain);
      setRoute(data);
      refreshEvents();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al calcular la ruta. Revisa la consola.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateEv(e) {
    e.preventDefault();
    try {
      await createTrafficEvent({
        ...newEv,
        latitude:  +newEv.latitude,
        longitude: +newEv.longitude,
        radius_m:  +newEv.radius_m,
      });
      refreshEvents();
      setShowForm(false);
      setNewEv({ event_type:"ACCIDENT", severity:"MEDIUM", latitude:"", longitude:"", radius_m:500, description:"" });
    } catch (err) {
      alert("Error: " + (err.response?.data?.detail || err.message));
    }
  }

  async function handleSimulation(scenario) {
    try {
      await simulateTraffic(scenario);
      refreshEvents();
      if (scenario === "rain") setRain(true);
      setTab("traffic");
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo ejecutar la simulacion.");
    }
  }

  const allRoutes    = route ? [route.selected, ...(route.alternatives || [])] : [];
  const activeRoute  = allRoutes[selAlt] || null;
  const routeCoords  = activeRoute?.geometry || [];
  const tmVehicleMarkers = (transit?.routes || []).flatMap((tmRoute, routeIndex) => {
    if (!tmRoute.geometry?.length) return [];
    return [0, 1].map(vehicleIndex => {
      const progress = ((tmTick * 0.035) + routeIndex * 0.17 + vehicleIndex * 0.5) % 1;
      const point = pointAlong(tmRoute.geometry, progress);
      return point ? {
        id: `${tmRoute.id}-${vehicleIndex}`,
        label: `${tmRoute.name} #${vehicleIndex + 1}`,
        position: point,
      } : null;
    }).filter(Boolean);
  });

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div style={G.wrap}>

      {/* ══════════════ SIDEBAR ══════════════ */}
      <aside style={G.side}>

        {/* Logo + clima */}
        <div style={G.head}>
          <div style={G.logo}>
            <svg width="26" height="26" viewBox="0 0 28 28" fill="none">
              <circle cx="14" cy="14" r="13" stroke="#4f98a3" strokeWidth="2"/>
              <path d="M8 20L14 8L20 20" stroke="#4f98a3" strokeWidth="2" strokeLinejoin="round"/>
              <path d="M10 16H18" stroke="#4f98a3" strokeWidth="1.5"/>
            </svg>
            UMOS <span style={{color:"#4f98a3", fontSize:"0.7rem", marginLeft:4}}>v3</span>
          </div>
          {weather && (
            <div style={G.badge(
              weather.is_raining ? "#1a3a5e" : "#1a3a2e",
              weather.is_raining ? "#7ac0ff" : "#6daa45"
            )}>
              {weather.is_raining
                ? `🌧 Lluvia: ${weather.rain_mm} mm/h`
                : `☀️ ${weather.description || "Sin lluvia"} · ${weather.temp}°C`}
            </div>
          )}
        </div>

        {/* Tabs */}
        <div style={G.tabs}>
          {[["route","🗺 Ruta"], ["traffic","⚠️ Tráfico"]].map(([k, l]) => (
            <button key={k} style={G.tab(tab === k)} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>

        <div style={G.body}>

          {/* ─── TAB: RUTA ─── */}
          {tab === "route" && <>

            {/* Selector modo de transporte */}
            <div>
              <label style={G.lbl}>Medio de transporte</label>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.4rem" }}>
                {TRANSPORT_MODES.map(m => (
                  <button key={m.id} onClick={() => setMode(m.id)} style={{
                    background:  mode === m.id ? m.color + "22" : "#22263a",
                    border:      `2px solid ${mode === m.id ? m.color : "#2e3248"}`,
                    borderRadius: 8,
                    padding:     "0.5rem 0.3rem",
                    color:       mode === m.id ? m.color : "#7b809a",
                    cursor:      "pointer",
                    fontSize:    "0.82rem",
                    fontWeight:  600,
                    display:     "flex",
                    flexDirection: "column",
                    alignItems:  "center",
                    gap:          2,
                    transition:  "all 0.15s",
                  }}>
                    <span style={{ fontSize:"1.2rem" }}>{m.icon}</span>
                    <span style={{ fontSize:"0.68rem" }}>{m.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Formulario origen / destino */}
            <form onSubmit={handleOptimize}
              style={{ display:"flex", flexDirection:"column", gap:"0.65rem" }}>
              {[["Origen 📍", origin, setOrigin], ["Destino 🎯", dest, setDest]].map(([lbl, val, set]) => (
                <div key={lbl}>
                  <label style={G.lbl}>{lbl}</label>
                  <select value={val} onChange={e => set(e.target.value)}
                    required style={G.inp}>
                    <option value="">Selecciona sede...</option>
                    {campuses.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              ))}

              <label style={{ display:"flex", gap:"0.5rem", alignItems:"center",
                              fontSize:"0.84rem", cursor:"pointer" }}>
                <input type="checkbox" checked={rain}
                  onChange={e => setRain(e.target.checked)} />
                Simular condición de lluvia
              </label>

              <button type="submit"
                disabled={loading || !origin || !dest || origin === dest}
                style={G.btn("#4f98a3", loading || !origin || !dest || origin === dest)}>
                {loading ? "⏳ Calculando ACO..." : "🐜 Buscar ruta óptima"}
              </button>
            </form>

            {mode === "transit" && transit && (
              <div style={G.card}>
                <div style={{ display:"flex", justifyContent:"space-between", gap:"0.5rem", alignItems:"center" }}>
                  <div style={{ fontWeight:700, color:"#e3b341", fontSize:"0.9rem" }}>
                    TransMilenio cercano
                  </div>
                  <span style={G.badge(transit.direct_match ? "#1a3a2e" : "#2a2d3a", transit.direct_match ? "#6daa45" : "#e3b341")}>
                    {transit.direct_match ? "Ruta directa" : "Con conexion"}
                  </span>
                </div>

                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.4rem" }}>
                  {[
                    ["Origen", transit.origin_station],
                    ["Destino", transit.destination_station],
                  ].map(([label, station]) => (
                    <div key={label} style={G.stat}>
                      <div style={{ fontSize:"0.67rem", color:"#7b809a" }}>{label}</div>
                      <div style={{ fontWeight:700, fontSize:"0.78rem" }}>
                        {station?.name || "Sin estacion cercana"}
                      </div>
                      {station && (
                        <div style={{ color:"#7b809a", fontSize:"0.7rem" }}>
                          {station.distance_m} m · {station.trunk}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {transit.routes?.length > 0 && (
                  <div>
                    <label style={G.lbl}>Servicios sugeridos</label>
                    {transit.routes.slice(0, 4).map(tmRoute => (
                      <div key={tmRoute.id} style={{
                        display:"flex", justifyContent:"space-between", gap:"0.6rem",
                        borderTop:"1px solid #2e3248", padding:"0.45rem 0",
                        fontSize:"0.76rem",
                      }}>
                        <strong style={{ color:"#f87171" }}>{tmRoute.name}</strong>
                        <span style={{ color:"#7b809a", textAlign:"right" }}>
                          {tmRoute.origin} → {tmRoute.destination}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {error && <div style={G.err}>⚠ {error}</div>}

            {/* Resultados */}
            {route && <>
              <div style={G.divider} />

              {/* Selector de alternativas */}
              {allRoutes.length > 1 && (
                <div style={{ display:"flex", flexDirection:"column", gap:"0.3rem" }}>
                  <label style={G.lbl}>Rutas encontradas</label>
                  {allRoutes.map((alt, i) => (
                    <button key={i} onClick={() => setSelAlt(i)} style={{
                      background:   selAlt === i ? ALT_COLORS[i] + "22" : "#22263a",
                      border:       `2px solid ${selAlt === i ? ALT_COLORS[i] : "#2e3248"}`,
                      borderRadius:  8,
                      padding:      "0.5rem 0.7rem",
                      color:        selAlt === i ? ALT_COLORS[i] : "#7b809a",
                      cursor:       "pointer",
                      textAlign:    "left",
                      fontSize:     "0.82rem",
                      display:      "flex",
                      justifyContent: "space-between",
                      transition:   "all 0.15s",
                    }}>
                      <span style={{ fontWeight:700 }}>{alt.label}</span>
                      <span>⏱ {alt.total_time} min · {alt.total_distance} km</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Detalle ruta activa */}
              {activeRoute && (
                <div style={G.card}>
                  <div style={{ fontWeight:700, color:ALT_COLORS[selAlt], fontSize:"0.92rem" }}>
                    {route.origin} → {route.destination}
                  </div>
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.4rem" }}>
                    {[
                      ["⏱ Tiempo",    `${activeRoute.total_time} min`],
                      ["📏 Distancia", `${activeRoute.total_distance} km`],
                      ["🚌 Medios",    activeRoute.transport_modes.join(", ") || "—"],
                      ["🐜 ACO",       `${route.aco_iterations} iter`],
                    ].map(([lbl, val]) => (
                      <div key={lbl} style={G.stat}>
                        <div style={{ fontSize:"0.67rem", color:"#7b809a" }}>{lbl}</div>
                        <div style={{ fontWeight:600, fontSize:"0.82rem", marginTop:2 }}>{val}</div>
                      </div>
                    ))}
                  </div>

                  {route.rain_penalty_applied && (
                    <div style={G.badge("#1a2e4a","#7ac0ff")}>⚠ Penalización lluvia +63%</div>
                  )}

                  {route.active_traffic_events?.length > 0 && (
                    <div style={{ background:"#2a1500", color:"#ff7b00",
                                  borderRadius:7, padding:"0.5rem 0.7rem", fontSize:"0.78rem" }}>
                      <strong>⚠ Eventos activos en la ruta:</strong>
                      {route.active_traffic_events.map((ev, i) => (
                        <div key={i}>
                          {EV_ICON[ev.event_type] || "⚠"} {ev.label} — {ev.severity} ×{ev.factor?.toFixed(1)}
                        </div>
                      ))}
                    </div>
                  )}

                  <label style={{ ...G.lbl, marginBottom:0 }}>Pasos de la ruta</label>
                  {activeRoute.steps.map((step, i) => (
                    <div key={i} style={{ display:"flex", gap:"0.5rem",
                                         alignItems:"flex-start", fontSize:"0.8rem" }}>
                      <div style={{
                        width:10, height:10, borderRadius:"50%", flexShrink:0, marginTop:4,
                        background: i === 0 ? "#4f98a3"
                          : i === activeRoute.steps.length - 1 ? "#6daa45" : "#555",
                      }}/>
                      <div>
                        <div style={{ fontWeight:600 }}>{step.campus_name}</div>
                        <div style={{ color:"#7b809a", fontSize:"0.73rem" }}>
                          {step.cumulative_time} min · {step.cumulative_distance} km
                          {step.transport && ` · ${step.transport}`}
                          {step.traffic_factor > 1.1 && (
                            <span style={{ color:"#ff7b00" }}> · ×{step.traffic_factor} tráfico</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>}
          </>}

          {/* ─── TAB: TRÁFICO ─── */}
          {tab === "traffic" && <>
            <div style={G.card}>
              <label style={G.lbl}>Simulaciones</label>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.4rem" }}>
                {[
                  ["peak", "Hora pico"],
                  ["rain", "Lluvia"],
                  ["incident", "Incidente"],
                  ["clear", "Limpiar"],
                ].map(([scenario, label]) => (
                  <button key={scenario}
                    onClick={() => handleSimulation(scenario)}
                    style={{
                      background:"#1a1d27",
                      border:"1px solid #2e3248",
                      color:"#e2e4f0",
                      borderRadius:8,
                      padding:"0.45rem 0.5rem",
                      fontSize:"0.78rem",
                      fontWeight:700,
                      cursor:"pointer",
                    }}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <button onClick={() => setShowForm(!showForm)}
              style={G.btn(showForm ? "#444" : "#c0392b", false)}>
              {showForm ? "✕ Cancelar" : "+ Reportar evento de tráfico"}
            </button>

            {showForm && (
              <form onSubmit={handleCreateEv} style={{ ...G.card, gap:"0.55rem" }}>
                {[
                  { lbl:"Tipo", key:"event_type", opts:{ PROTEST:"📢 Protesta", ACCIDENT:"🚨 Accidente", MINOR_CRASH:"💥 Choque leve", ROAD_CLOSED:"🚧 Vía cerrada", CONGESTION:"🚗 Congestión", RAIN:"🌧 Lluvia" }},
                  { lbl:"Severidad", key:"severity", opts:{ LOW:"🟡 Baja", MEDIUM:"🟠 Media", HIGH:"🔴 Alta", CRITICAL:"⛔ Crítica" }},
                ].map(f => (
                  <div key={f.key}>
                    <label style={G.lbl}>{f.lbl}</label>
                    <select value={newEv[f.key]}
                      onChange={e => setNewEv(p => ({ ...p, [f.key]: e.target.value }))}
                      style={G.inp}>
                      {Object.entries(f.opts).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </div>
                ))}
                {[
                  ["Latitud",     "latitude",    "4.6310"],
                  ["Longitud",    "longitude",   "-74.0660"],
                  ["Radio (m)",   "radius_m",    "500"],
                  ["Descripción", "description", "Ej: Trancón Av. NQS"],
                ].map(([lbl, key, ph]) => (
                  <div key={key}>
                    <label style={G.lbl}>{lbl}</label>
                    <input placeholder={ph} value={newEv[key]}
                      onChange={e => setNewEv(p => ({ ...p, [key]: e.target.value }))}
                      style={G.inp} />
                  </div>
                ))}
                <button type="submit" style={G.btn("#c0392b", false)}>
                  Reportar evento
                </button>
              </form>
            )}

            <label style={G.lbl}>Activos ({events.length})</label>

            {events.length === 0 ? (
              <div style={{ color:"#7b809a", fontSize:"0.85rem",
                            textAlign:"center", padding:"1.5rem 0" }}>
                ✅ Sin eventos activos en Bogotá
              </div>
            ) : events.map(ev => (
              <div key={ev.id} style={{
                ...G.card,
                border:`1px solid ${SEV_COLOR[ev.severity] || "#2e3248"}`
              }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
                  <span style={{ fontWeight:700, fontSize:"0.87rem" }}>
                    {EV_ICON[ev.event_type] || "⚠"} {ev.event_type.replace("_", " ")}
                  </span>
                  <span style={G.badge(SEV_COLOR[ev.severity])}>{ev.severity}</span>
                </div>
                {ev.description && (
                  <div style={{ color:"#7b809a", fontSize:"0.78rem" }}>{ev.description}</div>
                )}
                <div style={{ color:"#7b809a", fontSize:"0.72rem" }}>
                  📍 {ev.latitude?.toFixed(4)}, {ev.longitude?.toFixed(4)}
                  · r={ev.radius_m}m · ×{ev.delay_factor?.toFixed(1)}
                </div>
                <button
                  onClick={() => resolveTrafficEvent(ev.id).then(refreshEvents)}
                  style={{ background:"none", border:"1px solid #2e3248", color:"#6daa45",
                           borderRadius:6, padding:"0.28rem 0.6rem", cursor:"pointer",
                           fontSize:"0.74rem", alignSelf:"flex-start" }}>
                  ✓ Marcar como resuelto
                </button>
              </div>
            ))}
          </>}

        </div>
      </aside>

      {/* ══════════════ MAPA ══════════════ */}
      <div style={G.mapWrap}>
        <MapContainer
          center={[4.620, -74.080]}
          zoom={12}
          style={{ width:"100%", height:"100%" }}
          zoomControl={true}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution="© OpenStreetMap © CARTO"
          />

          {/* Marcadores de campus */}
          {campuses.map(c => (
            <Marker
              key={c.id}
              position={[c.latitude, c.longitude]}
              icon={
                +origin === c.id ? mkIcon("A", "#4f98a3") :
                +dest   === c.id ? mkIcon("B", "#6daa45") :
                new L.Icon.Default()
              }
            >
              <Popup>
                <strong>{c.name}</strong><br />
                <small style={{ color:"#666" }}>{c.address}</small>
              </Popup>
            </Marker>
          ))}

          {/* Rutas alternativas (detrás, semitransparentes) */}
          {allRoutes.map((alt, i) =>
            i !== selAlt && alt.geometry?.length > 1 ? (
              <Polyline
                key={`alt-bg-${i}`}
                positions={alt.geometry}
                pathOptions={{
                  color:     ALT_COLORS[i],
                  weight:    4,
                  opacity:   0.3,
                  dashArray: "8 6",
                  lineCap:   "round",
                  lineJoin:  "round",
                }}
                eventHandlers={{ click: () => setSelAlt(i) }}
              />
            ) : null
          )}

          {/* Ruta seleccionada — 3 capas tipo Google Maps */}
          {routeCoords.length > 1 && <>
            {/* Sombra */}
            <Polyline positions={routeCoords}
              pathOptions={{ color:"#000000", weight:14, opacity:0.3,
                             lineCap:"round", lineJoin:"round" }} />
            {/* Borde blanco */}
            <Polyline positions={routeCoords}
              pathOptions={{ color:"#ffffff", weight:9,  opacity:0.6,
                             lineCap:"round", lineJoin:"round" }} />
            {/* Línea de color principal */}
            <Polyline positions={routeCoords}
              pathOptions={{ color: ALT_COLORS[selAlt], weight:6, opacity:1.0,
                             lineCap:"round", lineJoin:"round" }} />

            {/* Punto origen */}
            <Circle center={routeCoords[0]} radius={35}
              pathOptions={{ color:"#fff", fillColor:"#4f98a3",
                             fillOpacity:1, weight:3 }} />
            {/* Punto destino */}
            <Circle center={routeCoords[routeCoords.length - 1]} radius={35}
              pathOptions={{ color:"#fff", fillColor:"#6daa45",
                             fillOpacity:1, weight:3 }} />

            <FitRoute coords={routeCoords} />
          </>}

          {/* Trazados, estaciones y flota simulada de TransMilenio */}
          {mode === "transit" && transit?.routes?.map((tmRoute, i) =>
            tmRoute.geometry?.length > 1 ? (
              <Polyline
                key={`tm-route-${tmRoute.id}`}
                positions={tmRoute.geometry}
                pathOptions={{
                  color:"#ef4444",
                  weight:3,
                  opacity:0.55,
                  dashArray: i % 2 ? "10 8" : undefined,
                  lineCap:"round",
                  lineJoin:"round",
                }}
              />
            ) : null
          )}

          {mode === "transit" && [
            ...(transit?.origin_nearby_stations || []),
            ...(transit?.destination_nearby_stations || []),
          ].map(station => (
            <Marker
              key={`tm-station-${station.id}-${station.distance_m}`}
              position={[station.latitude, station.longitude]}
              icon={tmStationIcon}
            >
              <Popup>
                <strong>{station.name}</strong><br />
                Troncal: {station.trunk}<br />
                Distancia sede: {station.distance_m} m
              </Popup>
            </Marker>
          ))}

          {mode === "transit" && tmVehicleMarkers.map(vehicle => (
            <Marker
              key={`tm-bus-${vehicle.id}`}
              position={vehicle.position}
              icon={tmBusIcon(vehicle.label)}
            >
              <Popup>
                <strong>Flota simulada</strong><br />
                Servicio {vehicle.label}
              </Popup>
            </Marker>
          ))}

          {/* Zonas de eventos de tráfico */}
          {events.map(ev => (
            <Circle key={ev.id}
              center={[ev.latitude, ev.longitude]}
              radius={ev.radius_m}
              pathOptions={{
                color:       SEV_COLOR[ev.severity] || "#ff7b00",
                fillColor:   SEV_COLOR[ev.severity],
                fillOpacity: 0.18,
                weight:      2,
              }}>
              <Popup>
                <strong>{EV_ICON[ev.event_type]} {ev.event_type.replace("_"," ")}</strong><br/>
                Severidad: {ev.severity}<br/>
                {ev.description}<br/>
                Factor demora: ×{ev.delay_factor?.toFixed(1)}
              </Popup>
            </Circle>
          ))}

        </MapContainer>

        {/* Leyenda flotante */}
        <div style={{
          position:"absolute", bottom:20, right:16, zIndex:1000,
          background:"rgba(26,29,39,0.93)", backdropFilter:"blur(8px)",
          borderRadius:10, padding:"0.65rem 0.9rem",
          border:"1px solid #2e3248", minWidth:175,
          fontSize:"0.72rem", color:"#7b809a",
          pointerEvents:"none",
        }}>
          <div style={{ color:"#e2e4f0", fontWeight:700,
                        marginBottom:"0.4rem", fontSize:"0.78rem" }}>🗺 Leyenda</div>
          {[
            ["#4f98a3", "━━", "Ruta óptima"],
            ["#e3b341", "──", "Alternativa A"],
            ["#f85149", "──", "Alternativa B"],
            ["#4f98a3", "●",  "Origen (A)"],
            ["#6daa45", "●",  "Destino (B)"],
            ["#ef4444", "━",  "Troncal TM"],
            ["#ef4444", "TM", "Flota simulada"],
            ["#f85149", "◉",  "Evento crítico"],
            ["#ff7b00", "◉",  "Evento alto"],
            ["#e3b341", "◉",  "Evento medio"],
          ].map(([c, sym, lbl]) => (
            <div key={lbl} style={{ display:"flex", gap:"0.4rem",
                                    alignItems:"center", marginBottom:"0.15rem" }}>
              <span style={{ color:c, fontWeight:800, minWidth:22, fontSize:"0.82rem" }}>{sym}</span>
              <span>{lbl}</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
