from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api.routes import campuses, routes as route_router, traffic as traffic_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_data()
    yield

app = FastAPI(title="UMOS API v3", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(campuses.router,       prefix="/api/v1")
app.include_router(route_router.router,   prefix="/api/v1")
app.include_router(traffic_router.router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "UMOS v3"}

async def seed_data():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.campus import Campus
    from app.models.route_edge import RouteEdge
    async with AsyncSessionLocal() as db:
        if (await db.execute(select(Campus))).scalars().first():
            return
        campuses_data = [
            {"id":1,"name":"Sede Sabio Caldas","code":"SC","address":"Cra 7 #40B-53","latitude":4.6341,"longitude":-74.0637,"description":"Chapinero"},
            {"id":2,"name":"Sede Tecnológica","code":"ST","address":"Cl 68D Bis A Sur #49F-70","latitude":4.5469,"longitude":-74.1323,"description":"Ciudad Bolívar"},
            {"id":3,"name":"Sede Macarena A","code":"MA","address":"Cra 3 #26A-40","latitude":4.6046,"longitude":-74.0714,"description":"La Candelaria"},
            {"id":4,"name":"Sede Macarena B","code":"MB","address":"Cra 4 #26D-54","latitude":4.6050,"longitude":-74.0710,"description":"La Candelaria"},
            {"id":5,"name":"Sede Vivero","code":"SV","address":"Cra 5 Este #15-82","latitude":4.6070,"longitude":-74.0690,"description":"La Candelaria"},
            {"id":6,"name":"Estación Universidades (TM)","code":"EU","address":"Cra 10 #39-00","latitude":4.6310,"longitude":-74.0660,"description":"TransMilenio"},
            {"id":7,"name":"Portal Sur (TM)","code":"PS","address":"Autopista Sur","latitude":4.5590,"longitude":-74.1510,"description":"TransMilenio"},
        ]
        for d in campuses_data:
            db.add(Campus(**d))
        await db.flush()
        edges_data = [
            (1,6,0.6,8,"WALK"),(6,1,0.6,8,"WALK"),
            (1,3,3.5,22,"SITP"),(3,1,3.5,22,"SITP"),
            (1,5,2.2,14,"BIKE"),(5,1,2.2,14,"BIKE"),
            (3,4,0.3,4,"WALK"),(4,3,0.3,4,"WALK"),
            (3,5,0.5,6,"WALK"),(5,3,0.5,6,"WALK"),
            (4,5,0.4,5,"WALK"),(5,4,0.4,5,"WALK"),
            (6,7,17.0,55,"TM"),(7,6,17.0,55,"TM"),
            (7,2,4.5,25,"CABLE"),(2,7,4.5,25,"CABLE"),
            (1,2,22.0,90,"TM"),(2,1,22.0,90,"TM"),
            (6,3,3.0,18,"SITP"),(3,6,3.0,18,"SITP"),
            (1,4,3.6,24,"SITP"),(4,1,3.6,24,"SITP"),
            (6,5,3.2,20,"SITP"),(5,6,3.2,20,"SITP"),
        ]
        for (o,d,dist,t,tr) in edges_data:
            db.add(RouteEdge(origin_id=o,dest_id=d,distance_km=dist,travel_time=t,transport=tr,pheromone=1.0))
        await db.commit()