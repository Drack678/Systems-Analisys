# UMOS — Urban Mobility Optimization System

Multimodal route planning for **Universidad Distrital Francisco José de Caldas (UDFJC)** in Bogotá, Colombia. Built as the capstone synthesis of workshops W1–W4: field-calibrated **Ant Colony Optimization (ACO)**, weather-aware routing, equity metrics, and real-time data integration.

## Features

- **ACO routing engine** — 50 ants, elitist deposit, rain modifiers (1.63×), cycling suppression above 2 mm/h, bus-bunching penalty at Universidades congestion
- **Equity panel** — cost-per-km on every route card; 38.5% Norte/Sur travel gap surfaced
- **5 external data sources** — TransMilenio, SDM, IDEAM, IDU, UDFJC (mock adapters + Redis circuit breaker fallback)
- **4 UI screens** — Route Planner, Real-Time Dashboard, Equity View, Alert Center
- **27 UDFJC campuses** — seeded graph with TransMilenio, SITP, walking, cycling, cable edges

## Quick Start

```bash
# 1. Copy environment
cp .env.example backend/.env

# 2. Start stack
docker compose up --build

# 3. Open app
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
```

### Local development (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Requires PostgreSQL (PostGIS) and Redis running locally — see `docker-compose.yml` for connection strings.

## API Highlights

| Endpoint | Description |
|---|---|
| `POST /api/v1/routes/compute` | Spec ACO contract (lat/lng or campus IDs) |
| `POST /api/v1/routes/optimize` | Legacy campus-to-campus optimizer |
| `GET /api/v1/dashboard/status` | Live dashboard metrics + data freshness |
| `GET /api/v1/equity/metrics` | Equity gap and zone breakdown |
| `GET /api/v1/alerts/` | Rain, Pico y Placa, traffic alerts |

## Architecture

```
umos/
├── backend/          FastAPI monolith (modular services)
│   └── app/services/
│       ├── aco/              ACO algorithm (Python)
│       ├── data_integration/ 5 upstream adapters + circuit breaker
│       └── equity_service.py cost/km + zone detection
├── frontend/         React 18 + Vite + Leaflet (dark cartographic UI)
└── docker-compose.yml
```

The master spec describes a full NestJS microservices deployment (Kong, GKE, Terraform). This repository implements the **core application logic** in a deployable monolith suitable for development and capstone demonstration; the service boundaries map 1:1 to the spec modules for future extraction.

## ACO Parameters

Calibrated from W1 field data and W4 simulation:

| Parameter | Value |
|---|---|
| α (pheromone) | 1.0 |
| β (heuristic) | 2.0 |
| ρ (evaporation) | 0.1 |
| Ants / iteration | 50 |
| Rain multiplier | 1.63 @ >2 mm/h |

## License

Academic project — Universidad Distrital Francisco José de Caldas.
