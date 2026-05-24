from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.campus import Campus
from app.schemas.campus import CampusResponse, CampusCreate

router = APIRouter(prefix="/campuses", tags=["Campuses"])

@router.get("/", response_model=list[CampusResponse])
async def list_campuses(db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Campus)
        .where(Campus.code.notin_(["EU", "PS", "MA"]))
        .order_by(Campus.name)
    )
    return r.scalars().all()

@router.post("/", response_model=CampusResponse, status_code=201)
async def create_campus(data: CampusCreate, db: AsyncSession = Depends(get_db)):
    c = Campus(**data.model_dump())
    db.add(c); await db.commit(); await db.refresh(c); return c
