import { useState, useEffect } from "react";
import AppNav from "../components/AppNav.jsx";
import DataFreshnessBadge from "../components/DataFreshnessBadge.jsx";
import { getDashboardStatus, getTrafficEvents, simulateTraffic } from "../services/api.js";

export default function Dashboard() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);

  const refresh = () => {
    getDashboardStatus().then(setStatus).catch(() => {});
    getTrafficEvents().then(setEvents).catch(() => {});
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ minHeight: "100dvh", background: "var(--bg)" }}>
      <header style={{ padding: "1rem", borderBottom: "1px solid var(--border)" }}>
        <h1 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Real-Time Dashboard</h1>
        <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
          Live transit, weather, and congestion for Bogotá
        </p>
      </header>
      <AppNav />

      <div style={{ padding: "1rem", display: "grid", gap: "1rem", maxWidth: 900, margin: "0 auto" }}>
        {status && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "0.75rem" }}>
              {[
                ["Buses tracked", status.vehicle_count, "🚌"],
                ["Universidades occ.", `${status.universidades_occupancy}%`, status.universidades_congested ? "🔴" : "🟢"],
                ["Rain", `${status.weather?.rain_mmh ?? 0} mm/h`, "🌧"],
                ["SDM congestion", `${Math.round((status.sdm_congestion || 0) * 100)}%`, "🚗"],
              ].map(([label, val, icon]) => (
                <div key={label} className="result-box" style={{ padding: "0.85rem" }}>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{label}</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: "1.4rem", fontWeight: 700, color: "var(--electric)" }}>
                    {icon} {val}
                  </div>
                </div>
              ))}
            </div>

            <div className="result-box" style={{ padding: "0.85rem" }}>
              <div className="section-label">Data freshness</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                {(status.data_freshness || []).map(f => (
                  <DataFreshnessBadge key={f.source} source={f.source} ageSeconds={f.age_seconds} stale={f.stale} />
                ))}
              </div>
            </div>
          </>
        )}

        <div className="result-box" style={{ padding: "0.85rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span className="section-label" style={{ margin: 0 }}>Simulations</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
            {["peak", "rain", "incident", "clear"].map(s => (
              <button key={s} type="button" onClick={() => simulateTraffic(s).then(refresh)}
                style={{ background: "var(--surface-2)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 6, padding: "0.5rem", cursor: "pointer", fontSize: "0.75rem" }}>
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="result-box" style={{ padding: "0.85rem" }}>
          <div className="section-label">Active traffic events ({events.length})</div>
          {events.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: 8 }}>No active events</p>
          ) : events.map(ev => (
            <div key={ev.id} style={{ padding: "0.5rem 0", borderTop: "1px solid var(--border)", fontSize: "0.8rem" }}>
              <strong>{ev.event_type}</strong> — {ev.severity}
              {ev.description && <div style={{ color: "var(--text-muted)" }}>{ev.description}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
