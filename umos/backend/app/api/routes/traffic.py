from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.traffic_event import TrafficEvent
from app.schemas.traffic_event import TrafficEventCreate, TrafficEventResponse
from app.services.traffic_service import EVENT_META, SEVERITY_FACTOR, get_traffic_summary
from app.services.data_integration import set_simulation_mode

router = APIRouter(prefix="/traffic", tags=["Traffic"])

@router.get("/events", response_model=list[TrafficEventResponse])
async def list_events(db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(TrafficEvent).where(TrafficEvent.active == True)
        .order_by(TrafficEvent.created_at.desc())
    )
    return r.scalars().all()

@router.post("/events", response_model=TrafficEventResponse, status_code=201)
async def create_event(data: TrafficEventCreate, db: AsyncSession = Depends(get_db)):
    ev = TrafficEvent(
        **data.model_dump(),
        delay_factor=SEVERITY_FACTOR.get(data.severity, 1.5),
    )
    db.add(ev); await db.commit(); await db.refresh(ev); return ev

@router.patch("/events/{eid}/resolve", response_model=TrafficEventResponse)
async def resolve(eid: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(TrafficEvent).where(TrafficEvent.id == eid))
    ev = r.scalar_one_or_none()
    if not ev: raise HTTPException(404, "Evento no encontrado")
    ev.active = False; await db.commit(); await db.refresh(ev); return ev

@router.get("/event-types")
async def event_types():
    return [{"type": k, **v} for k, v in EVENT_META.items()]


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_db)):
    return await get_traffic_summary(db)


@router.post("/simulations/{scenario}", response_model=list[TrafficEventResponse])
async def simulate(scenario: str, db: AsyncSession = Depends(get_db)):
    set_simulation_mode(scenario)
    presets = {
        "peak": [
            ("CONGESTION", "HIGH", 4.6310, -74.0660, 750, "Hora pico en Universidades y Carrera 10"),
            ("CONGESTION", "MEDIUM", 4.6048, -74.0712, 550, "Carga alta alrededor de Macarena"),
            ("CONGESTION", "MEDIUM", 4.5590, -74.1510, 900, "Demoras en Portal Sur"),
        ],
        "rain": [
            ("RAIN", "HIGH", 4.6310, -74.0660, 1200, "Lluvia intensa: cambio modal y filas"),
            ("CONGESTION", "HIGH", 4.6200, -74.0580, 850, "Congestion por lluvia en Chapinero"),
            ("CONGESTION", "MEDIUM", 4.5469, -74.1323, 900, "Acceso lento a Sede Tecnologica"),
        ],
        "incident": [
            ("ACCIDENT", "CRITICAL", 4.6060, -74.0820, 900, "Incidente sobre corredor centro-sur"),
            ("ROAD_CLOSED", "HIGH", 4.6341, -74.0637, 450, "Cierre parcial cerca de Sabio Caldas"),
        ],
    }

    if scenario == "clear":
        active = await db.execute(select(TrafficEvent).where(TrafficEvent.active == True))
        for ev in active.scalars().all():
            ev.active = False
        await db.commit()
        return []

    if scenario not in presets:
        raise HTTPException(400, "Escenario no soportado")

    created = []
    for event_type, severity, lat, lon, radius, description in presets[scenario]:
        ev = TrafficEvent(
            event_type=event_type,
            severity=severity,
            latitude=lat,
            longitude=lon,
            radius_m=radius,
            description=description,
            delay_factor=SEVERITY_FACTOR.get(severity, 1.5),
        )
        db.add(ev)
        created.append(ev)

    await db.commit()
    for ev in created:
        await db.refresh(ev)
    return created
