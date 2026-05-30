const LEVEL_COLORS = {
  green: { bg: "#0d2818", border: "#238636", text: "#3fb950" },
  amber: { bg: "#2a1f0a", border: "#d29922", text: "#e3b341" },
  red:   { bg: "#2a0f0f", border: "#f85149", text: "#f85149" },
};

export default function CostPerKmBadge({ value, zone, level = "green" }) {
  const c = LEVEL_COLORS[level] || LEVEL_COLORS.green;
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: "0.35rem",
      background: c.bg, border: `1px solid ${c.border}`,
      borderRadius: 6, padding: "0.25rem 0.55rem",
      fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: c.text,
    }}>
      <span>${value?.toLocaleString()} COP/km</span>
      {zone && <span style={{ opacity: 0.7 }}>· {zone}</span>}
    </div>
  );
}
