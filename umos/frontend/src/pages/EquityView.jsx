import { useState, useEffect } from "react";
import AppNav from "../components/AppNav.jsx";
import CostPerKmBadge from "../components/CostPerKmBadge.jsx";
import { getEquityMetrics } from "../services/api.js";

const LEVEL = {
  green: "#3fb950",
  amber: "#e3b341",
  red: "#f85149",
};

export default function EquityView() {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    getEquityMetrics().then(setMetrics).catch(() => {});
  }, []);

  if (!metrics) {
    return (
      <div style={{ padding: "2rem", color: "var(--text-muted)" }}>Loading equity metrics...</div>
    );
  }

  return (
    <div style={{ minHeight: "100dvh", background: "var(--bg)" }}>
      <header style={{ padding: "1rem", borderBottom: "1px solid var(--border)" }}>
        <h1 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Equity Panel</h1>
        <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
          Cost-per-km comparison — Norte vs Sur travel disparity
        </p>
      </header>
      <AppNav />

      <div style={{ padding: "1rem", maxWidth: 720, margin: "0 auto", display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div className="result-box" style={{ padding: "1rem", borderColor: LEVEL.red }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "2rem", fontWeight: 700, color: LEVEL.red }}>
            {metrics.equity_gap_percent}%
          </div>
          <div style={{ fontSize: "0.85rem", marginTop: 4 }}>Travel time gap (Norte vs Sur)</div>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 8 }}>
            {metrics.disparity_message}
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
          <div className="result-box" style={{ padding: "0.85rem" }}>
            <div className="section-label">Norte avg time</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "1.5rem", color: LEVEL.green }}>
              {metrics.north_avg_time_min} min
            </div>
            <CostPerKmBadge value={metrics.north_avg_cost_per_km} zone="Norte" level="green" />
          </div>
          <div className="result-box" style={{ padding: "0.85rem" }}>
            <div className="section-label">Sur avg time</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "1.5rem", color: LEVEL.red }}>
              {metrics.south_avg_time_min} min
            </div>
            <CostPerKmBadge value={metrics.south_avg_cost_per_km} zone="Sur" level="red" />
          </div>
        </div>

        <div className="result-box" style={{ padding: "0.85rem" }}>
          <div className="section-label">Campuses by zone</div>
          {Object.entries(metrics.campuses_by_zone || {}).map(([zone, names]) => (
            <div key={zone} style={{ marginTop: 8 }}>
              <strong style={{ color: zone === "Sur" ? LEVEL.red : zone === "Norte" ? LEVEL.green : "var(--text)" }}>
                {zone}
              </strong>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginLeft: 8 }}>
                ({names.length} sedes)
              </span>
              <ul style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4, paddingLeft: "1.2rem" }}>
                {names.slice(0, 5).map(n => <li key={n}>{n}</li>)}
                {names.length > 5 && <li>+{names.length - 5} more</li>}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
