const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    let errMsg = res.statusText;
    try {
      const err = await res.json();
      if (err.detail) {
        if (typeof err.detail === "string") {
          errMsg = err.detail;
        } else if (Array.isArray(err.detail)) {
          errMsg = err.detail.map(d => `${d.loc?.join('.') || 'field'}: ${d.msg}`).join(', ');
        } else {
          errMsg = JSON.stringify(err.detail);
        }
      }
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }
  return res.json();
}

export const getCampuses = () => request("/campuses/");
export const getWeather = () => request("/routes/weather");

export const optimizeRoute = (originId, destinationId, transportMode, rain = false) =>
  request("/routes/optimize", {
    method: "POST",
    body: JSON.stringify({
      origin_id: originId,
      destination_id: destinationId,
      transport_mode: transportMode,
      rain,
    }),
  });

export const computeRoute = (body) =>
  request("/routes/compute", { method: "POST", body: JSON.stringify(body) });

export const getTrafficEvents = () => request("/traffic/events");
export const createTrafficEvent = (data) =>
  request("/traffic/events", { method: "POST", body: JSON.stringify(data) });
export const resolveTrafficEvent = (id) =>
  request(`/traffic/events/${id}/resolve`, { method: "PATCH" });
export const simulateTraffic = (scenario) =>
  request(`/traffic/simulations/${scenario}`, { method: "POST" });

export const getTransmilenioRecommendations = (origin, destination) =>
  request(
    `/transmilenio/recommendations?origin_lat=${origin.latitude}&origin_lon=${origin.longitude}` +
    `&dest_lat=${destination.latitude}&dest_lon=${destination.longitude}` +
    `&origin_name=${encodeURIComponent(origin.name)}&dest_name=${encodeURIComponent(destination.name)}`
  );

export const getDashboardStatus = () => request("/dashboard/status");
export const getDataFreshness = () => request("/dashboard/freshness");
export const getEquityMetrics = () => request("/equity/metrics");
export const getAlerts = () => request("/alerts/");
