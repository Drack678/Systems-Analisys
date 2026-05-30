from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
import logging

from app.core.database import engine, Base
from app.core.redis_client import close_redis
from app.api.routes import (
    campuses,
    routes as route_router,
    traffic as traffic_router,
    transmilenio as transmilenio_router,
    dashboard,
    equity,
    alerts,
)

logger = logging.getLogger("umos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_data()
    yield
    await close_redis()


app = FastAPI(
    title="UMOS — Urban Mobility Optimization System",
    version="4.0.0",
    description="Multimodal route planning with ACO for UDFJC Bogotá",
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = cid
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campuses.router, prefix="/api/v1")
app.include_router(route_router.router, prefix="/api/v1")
app.include_router(traffic_router.router, prefix="/api/v1")
app.include_router(transmilenio_router.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(equity.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "UMOS", "version": "4.0.0"}

async def seed_data():
    from app.core.database import AsyncSessionLocal
    from app.services.campus_loader import reconcile_faculties

    async with AsyncSessionLocal() as db:
        await reconcile_faculties(db)