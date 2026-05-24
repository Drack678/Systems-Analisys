import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api/v1",
  timeout: 30000,
});

// ── Campuses ─────────────────────────────────────────────────────────────────
export const getCampuses = () =>
  api.get("/campuses/").then(r => r.data);

// ── Rutas ────────────────────────────────────────────────────────────────────
export const optimizeRoute = (originId, destinationId, transportMode, rain = false) =>
  api.post("/routes/optimize", {
    origin_id:      originId,
    destination_id: destinationId,
    transport_mode: transportMode,
    rain,
  }).then(r => r.data);

export const getWeather = () =>
  api.get("/routes/weather").then(r => r.data);

// ── Tráfico ───────────────────────────────────────────────────────────────────
export const getTrafficEvents = () =>
  api.get("/traffic/events").then(r => r.data);

export const createTrafficEvent = (data) =>
  api.post("/traffic/events", data).then(r => r.data);

export const resolveTrafficEvent = (id) =>
  api.patch(`/traffic/events/${id}/resolve`).then(r => r.data);

export const getEventTypes = () =>
  api.get("/traffic/event-types").then(r => r.data);

export const simulateTraffic = (scenario) =>
  api.post(`/traffic/simulations/${scenario}`).then(r => r.data);

export const getTransmilenioRecommendations = (origin, destination) =>
  api.get("/transmilenio/recommendations", {
    params: {
      origin_lat: origin.latitude,
      origin_lon: origin.longitude,
      dest_lat: destination.latitude,
      dest_lon: destination.longitude,
    },
  }).then(r => r.data);

export const getNearbyTransmilenio = (lat, lon, radiusM = 1000) =>
  api.get("/transmilenio/routes/nearby", {
    params: { lat, lon, radius_m: radiusM },
  }).then(r => r.data);
