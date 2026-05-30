export default function ETADisplay({ value, confidenceInterval, weatherAdjusted }) {
  const margin = confidenceInterval
    ? Math.round((confidenceInterval.upper - confidenceInterval.lower) / 2)
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <div style={{
        fontFamily: "var(--font-mono)", fontSize: "1.25rem", fontWeight: 700,
        color: "var(--electric)",
      }}>
        {margin != null ? `~${Math.round(value)} ± ${margin} min` : `${Math.round(value)} min`}
      </div>
      {weatherAdjusted && (
        <span style={{
          fontSize: "0.68rem", color: "#58a6ff",
          background: "#0d1f35", padding: "0.15rem 0.4rem",
          borderRadius: 4, alignSelf: "flex-start",
        }}>
          Weather adjusted
        </span>
      )}
    </div>
  );
}
