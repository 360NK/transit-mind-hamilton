import os
import asyncpg
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db_connection():
    return await asyncpg.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432")
    )

@app.get("/busses")
async def get_busses():
    conn = await get_db_connection()
    try:
        # 1. DISTINCT ON (vehicle_id): Removes the "History Trails" (The Snake Effect)
        # 2. JOIN shape_geoms: Gets the "White Line" track for the bus
        query = """
            WITH latest_positions AS (
                SELECT DISTINCT ON (vehicle_id)
                    vp.vehicle_id,
                    vp.route_id,
                    vp.speed,
                    vp.geom,
                    sg.geom as route_line  -- The Route Shape
                FROM live_vehicle_positions vp
                LEFT JOIN trips t ON vp.trip_id = t.trip_id
                LEFT JOIN shape_geoms sg ON t.shape_id = sg.shape_id
                ORDER BY vp.vehicle_id, vp.id DESC -- Only keep the newest ID per bus
            )
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(t.geom)::json, -- The Bus Dot
                        'properties', json_build_object(
                            'vehicle_id', t.vehicle_id,
                            'route_id', t.route_id,
                            'speed', t.speed,
                            'route_geometry', ST_AsGeoJSON(t.route_line)::json -- The Track Line
                        )
                    )
                ), '[]'::json)
            )
            FROM latest_positions t;
        """
        geojson = await conn.fetchval(query)
        return Response(content=geojson, media_type="application/json")
    finally:
        await conn.close()

@app.get("/conflicts")
async def get_conflicts():
    conn = await get_db_connection()
    try:
        query = """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(ST_AsGeoJSON(t.*)::json), '[]'::json)
            ) 
            FROM (
                SELECT permit_id, hazard_type, description, geom 
                FROM live_permits 
                WHERE metadata->>'status' IN ('Active', 'Authorised')
            ) t;
        """
        geojson = await conn.fetchval(query)
        # FIX: Return raw pre-formatted JSON
        return Response(content=geojson, media_type="application/json")
    finally:
        await conn.close()
