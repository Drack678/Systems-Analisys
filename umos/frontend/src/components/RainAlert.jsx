/**
 * RainAlert — Aviso proactivo de lluvia.
 * Recibe el objeto weather del endpoint /routes/weather y muestra 3 estados:
 *  1. Sin lluvia ni pronóstico         → no se renderiza nada
 *  2. Lluvia inminente (en 30 min)     → caja amarilla con sugerencia
 *  3. Lluviendo ahora                  → caja azul con intensidad
 */

export default function RainAlert({ weather, rainActive, onActivateRain }) {
  if (!weather) return null;

  const rainNow = weather.rain_mm || 0;
  const forecastSoon = weather.forecast_30min_mmh || 0;
  const isRaining = weather.is_raining;

  // Estado 3: lluviendo ahora (prioridad máxima)
  if (isRaining && rainNow > 0.2) {
    return (
      <div style={alertBox("#0c4a6e", "#0ea5e9")}>
        <div style={alertHeader}>
          <span style={{ fontSize: "1.2rem" }}>🌧</span>
          <span style={{ color: "#0ea5e9" }}>LLUVIENDO AHORA</span>
        </div>
        <p style={alertText}>
          Intensidad: <strong>{rainNow.toFixed(1)} mm/h</strong>
          {weather.description && ` · ${weather.description}`}
        </p>
        <p style={{ ...alertText, marginTop: 4, opacity: 0.8 }}>
          Tu ruta puede tardar ~30% más de lo usual.
          {!rainActive && " Recalcula con simulación de lluvia para una estimación más precisa."}
        </p>
        {!rainActive && (
          <button
            type="button"
            onClick={onActivateRain}
            style={alertButton("#0ea5e9")}
          >
            Activar simulación de lluvia
          </button>
        )}
      </div>
    );
  }

  // Estado 2: lluvia esperada en 30 min (umbral configurable)
  if (forecastSoon >= 1.5) {
    return (
      <div style={alertBox("#3d2914", "#f59e0b")}>
        <div style={alertHeader}>
          <span style={{ fontSize: "1.2rem" }}>⚠️</span>
          <span style={{ color: "#f59e0b" }}>LLUVIA INMINENTE</span>
        </div>
        <p style={alertText}>
          Se espera lluvia de ~<strong>{forecastSoon.toFixed(1)} mm/h</strong> en los próximos 30 min.
        </p>
        <p style={{ ...alertText, marginTop: 4, opacity: 0.8 }}>
          Considera salir antes o recalcular tu ruta con simulación de lluvia.
        </p>
        {!rainActive && (
          <button
            type="button"
            onClick={onActivateRain}
            style={alertButton("#f59e0b")}
          >
            Activar simulación de lluvia
          </button>
        )}
      </div>
    );
  }

  // Estado 1: sin lluvia, no mostrar nada
  return null;
}


// ───── estilos auxiliares (inline) ─────

const alertBox = (bg, border) => ({
  background: bg,
  border: `1px solid ${border}`,
  borderRadius: 8,
  padding: "0.75rem 0.85rem",
  marginBottom: "0.5rem",
});

const alertHeader = {
  display: "flex",
  alignItems: "center",
  gap: "0.4rem",
  fontSize: "0.72rem",
  fontWeight: 700,
  letterSpacing: "0.05em",
  marginBottom: "0.4rem",
  textTransform: "uppercase",
};

const alertText = {
  fontSize: "0.78rem",
  color: "var(--text)",
  lineHeight: 1.4,
  margin: 0,
};

const alertButton = (color) => ({
  marginTop: 8,
  background: "transparent",
  border: `1px solid ${color}`,
  borderRadius: 6,
  padding: "0.4rem 0.7rem",
  color: color,
  fontWeight: 600,
  fontSize: "0.72rem",
  cursor: "pointer",
  transition: "background 0.2s",
});