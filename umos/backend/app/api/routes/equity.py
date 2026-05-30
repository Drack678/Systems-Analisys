from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.campus import Campus
from app.services.equity_service import (
    EQUITY_GAP_BASELINE,
    detect_zone,
    equity_comparison,
)

router = APIRouter(prefix="/equity", tags=["Equity"])


@router.get("/metrics")
async def equity_metrics(db: AsyncSession = Depends(get_db)):
    campuses = (await db.execute(select(Campus))).scalars().all()
    by_zone: dict[str, list] = {"Norte": [], "Sur": [], "Este": [], "Centro": []}
    for c in campuses:
        by_zone[detect_zone(c)].append(c.name)

    comparison = equity_comparison("Sur")
    return {
        "equity_gap_percent": round(EQUITY_GAP_BASELINE * 100, 1),
        "north_avg_time_min": comparison["north_avg_time_min"],
        "south_avg_time_min": comparison["south_avg_time_min"],
        "north_avg_cost_per_km": 120,
        "south_avg_cost_per_km": 410,
        "cost_multiplier": 3.4,
        "zones": {z: len(names) for z, names in by_zone.items()},
        "campuses_by_zone": by_zone,
        "disparity_message": (
            "Southern zone students face 38.5% longer travel times "
            "and 3.4× higher cost-per-km vs northern zones."
        ),
    }


@router.get("/zone/{campus_id}")
async def campus_zone(campus_id: int, db: AsyncSession = Depends(get_db)):
    campus = await db.get(Campus, campus_id)
    if not campus:
        return {"error": "Campus not found"}
    zone = detect_zone(campus)
    return {"campus_id": campus_id, "zone": zone, **equity_comparison(zone)}
