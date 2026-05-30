import { Marker } from "react-leaflet";
import L from "leaflet";

export function FacultyDot({ campus, isOrigin, isDest, onClick }) {
  const isActive = isOrigin || isDest;
  const color = isOrigin ? "#3b82f6" : isDest ? "#22c55e" : "#64748b";

  return (
    <Marker
      position={[campus.latitude, campus.longitude]}
      icon={L.divIcon({
        className: "faculty-dot-marker",
        iconAnchor: [6, 6],
        html: `<div style="
          width:${isActive ? 14 : 10}px;height:${isActive ? 14 : 10}px;
          border-radius:50%;background:${color};
          border:2px solid #fff;box-shadow:0 1px 6px #0008;
          cursor:pointer;opacity:${isActive ? 1 : 0.85};
        " title="${campus.name}"></div>`,
      })}
      eventHandlers={{ click: onClick }}
    />
  );
}

export function AntMarkers({ vehicles }) {
  const icon = (label) =>
    L.divIcon({
      className: "",
      iconAnchor: [11, 11],
      html: `<div style="
        width:22px;height:22px;border-radius:50%;background:#e11d48;color:#fff;
        display:flex;align-items:center;justify-content:center;
        font-size:9px;font-weight:800;border:2px solid #fff;
        box-shadow:0 2px 8px #000a;font-family:monospace;
      ">${label}</div>`,
    });

  return vehicles.map((v) => (
    <Marker
      key={v.id}
      position={[v.latitude, v.longitude]}
      icon={icon(v.label)}
    />
  ));
}

export function pointAlong(geometry, progress) {
  if (!geometry?.length) return null;
  const idx = Math.min(Math.floor(progress * (geometry.length - 1)), geometry.length - 1);
  return geometry[idx];
}

export function animateAnts(routes, tick, periodSec = 12) {
  const t = tick / (periodSec * 1000 / 60);
  const vehicles = [];
  for (const route of routes || []) {
    const geom = route.geometry || [];
    if (geom.length < 2) continue;
    for (const ant of route.ants || []) {
      const progress = (t * 0.04 + ant.offset) % 1;
      const pt = pointAlong(geom, progress);
      if (pt) {
        vehicles.push({
          id: ant.id,
          label: route.short_name || route.name,
          latitude: pt[0],
          longitude: pt[1],
        });
      }
    }
  }
  return vehicles;
}
