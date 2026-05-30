from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.campus import Campus
from app.schemas.campus import CampusResponse, CampusCreate, CampusUpdate
from app.services.campus_loader import reconcile_faculties, load_campuses_json

router = APIRouter(prefix="/campuses", tags=["Campuses"])


@router.get("/", response_model=list[CampusResponse])
async def list_campuses(db: AsyncSession = Depends(get_db)):
    allowed = {row["id"] for row in load_campuses_json()}
    r = await db.execute(
        select(Campus)
        .where(Campus.id.in_(allowed))
        .order_by(Campus.name)
    )
    return r.scalars().all()


@router.get("/catalog")
async def campuses_catalog():
    """Lista de sedes desde campuses.json (referencia para editar coordenadas)."""
    return load_campuses_json()


@router.patch("/{campus_id}", response_model=CampusResponse)
async def update_campus(
    campus_id: int,
    data: CampusUpdate,
    db: AsyncSession = Depends(get_db),
):
    campus = await db.get(Campus, campus_id)
    if not campus:
        raise HTTPException(404, "Sede no encontrada")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campus, field, value)
    await db.commit()
    await db.refresh(campus)
    return campus


@router.post("/sync-coordinates")
async def sync_coordinates(db: AsyncSession = Depends(get_db)):
    """
    Sincroniza las 6 facultades oficiales desde backend/data/campuses.json.
    Elimina sedes que ya no están en el catálogo.
    """
    result = await reconcile_faculties(db)
    return {
        "updated": result["faculties"],
        "edges": result["edges"],
        "message": f"{result['faculties']} facultad(es) activas, {result['edges']} aristas en el grafo",
    }


@router.post("/", response_model=CampusResponse, status_code=201)
async def create_campus(data: CampusCreate, db: AsyncSession = Depends(get_db)):
    c = Campus(**data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c
