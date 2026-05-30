"""Carga y sincronización de las 6 facultades UDFJC desde backend/data/campuses.json"""

import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campus import Campus
from app.models.route_edge import RouteEdge

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CAMPUSES_FILE = DATA_DIR / "campuses.json"
EDGES_FILE = DATA_DIR / "route_edges.json"


def load_campuses_json() -> list[dict]:
    with open(CAMPUSES_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_edges_json() -> list[dict]:
    with open(EDGES_FILE, encoding="utf-8") as f:
        return json.load(f)


def allowed_campus_ids() -> set[int]:
    return {row["id"] for row in load_campuses_json()}


async def reconcile_faculties(db: AsyncSession) -> dict:
    """
    Deja en BD exactamente las 6 facultades del JSON oficial.
    Elimina sedes antiguas y reconstruye aristas del grafo ACO.
    """
    catalog = load_campuses_json()
    allowed_ids = {row["id"] for row in catalog}

    # Quitar aristas y sedes que ya no aplican
    await db.execute(delete(RouteEdge))
    existing = (await db.execute(select(Campus))).scalars().all()
    for campus in existing:
        if campus.id not in allowed_ids:
            await db.delete(campus)
    await db.flush()

    # Upsert facultades
    upserted = 0
    for row in catalog:
        campus = await db.get(Campus, row["id"])
        if campus:
            for field in ("name", "code", "address", "latitude", "longitude", "description"):
                setattr(campus, field, row[field])
        else:
            db.add(Campus(**row))
        upserted += 1

    await db.flush()

    # Reconstruir grafo multimodal entre facultades
    for edge in load_edges_json():
        db.add(RouteEdge(**edge, pheromone=1.0))

    await db.commit()
    return {
        "faculties": upserted,
        "edges": len(load_edges_json()),
        "removed_old_campuses": len(existing) - len([c for c in existing if c.id in allowed_ids]),
    }


async def seed_campuses(db: AsyncSession) -> None:
    if (await db.execute(select(Campus))).scalars().first():
        return
    for row in load_campuses_json():
        db.add(Campus(**row))


async def sync_campus_coordinates(db: AsyncSession) -> int:
    """Compatibilidad: delega en reconcile_faculties."""
    result = await reconcile_faculties(db)
    return result["faculties"]
