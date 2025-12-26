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

@app.get("/static/routes")
async def get_static_routes():
    conn = await get_db_connection()
    try:
        # Groups shapes by route so we get one line per route
        query = """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(sg.geom)::json,
                        'properties', json_build_object(
                            'route_id', r.route_id,
                            'route_name', r.route_short_name,
                            'route_color', r.route_color,
                            'route_text_color', r.route_text_color
                        )
                    )
                ), '[]'::json)
            )
            FROM shape_geoms sg
            JOIN trips t ON sg.shape_id = t.shape_id
            JOIN routes r ON t.route_id = r.route_id
            GROUP BY r.route_id, r.route_short_name, r.route_color, r.route_text_color, sg.geom;
        """
        geojson = await conn.fetchval(query)
        return Response(content=geojson, media_type="application/json")
    finally:
        await conn.close()

# 2. OPTIMIZED: Get ONLY the dots (Fast!)
@app.get("/live/buses")
async def get_live_buses():
    conn = await get_db_connection()
    try:
        query = """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(geom)::json,
                        'properties', json_build_object(
                            'vehicle_id', vehicle_id,
                            'route_id', route_id,
                            'speed', speed,
                            'bearing', bearing 
                        )
                    )
                ), '[]'::json)
            )
            FROM (
                SELECT DISTINCT ON (vehicle_id) *
                FROM live_vehicle_positions
                ORDER BY vehicle_id, timestamp DESC
            ) t;
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
