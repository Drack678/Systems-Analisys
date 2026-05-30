import { useState, useEffect } from "react";
import AppNav from "../components/AppNav.jsx";
import { getAlerts } from "../services/api.js";

const SEV_STYLE = {
  CRITICAL: { bg: "#2a0f0f", border: "#f85149" },
  HIGH:     { bg: "#2a1500", border: "#ff7b00" },
  MEDIUM:   { bg: "#2a1f0a", border: "#e3b341" },
  LOW:      { bg: "#1a1d27", border: "#58a6ff" },
};

export default function AlertCenter() {
  const [data, setData] = useState(null);

  useEffect(() => {
    getAlerts().then(setData).catch(() => {});
    const t = setInterval(() => getAlerts().then(setData).catch(() => {}), 30000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ minHeight: "100dvh", background: "var(--bg)" }}>
      <header style={{ padding: "1rem", borderBottom: "1px solid var(--border)" }}>
        <h1 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Alert Center</h1>
        <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
          Rain, Pico y Placa, and incident notifications
        </p>
      </header>
      <AppNav />

      <div style={{ padding: "1rem", maxWidth: 640, margin: "0 auto" }}>
        {!data ? (
          <p style={{ color: "var(--text-muted)" }}>Loading alerts...</p>
        ) : data.alerts.length === 0 ? (
          <div className="result-box" style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
            No active alerts
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
            {data.alerts.map(alert => {
              const s = SEV_STYLE[alert.severity] || SEV_STYLE.MEDIUM;
              return (
                <div
                  key={alert.id}
                  style={{
                    background: s.bg,
                    border: `1px solid ${s.border}`,
                    borderRadius: 10,
                    padding: "0.85rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <strong style={{ fontSize: "0.88rem" }}>{alert.title}</strong>
                    <span style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>{alert.type}</span>
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 6 }}>{alert.message}</p>
                  {alert.lead_time_minutes != null && alert.lead_time_minutes > 0 && (
                    <span style={{ fontSize: "0.72rem", color: "#58a6ff" }}>
                      Lead time: {alert.lead_time_minutes} min
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
