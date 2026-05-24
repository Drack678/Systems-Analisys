from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    campuses,
    routes as route_router,
    traffic as traffic_router,
    transmilenio as transmilenio_router,
)
from app.core.database import Base, engine
from app.models import Campus, RouteEdge, TrafficEvent  # noqa: registra los modelos


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_data()
    yield


app = FastAPI(
    title="UMOS API",
    description="Urban Mobility Optimization System - Universidad Distrital",
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
app.include_router(traffic_router.router, prefix="/api/v1")
app.include_router(transmilenio_router.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "UMOS Backend"}


async def seed_data():
    """Upsert de sedes oficiales UD y aristas base de movilidad."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.campus import Campus
    from app.models.route_edge import RouteEdge

    campuses_data = [
        {"name": "Aduanilla de Paiba", "code": "ADP", "address": "Calle 13 #31-75", "latitude": 4.6205, "longitude": -74.0909},
        {"name": "Calle 34", "code": "C34", "address": "Calle 34 #13-13", "latitude": 4.6226, "longitude": -74.0688},
        {"name": "Calle 40 - Edificio Administrativo", "code": "SC", "address": "Carrera 7 #40B-53", "latitude": 4.6341, "longitude": -74.0637},
        {"name": "Calle 40 - Facultad de Ingenieria", "code": "ING", "address": "Carrera 8 #40-62", "latitude": 4.6334, "longitude": -74.0649},
        {"name": "Ciudadela Universitaria Bosa Porvenir - entrada 1", "code": "BP1", "address": "Calle 52 Sur #93D-97", "latitude": 4.6289, "longitude": -74.1992},
        {"name": "Ciudadela Universitaria Bosa Porvenir - entrada 2", "code": "BP2", "address": "Calle 52 Sur #92A-45", "latitude": 4.6299, "longitude": -74.1969},
        {"name": "Edificio CAXDAC", "code": "CAX", "address": "Calle 35 #7-25", "latitude": 4.6259, "longitude": -74.0635},
        {"name": "Edificio Villa Esther", "code": "VES", "address": "Carrera 13 #42-36", "latitude": 4.6363, "longitude": -74.0670},
        {"name": "El Ensueno", "code": "ENS", "address": "Lote 1 Manzana 2 Plan Parcial El Ensueno", "latitude": 4.5565, "longitude": -74.1512},
        {"name": "El Tibar", "code": "TIB", "address": "Km 3.5 via Choachi - La Union, Guanza", "latitude": 4.5798, "longitude": -74.0035},
        {"name": "Emisora LAUD 90.4 F.M", "code": "LAUD", "address": "Calle 31 #6-42/62 Oficina 801", "latitude": 4.6157, "longitude": -74.0668},
        {"name": "ILUD - Parkway", "code": "ILP", "address": "Carrera 21 #44-07", "latitude": 4.6374, "longitude": -74.0718},
        {"name": "ILUD - San Luis Calle 58 - entrada 1", "code": "SL1", "address": "Calle 58B #17-18", "latitude": 4.6481, "longitude": -74.0658},
        {"name": "ILUD - San Luis Calle 58 - entrada 2", "code": "SL2", "address": "Calle 59 #17-19", "latitude": 4.6490, "longitude": -74.0658},
        {"name": "Luis A. Calvo", "code": "LAC", "address": "Carrera 9 #52-52", "latitude": 4.6432, "longitude": -74.0619},
        {"name": "Macarena A - entrada 1", "code": "MA1", "address": "Carrera 3 #26A-40", "latitude": 4.6108, "longitude": -74.0655},
        {"name": "Macarena A - entrada 2", "code": "MA2", "address": "Carrera 1 Este #33-54", "latitude": 4.6202, "longitude": -74.0594},
        {"name": "Macarena B", "code": "MB", "address": "Carrera 4A #26D-54", "latitude": 4.6102, "longitude": -74.0664},
        {"name": "Palacio de la Merced", "code": "MER", "address": "Carrera 13 #14-69", "latitude": 4.6019, "longitude": -74.0735},
        {"name": "Seccion de Publicaciones - entrada 1", "code": "PUB1", "address": "Carrera 24 #34-37", "latitude": 4.6225, "longitude": -74.0796},
        {"name": "Seccion de Publicaciones - entrada 2", "code": "PUB2", "address": "Carrera 28 #34-20", "latitude": 4.6226, "longitude": -74.0846},
        {"name": "Sede administrativa FCMYN", "code": "FCMYN", "address": "Carrera 4 #26D-31", "latitude": 4.6102, "longitude": -74.0660},
        {"name": "Sede Edificio Santo Domingo", "code": "SDO", "address": "Calle 52 #7-11", "latitude": 4.6423, "longitude": -74.0609},
        {"name": "Sotanos - entrada 1", "code": "SOT1", "address": "Carrera 7 #12C-59", "latitude": 4.5993, "longitude": -74.0730},
        {"name": "Sotanos - entrada 2", "code": "SOT2", "address": "Carrera 8 #12C-58", "latitude": 4.5994, "longitude": -74.0741},
        {"name": "Tecnologica", "code": "ST", "address": "Calle 68D Bis A Sur #49F-70", "latitude": 4.5469, "longitude": -74.1323},
        {"name": "TEINCO Calle 42", "code": "TEI", "address": "Calle 42 #16-86", "latitude": 4.6361, "longitude": -74.0714},
        {"name": "Universidad Autonoma - 30 Aniversario", "code": "UA30", "address": "Calle 12B #4A-68", "latitude": 4.5983, "longitude": -74.0710},
        {"name": "Universidad Autonoma - 9 pisos", "code": "UA9", "address": "Carrera 6 #10-58/72", "latitude": 4.5965, "longitude": -74.0734},
        {"name": "Universidad Autonoma - Casa ASAB Arte Danzario", "code": "ASAB", "address": "Carrera 5 #12-74", "latitude": 4.5985, "longitude": -74.0712},
        {"name": "Universidad ECCI - Sede Cristiano Luque", "code": "ECCI", "address": "Carrera 10 #19-62", "latitude": 4.6072, "longitude": -74.0751},
        {"name": "Vivero - entrada 1", "code": "SV", "address": "Carrera 5 Este #15-82", "latitude": 4.5967, "longitude": -74.0616},
        {"name": "Vivero - entrada 2", "code": "SV2", "address": "Calle 14 #7-46 Este", "latitude": 4.5948, "longitude": -74.0627},
    ]

    edges_data = [
        ("SC", "ING", 0.3, 5, "WALK"),
        ("ING", "SC", 0.3, 5, "WALK"),
        ("MA1", "MB", 0.35, 5, "WALK"),
        ("MB", "MA1", 0.35, 5, "WALK"),
        ("SV", "SV2", 0.35, 5, "WALK"),
        ("SV2", "SV", 0.35, 5, "WALK"),
        ("BP1", "BP2", 0.45, 6, "WALK"),
        ("BP2", "BP1", 0.45, 6, "WALK"),
        ("SC", "MA1", 3.2, 22, "SITP"),
        ("MA1", "SC", 3.2, 22, "SITP"),
        ("SC", "SV", 5.6, 32, "SITP"),
        ("SV", "SC", 5.6, 32, "SITP"),
        ("ST", "ENS", 2.8, 18, "SITP"),
        ("ENS", "ST", 2.8, 18, "SITP"),
        ("ADP", "SC", 6.0, 28, "SITP"),
        ("SC", "ADP", 6.0, 28, "SITP"),
        ("BP1", "ST", 12.5, 55, "SITP"),
        ("ST", "BP1", 12.5, 55, "SITP"),
    ]

    async with AsyncSessionLocal() as db:
        campus_by_code = {
            campus.code: campus
            for campus in (await db.execute(select(Campus))).scalars().all()
        }

        for data in campuses_data:
            campus = campus_by_code.get(data["code"])
            if campus:
                for key, value in data.items():
                    setattr(campus, key, value)
                campus.description = campus.description or "Sede oficial Universidad Distrital"
            else:
                campus = Campus(**data, description="Sede oficial Universidad Distrital")
                db.add(campus)
                campus_by_code[data["code"]] = campus
        await db.flush()

        existing_edges = {
            (edge.origin_id, edge.dest_id): edge
            for edge in (await db.execute(select(RouteEdge))).scalars().all()
        }

        for origin_code, dest_code, dist, minutes, transport in edges_data:
            origin = campus_by_code[origin_code]
            dest = campus_by_code[dest_code]
            edge = existing_edges.get((origin.id, dest.id))
            if edge:
                edge.distance_km = dist
                edge.travel_time = minutes
                edge.transport = transport
            else:
                db.add(
                    RouteEdge(
                        origin_id=origin.id,
                        dest_id=dest.id,
                        distance_km=dist,
                        travel_time=minutes,
                        transport=transport,
                        pheromone=1.0,
                    )
                )

        await db.commit()
