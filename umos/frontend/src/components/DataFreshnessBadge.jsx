export default function DataFreshnessBadge({ source, ageSeconds, stale }) {
  const label = ageSeconds == null
    ? "Unavailable"
    : ageSeconds === 0
      ? "Live"
      : `${ageSeconds}s ago`;

  const color = stale ? "#f85149" : ageSeconds > 30 ? "#e3b341" : "#3fb950";

  return (
    <span style={{
      fontFamily: "var(--font-mono)", fontSize: "0.65rem",
      color, display: "inline-flex", alignItems: "center", gap: 4,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%",
        background: color, display: "inline-block",
      }} />
      {source} · {label}
    </span>
  );
}
