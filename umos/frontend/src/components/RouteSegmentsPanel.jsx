/**
 * RouteSegmentsPanel — Lista de pasos tipo Moovit.
 *
 * Recibe una ruta del backend (con array `segments`) y renderiza
 * un timeline vertical, cada paso con su icono, instrucción,
 * duración y distancia. El trazo lateral usa el color del modo
 * de transporte para que el usuario asocie visualmente cada paso
 * con su correspondiente tramo en el mapa.
 */
export default function RouteSegmentsPanel({ route }) {
  if (!route?.segments?.length) {
    return null;
  }

  return (
    <div
      style={{
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "0.85rem",
        marginTop: "0.5rem",
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          fontWeight: 700,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "0.75rem",
        }}
      >
        Paso a paso ({route.segments.length}{" "}
        {route.segments.length === 1 ? "tramo" : "tramos"})
      </div>

      <div style={{ display: "flex", flexDirection: "column" }}>
        {route.segments.map((seg, i) => {
          const isLast = i === route.segments.length - 1;
          return (
            <SegmentRow
              key={i}
              segment={seg}
              isLast={isLast}
            />
          );
        })}
      </div>

      <div
        style={{
          marginTop: "0.5rem",
          paddingTop: "0.5rem",
          borderTop: "1px dashed var(--border)",
          fontSize: "0.72rem",
          color: "var(--text-muted)",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>Total</span>
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>
          {Math.round(route.total_time)} min · {route.total_distance?.toFixed(1)} km
        </span>
      </div>
    </div>
  );
}


function SegmentRow({ segment, isLast }) {
  const color = segment.color || "#64748b";
  const icon = segment.icon || "•";

  return (
    <div style={{ display: "flex", gap: "0.75rem", position: "relative" }}>
      {/* Columna izquierda: icono + línea vertical */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          minWidth: 28,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            background: color + "22",
            border: `2px solid ${color}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "0.85rem",
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
        {!isLast && (
          <div
            style={{
              flex: 1,
              width: 2,
              background: color,
              opacity: 0.5,
              marginTop: 2,
              marginBottom: 2,
              minHeight: 18,
            }}
          />
        )}
      </div>

      {/* Columna derecha: instrucción + métricas */}
      <div
        style={{
          flex: 1,
          paddingBottom: isLast ? 0 : "0.85rem",
        }}
      >
        <div
          style={{
            fontSize: "0.8rem",
            color: "var(--text)",
            lineHeight: 1.35,
            fontWeight: 600,
          }}
        >
          {segment.instruction || `${segment.from_name} → ${segment.to_name}`}
        </div>
        <div
          style={{
            fontSize: "0.7rem",
            color: "var(--text-muted)",
            marginTop: 3,
            fontFamily: "var(--font-mono)",
          }}
        >
          {segment.duration_min} min · {(segment.distance_km * 1000).toFixed(0)}m
          <span
            style={{
              marginLeft: 8,
              padding: "0.05rem 0.4rem",
              borderRadius: 4,
              background: color + "22",
              color: color,
              fontSize: "0.62rem",
              fontWeight: 700,
              textTransform: "uppercase",
            }}
          >
            {segment.mode}
          </span>
        </div>
      </div>
    </div>
  );
}