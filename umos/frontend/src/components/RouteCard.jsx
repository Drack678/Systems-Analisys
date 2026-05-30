import ETADisplay from "./ETADisplay.jsx";
import CostPerKmBadge from "./CostPerKmBadge.jsx";

const MODE_COLORS = {
  TM: "#e11d48", SITP: "#14b8a6", BIKE: "#22c55e",
  WALK: "#f59e0b", CABLE: "#a855f7", CAR: "#64748b",
};

export default function RouteCard({
  route, selected, onSelect, index = 0,
}) {
  if (!route) return null;
  const borderColor = selected ? "var(--electric)" : "var(--border)";

  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        background: selected ? "#0a1628" : "var(--surface-2)",
        border: `2px solid ${borderColor}`,
        borderRadius: 10, padding: "0.85rem",
        textAlign: "left", cursor: "pointer", width: "100%",
        color: "var(--text)", transition: "border-color 0.15s",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontSize: "0.85rem" }}>{route.label}</span>
        {route.weather_adjusted && (
          <span style={{ fontSize: "0.7rem" }}>Weather adjusted</span>
        )}
      </div>

      <ETADisplay
        value={route.total_time}
        confidenceInterval={route.eta_confidence_interval}
        weatherAdjusted={route.weather_adjusted}
      />

      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr",
        gap: "0.4rem", marginTop: "0.65rem",
      }}>
        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          ${route.total_cost_cop?.toLocaleString()} COP
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          {route.transfers ?? 0} transfers
        </div>
      </div>

      <div style={{ marginTop: "0.5rem" }}>
        <CostPerKmBadge
          value={route.cost_per_km}
          level={route.equity_level}
        />
      </div>

      <div style={{ display: "flex", gap: 4, marginTop: 8, flexWrap: "wrap" }}>
        {(route.transport_modes || []).map(m => (
          <span key={m} style={{
            fontSize: "0.62rem", fontWeight: 700, textTransform: "uppercase",
            padding: "0.1rem 0.35rem", borderRadius: 4,
            background: (MODE_COLORS[m] || "#555") + "33",
            color: MODE_COLORS[m] || "#aaa",
          }}>{m}</span>
        ))}
      </div>
    </button>
  );
}
