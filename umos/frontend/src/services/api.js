import axios from "axios";

// En Docker: usa proxy de Vite (/api → backend:8000)
// En local sin Docker: apunta directo a localhost:8000
const BASE = typeof window !== "undefined" && window.location.port === "5173"
  ? "/api/v1"
  : "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
});

export const getCampuses = () =>
  api.get("/campuses/").then((r) => r.data);

export const optimizeRoute = (originId, destinationId, mode = "fastest", rain = false) =>
  api.post("/routes/optimize", {
    origin_id: originId,
    destination_id: destinationId,
    mode,
    rain,
  }).then((r) => r.data);

export const getWeather = () =>
  api.get("/routes/weather").then((r) => r.data);