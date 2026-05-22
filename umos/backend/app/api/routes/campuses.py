from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.campus import Campus
from app.schemas.campus import CampusResponse, CampusCreate

router = APIRouter(prefix="/campuses", tags=["Campuses"])


@router.get("/", response_model=list[CampusResponse])
async def list_campuses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campus))
    return result.scalars().all()


@router.get("/{campus_id}", response_model=CampusResponse)
async def get_campus(campus_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campus).where(Campus.id == campus_id))
    campus = result.scalar_one_or_none()
    if not campus:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Campus no encontrado")
    return campus


@router.post("/", response_model=CampusResponse, status_code=201)
async def create_campus(data: CampusCreate, db: AsyncSession = Depends(get_db)):
    campus = Campus(**data.model_dump())
    db.add(campus)
    await db.commit()
    await db.refresh(campus)
    return campus