import math
import time
from urllib.parse import urlencode

import httpx


ARCGIS_BASE = "https://gis.transmilenio.gov.co/arcgis/rest/services"
STATIONS_URL = f"{ARCGIS_BASE}/Troncal/consulta_estaciones_troncales/MapServer/0/query"
TRUNK_ROUTES_URL = f"{ARCGIS_BASE}/Troncal/consulta_rutas_troncales/MapServer/0/query"


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _arcgis_query(url: str, params: dict) -> dict:
    query = {
        "f": "json",
        "inSR": 4326,
        "outSR": 4326,
        **params,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{url}?{urlencode(query)}")
        response.raise_for_status()
        return response.json()


def _station_from_feature(feature: dict, lat: float, lon: float) -> dict:
    attrs = feature.get("attributes", {})
    geometry = feature.get("geometry") or {}
    station_lat = attrs.get("latitud_estacion") or geometry.get("y")
    station_lon = attrs.get("longitud_estacion") or geometry.get("x")
    return {
        "id": attrs.get("objectid"),
        "name": attrs.get("nombre_estacion") or attrs.get("numero_estacion"),
        "number": attrs.get("numero_estacion"),
        "trunk": attrs.get("troncal_estacion"),
        "address": attrs.get("ubicacion_estacion"),
        "latitude": station_lat,
        "longitude": station_lon,
        "distance_m": round(_haversine(lat, lon, station_lat, station_lon)),
        "bike_parking": attrs.get("biciparqueadero_estacion"),
    }


def _path_from_feature(feature: dict) -> list[list[float]]:
    geometry = feature.get("geometry") or {}
    paths = geometry.get("paths") or []
    if not paths:
        return []
    return [[point[1], point[0]] for point in paths[0] if len(point) >= 2]


def _route_from_feature(feature: dict) -> dict:
    attrs = feature.get("attributes", {})
    name = attrs.get("nombre_ruta_troncal") or attrs.get("route_name_ruta_troncal")
    return {
        "id": attrs.get("objectid"),
        "name": name,
        "route_name": attrs.get("route_name_ruta_troncal"),
        "origin": attrs.get("origen_ruta_troncal"),
        "destination": attrs.get("destino_ruta_troncal"),
        "service": attrs.get("servicio_unico_ruta_troncal"),
        "type": attrs.get("desc_tipo_ruta_troncal"),
        "bus_type": attrs.get("desc_tipo_bus_ruta_troncal"),
        "weekday_schedule": attrs.get("horario_lunes_viernes"),
        "status": attrs.get("estado_ruta_troncal"),
        "geometry": _path_from_feature(feature),
    }


async def nearby_stations(lat: float, lon: float, radius_m: int = 900, limit: int = 8) -> list[dict]:
    data = await _arcgis_query(
        STATIONS_URL,
        {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "distance": radius_m,
            "units": "esriSRUnit_Meter",
            "outFields": "objectid,numero_estacion,nombre_estacion,ubicacion_estacion,troncal_estacion,latitud_estacion,longitud_estacion,biciparqueadero_estacion",
            "returnGeometry": "true",
            "resultRecordCount": limit,
        },
    )
    stations = [
        _station_from_feature(feature, lat, lon)
        for feature in data.get("features", [])
    ]
    return sorted(stations, key=lambda station: station["distance_m"])[:limit]


async def nearby_trunk_routes(lat: float, lon: float, radius_m: int = 1000, limit: int = 8) -> list[dict]:
    data = await _arcgis_query(
        TRUNK_ROUTES_URL,
        {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "distance": radius_m,
            "units": "esriSRUnit_Meter",
            "outFields": "objectid,route_name_ruta_troncal,nombre_ruta_troncal,servicio_unico_ruta_troncal,origen_ruta_troncal,destino_ruta_troncal,desc_tipo_ruta_troncal,desc_tipo_bus_ruta_troncal,horario_lunes_viernes,estado_ruta_troncal",
            "returnGeometry": "true",
            "returnZ": "false",
            "resultRecordCount": limit,
        },
    )
    routes = [_route_from_feature(feature) for feature in data.get("features", [])]
    return [route for route in routes if route["geometry"]][:limit]


def simulated_vehicles(routes: list[dict], per_route: int = 2) -> list[dict]:
    now = time.time()
    vehicles: list[dict] = []
    for route in routes:
        geometry = route.get("geometry") or []
        if len(geometry) < 2:
            continue
        for index in range(per_route):
            offset = (now / 45 + index / per_route) % 1
            position_index = min(int(offset * (len(geometry) - 1)), len(geometry) - 1)
            vehicles.append(
                {
                    "id": f"{route['id']}-{index}",
                    "route": route["name"],
                    "label": f"{route['name']} #{index + 1}",
                    "latitude": geometry[position_index][0],
                    "longitude": geometry[position_index][1],
                    "progress": round(offset, 2),
                }
            )
    return vehicles


async def recommendation_for_trip(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> dict:
    origin_stations = await nearby_stations(origin_lat, origin_lon, 1800, 6)
    dest_stations = await nearby_stations(dest_lat, dest_lon, 3000, 6)

    origin_routes = await nearby_trunk_routes(origin_lat, origin_lon, 1800, 10)
    dest_routes = await nearby_trunk_routes(dest_lat, dest_lon, 3000, 10)
    dest_route_names = {route["name"] for route in dest_routes}
    direct = [route for route in origin_routes if route["name"] in dest_route_names]
    suggested = direct[:4] or origin_routes[:4]

    return {
        "origin_station": origin_stations[0] if origin_stations else None,
        "destination_station": dest_stations[0] if dest_stations else None,
        "origin_nearby_stations": origin_stations,
        "destination_nearby_stations": dest_stations,
        "routes": suggested,
        "direct_match": bool(direct),
        "vehicles": simulated_vehicles(suggested, 2),
        "source": "ArcGIS GeoServices REST API - TransMilenio",
    }
