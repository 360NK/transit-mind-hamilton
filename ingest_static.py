import os
import requests
import zipfile
import io
import csv
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# HSR Static GTFS URL
GTFS_URL = "https://opendata.hamilton.ca/GTFS-Static/google_transit.zip"

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    return psycopg2.connect(**DB_PARAMS)

def init_static_schema(cur):
    print("🔨 Creating Static Tables...")
    
    # 1. Routes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            route_id VARCHAR(50) PRIMARY KEY,
            agency_id VARCHAR(50),
            route_short_name VARCHAR(50),
            route_long_name VARCHAR(255),
            route_desc TEXT,
            route_type INTEGER,
            route_url VARCHAR(255),
            route_color VARCHAR(20),
            route_text_color VARCHAR(20)
        );
    """)

    # 2. Stops
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stops (
            stop_id VARCHAR(50) PRIMARY KEY,
            stop_code VARCHAR(50),
            stop_name VARCHAR(255),
            stop_desc VARCHAR(255),
            stop_lat DOUBLE PRECISION,
            stop_lon DOUBLE PRECISION,
            zone_id VARCHAR(50),
            stop_url VARCHAR(255),
            location_type INTEGER,
            parent_station VARCHAR(50),
            geom GEOMETRY(Point, 4326)
        );
    """)

    # 3. Trips
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            route_id VARCHAR(50),
            service_id VARCHAR(50),
            trip_id VARCHAR(50) PRIMARY KEY,
            trip_headsign VARCHAR(255),
            trip_short_name VARCHAR(50),
            direction_id INTEGER,
            block_id VARCHAR(50),
            shape_id VARCHAR(50),
            wheelchair_accessible INTEGER,
            bikes_allowed INTEGER
        );
    """)

    # 4. Shapes (Raw Points)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shapes (
            shape_id VARCHAR(50),
            shape_pt_lat DOUBLE PRECISION,
            shape_pt_lon DOUBLE PRECISION,
            shape_pt_sequence INTEGER,
            shape_dist_traveled DOUBLE PRECISION
        );
    """)

    # 5. Shape Geoms (The Polylines used for the "Magic Query")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shape_geoms (
            shape_id VARCHAR(50) PRIMARY KEY,
            geom GEOMETRY(LineString, 4326)
        );
    """)
    
    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stops_geom ON stops USING GIST(geom);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shape_geoms ON shape_geoms USING GIST(geom);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shapes_id ON shapes(shape_id);")

def import_csv_to_table(cur, zip_file, filename, table_name, columns):
    """Generic CSV loader"""
    print(f"📥 Loading {table_name}...")
    if filename not in zip_file.namelist():
        print(f"⚠️  {filename} not found in zip. Skipping.")
        return

    with zip_file.open(filename) as f:
        # Decode bytes to string
        content = io.TextIOWrapper(f, encoding='utf-8-sig')
        reader = csv.DictReader(content)
        
        # Prepare SQL
        placeholders = ",".join(["%s"] * len(columns))
        col_names = ",".join(columns)
        sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        
        count = 0
        for row in reader:
            # Extract values in order
            values = [row.get(c, None) for c in columns]
            cur.execute(sql, values)
            count += 1
            if count % 10000 == 0:
                print(f"   - Processed {count} rows...")
        
    print(f"✅ {table_name} complete ({count} rows).")

def generate_geometries(cur):
    print("🌍 Generating Spatial Geometries...")
    
    # 1. Update Stops Geometry
    cur.execute("""
        UPDATE stops 
        SET geom = ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326)
        WHERE geom IS NULL;
    """)
    print("   - Stops geometry updated.")

    # 2. Build Shape Polylines (Heavy Query)
    print("   - Building Shape Polylines (This might take a moment)...")
    cur.execute("TRUNCATE TABLE shape_geoms;") # Clear old data
    cur.execute("""
        INSERT INTO shape_geoms (shape_id, geom)
        SELECT 
            shape_id, 
            ST_SetSRID(ST_MakeLine(ST_MakePoint(shape_pt_lon, shape_pt_lat) ORDER BY shape_pt_sequence), 4326)
        FROM shapes
        GROUP BY shape_id;
    """)
    print("   - Shape Polylines created.")

def ingest_static():
    print(f"⬇️  Downloading GTFS Static from {GTFS_URL}...")
    resp = requests.get(GTFS_URL)
    if resp.status_code != 200:
        print("❌ Failed to download file.")
        return

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Init Schema
        init_static_schema(cur)
        conn.commit()

        # 2. Import Data (Order matters for foreign keys usually, but we are lenient here)
        import_csv_to_table(cur, z, 'routes.txt', 'routes', 
            ['route_id', 'route_short_name', 'route_long_name', 'route_type', 'route_color', 'route_text_color'])
        
        import_csv_to_table(cur, z, 'stops.txt', 'stops', 
            ['stop_id', 'stop_code', 'stop_name', 'stop_lat', 'stop_lon'])
            
        import_csv_to_table(cur, z, 'trips.txt', 'trips', 
            ['route_id', 'service_id', 'trip_id', 'trip_headsign', 'shape_id', 'direction_id'])
            
        import_csv_to_table(cur, z, 'shapes.txt', 'shapes', 
            ['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence'])

        conn.commit()
        
        # 3. Post-Process Geometries
        generate_geometries(cur)
        
        conn.commit()
        cur.close()
        conn.close()
        print("🎉 Static GTFS Ingestion Complete!")

if __name__ == "__main__":
    ingest_static()