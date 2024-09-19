import asyncio

from pydantic import BaseModel
from app.datastore import ds
from fastapi import APIRouter
# from app.routers.on_server_navigation.default_paths import paths, paths_json
from app.routers.on_server_navigation.create_path import CreatePath
import rasterio
import uuid
import geojson
from geojson import Point, LineString
from app.event import Event

geojson.geometry.DEFAULT_PRECISION = 8
dataset = rasterio.open("/code/app/routers/rockyard_map_geo.tif")
router = APIRouter(prefix="/navigation", tags=["navigation"])
pins_key = "pins"
paths_key = "paths"
in_mem_pins: dict[str,any] = {}
in_mem_paths: dict[str, list[str]] = {}

@router.get("/" + pins_key)
async def pins():
    return {pins_key: in_mem_pins}

@router.get("/" + paths_key)
async def paths():
    return {paths_key: in_mem_paths}

class PointBody(BaseModel):
    x: int | None = None
    y: int | None = None
    lat: float | None = None
    lon: float | None = None
    properties: dict = {}

async def add_pin(point: Point):
    _id = point.properties["id"]
    in_mem_pins[_id] = point # add pin to in mem pins
    pin_event = Event.create_event(pins_key, point, upsert_key=_id)
    await ds.add_event(pins_key, pin_event) # add event to datastore

def create_point(point: PointBody):
    x, y, lon, lat, properties = (point.x, point.y, point.lon, point.lat, point.properties)
    # do not use "falsy" values (e.g. 0 is evaluated as false)
    if x != None and y != None:
        lon, lat = dataset.xy(x, y) # convert pixel to lat/lon
    elif lat != None and lon != None:
        y, x = ~dataset.transform * (lon, lat) # convert lat/lon to pixel
    else:
        return False
    properties["id"] = str(uuid.uuid4()) if "id" not in properties else properties["id"]
    properties["x"] = int(x)
    properties["y"] = int(y)
    return Point((lon, lat), properties=properties)

@router.post("/" + pins_key)
async def translate(point: PointBody):
    created = create_point(point)
    if not created:
        return {"message":"Not able to parse pin coordinates!"}
    await add_pin(created)
    return {"message": "Successfully created pin."}

class PathBody(BaseModel):
    pins: list[str]
    properties: dict = {}

async def add_path(path: CreatePath):
    _id = path.properties["id"]
    in_mem_paths[_id] = path # add path to in mem paths
    path_event = Event.create_event(paths_key, path, upsert_key=_id)
    await ds.add_event(paths_key, path_event) # add event to datastore

def create_path(path: PathBody):
    properties = path.properties
    properties["pin_ids"] = []
    points = []
    for _id in path.pins:
        if _id not in in_mem_pins:
            return _id # validate if point exists
        else:
            point = in_mem_pins[_id]
            points.append(point.coordinates)
            properties["pin_ids"].append(point.properties["id"])
    properties["id"] = str(uuid.uuid4()) if "id" not in properties else properties["id"]
    return LineString(points, properties=properties)

@router.post("/" + paths_key)
async def post_path(path: PathBody):
    created = create_path(path)
    if not isinstance(created, LineString):
        return {"message": f"Not able to create path, pin id does not exist!: {created}"}
    await add_path(created)
    return {"message": "Successfully created path."}