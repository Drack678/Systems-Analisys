from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.database import engine, Base
from app.core.redis_client import get_redis
from app.api.routes import campuses, routes as route_router
from app.models import Campus, RouteEdge  # noqa: registra los modelos


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas al iniciar
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed de datos si la tabla está vacía
    await seed_data()
    yield


app = FastAPI(
    title="UMOS API",
    description="Urban Mobility Optimization System — Universidad Distrital",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campuses.router, prefix="/api/v1")
app.include_router(route_router.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "UMOS Backend"}


async def seed_data():
    """Inserta los campus y aristas reales de la UDFJC si la BD está vacía."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.campus import Campus
    from app.models.route_edge import RouteEdge

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(Campus))).scalars().first()
        if count:
            return  # Ya hay datos

        campuses_data = [
            {"name": "Sede Sabio Caldas",  "code": "SC",  "address": "Carrera 7 #40B-53, Chapinero",         "latitude": 4.6341,  "longitude": -74.0637},
            {"name": "Sede Tecnológica",   "code": "ST",  "address": "Calle 68D Bis A Sur #49F-70, Cd. Bolívar","latitude": 4.5469, "longitude": -74.1323},
            {"name": "Sede Macarena A",    "code": "MA",  "address": "Carrera 3 #26A-40, La Candelaria",      "latitude": 4.6046,  "longitude": -74.0714},
            {"name": "Sede Macarena B",    "code": "MB",  "address": "Carrera 4 #26D-54, La Candelaria",      "latitude": 4.6050,  "longitude": -74.0710},
            {"name": "Sede Vivero",        "code": "SV",  "address": "Cra 5 Este #15-82, Chapinero",          "latitude": 4.6200,  "longitude": -74.0580},
            {"name": "Estación Universidades (TM)", "code": "EU", "address": "Carrera 10 #39-00 (TransMilenio)", "latitude": 4.6310, "longitude": -74.0660},
            {"name": "Portal Sur (TM)",    "code": "PS",  "address": "Autopista Sur - Portal Sur",             "latitude": 4.5590,  "longitude": -74.1510},
        ]

        campus_objs = []
        for data in campuses_data:
            c = Campus(**data, description="")
            db.add(c)
            campus_objs.append(c)
        await db.flush()

        # Aristas reales (origen_id, dest_id, distancia_km, tiempo_min, transporte)
        edges_data = [
            # Sabio Caldas ↔ Estación Universidades
            (1, 6, 0.6,  8,  "WALK"),
            (6, 1, 0.6,  8,  "WALK"),
            # Sabio Caldas ↔ Macarena A (bus/caminata)
            (1, 3, 3.5,  22, "SITP"),
            (3, 1, 3.5,  22, "SITP"),
            # Sabio Caldas ↔ Vivero
            (1, 5, 1.8,  12, "BIKE"),
            (5, 1, 1.8,  12, "BIKE"),
            # Estación Universidades → Portal Sur (TransMilenio)
            (6, 7, 17.0, 55, "TM"),
            (7, 6, 17.0, 55, "TM"),
            # Portal Sur → Sede Tecnológica (SITP + Cable)
            (7, 2, 4.5,  25, "CABLE"),
            (2, 7, 4.5,  25, "CABLE"),
            # Macarena A ↔ Macarena B
            (3, 4, 0.3,  4,  "WALK"),
            (4, 3, 0.3,  4,  "WALK"),
            # Sabio Caldas → Sede Tecnológica (ruta completa)
            (1, 2, 22.0, 90, "TM"),
            (2, 1, 22.0, 90, "TM"),
        ]

        for (oid, did, dist, time, transport) in edges_data:
            e = RouteEdge(
                origin_id=oid, dest_id=did,
                distance_km=dist, travel_time=time,
                transport=transport, pheromone=1.0,
            )
            db.add(e)

        await db.commit()