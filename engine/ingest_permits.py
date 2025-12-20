import requests
import psycopg2
from psycopg2.extras import Json
import datetime
import json
import os
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

# --- 1. CONFIGURATION ---
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432")
}

URLS = {
    "Film": "https://services1.arcgis.com/DkpbFZAaJs7sZX2x/arcgis/rest/services/Active_Film_Permits/FeatureServer/0/query?where=1%3D1&outFields=*&f=json",
    "Occupancy": "https://services1.arcgis.com/DkpbFZAaJs7sZX2x/arcgis/rest/services/Active_Temporary_Lane_and_Sidewalk_Occupancy_Permits/FeatureServer/0/query?where=1%3D1&outFields=*&f=json",
    "Closures": "https://services1.arcgis.com/DkpbFZAaJs7sZX2x/arcgis/rest/services/Active_Temporary_Full_Road_Closure_Permit/FeatureServer/0/query?where=1%3D1&outFields=*&f=json",
    "SuperLoad": "https://services1.arcgis.com/DkpbFZAaJs7sZX2x/arcgis/rest/services/Active_SuperLoad_Truck_Permits/FeatureServer/0/query?where=1%3D1&outFields=*&f=json",
    "Truck": "https://services1.arcgis.com/DkpbFZAaJs7sZX2x/arcgis/rest/services/Active_Overload_Truck_Permits/FeatureServer/0/query?where=1%3D1&outFields=*&f=json",
    "Utility_Consent": "https://services1.arcgis.com/DkpbFZAaJs7sZX2x/arcgis/rest/services/Active_Municipal_Consents_Utility_Permits/FeatureServer/0/query?where=1%3D1&outFields=*&f=json",
    "Capital_Projects": "https://services1.arcgis.com/DkpbFZAaJs7sZX2x/arcgis/rest/services/CP_List_of_Geomatics_Capital_Projects/FeatureServer/0/query?where=1%3D1&outFields=*&f=json"
}

def get_db_connection():
    try:
        return psycopg2.connect(**DB_PARAMS)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def initialize_schema(conn):
    """
    Idempotent Schema Initialization.
    Recreates the exact table structure and Views from your Architecture Doc.
    """
    cur = conn.cursor()
    print("🔨 Verifying Schema...")

    # 1. Create the Main Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS live_permits (
            id SERIAL PRIMARY KEY,
            permit_id VARCHAR(100) UNIQUE,
            source_layer VARCHAR(50),
            hazard_type VARCHAR(50),
            description TEXT,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            metadata JSONB,
            geom GEOMETRY(Geometry, 4326)
        );
    """)

    # 2. Create Indices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_live_permits_geom ON live_permits USING GIST(geom);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_live_permits_time ON live_permits (start_time, end_time);")

    # 3. Create Views (Based on your schema_dump.sql)
    print("   - Updating Views...")
    
    # Capital Projects View
    cur.execute("""
        CREATE OR REPLACE VIEW vw_capital_projects AS
        SELECT 
            ((metadata -> 'original_fields') ->> 'globalid')::uuid AS id,
            ((metadata -> 'original_fields') ->> 'Project_Name') AS project_name,
            ((metadata -> 'original_fields') ->> 'Status') AS status,
            to_timestamp((((metadata -> 'original_fields') ->> 'Date_Submitted')::bigint / 1000.0)) AS date_submitted,
            to_timestamp((((metadata -> 'original_fields') ->> 'Date_Requested_Completion')::bigint / 1000.0)) AS estimated_completion,
            geom
        FROM live_permits
        WHERE source_layer = 'Capital_Projects';
    """)

    # Utility Permits View
    cur.execute("""
        CREATE OR REPLACE VIEW vw_utility_permits AS
        SELECT 
            ((metadata -> 'original_fields') ->> 'GlobalID')::uuid AS id,
            ((metadata -> 'original_fields') ->> 'Utility_Company_Name') AS company_name,
            ((metadata -> 'original_fields') ->> 'Status') AS status,
            ((metadata -> 'original_fields') ->> 'Stream_Class') AS impact_level,
            geom
        FROM live_permits
        WHERE source_layer = 'Utility_Consent';
    """)

    # Road Closures View
    cur.execute("""
        CREATE OR REPLACE VIEW vw_road_closures AS
        SELECT 
            ((metadata -> 'original_fields') ->> 'globalid')::uuid AS id,
            ((metadata -> 'original_fields') ->> 'closure_to_what_street_name') AS road_name,
            ((metadata -> 'original_fields') ->> 'Description') AS description,
            ((metadata -> 'original_fields') ->> 'Close_Both_Traffic_Directions') AS closure_type,
            geom
        FROM live_permits
        WHERE source_layer = 'Closures';
    """)
    
    # Occupancy View
    cur.execute("""
        CREATE OR REPLACE VIEW vw_occupancy_permits AS
        SELECT 
            ((metadata -> 'original_fields') ->> 'globalid')::uuid AS id,
            ((metadata -> 'original_fields') ->> 'Item_for_Occupancy') AS obstruction_type,
            ((metadata -> 'original_fields') ->> 'Location') AS address,
            geom
        FROM live_permits
        WHERE source_layer = 'Occupancy';
    """)

    # Master View (vw_all_disruptions)
    cur.execute("""
        CREATE OR REPLACE VIEW vw_all_disruptions AS
        SELECT id, 'CLOSURE' AS disruption_type, description, geom FROM vw_road_closures
        UNION ALL
        SELECT id, 'CONSTRUCTION' AS disruption_type, project_name AS description, geom FROM vw_capital_projects
        UNION ALL
        SELECT id, 'UTILITY_WORK' AS disruption_type, company_name AS description, geom FROM vw_utility_permits
        UNION ALL
        SELECT id, 'OCCUPANCY' AS disruption_type, obstruction_type AS description, geom FROM vw_occupancy_permits;
    """)

    conn.commit()
    print("✅ Schema verification complete.")

def clean_time(epoch_ms):
    if not epoch_ms: return None
    return datetime.datetime.fromtimestamp(epoch_ms / 1000.0)

def esri_to_geojson(esri_geom):
    if not esri_geom: return None
    if 'x' in esri_geom and 'y' in esri_geom:
        return {"type": "Point", "coordinates": [esri_geom['x'], esri_geom['y']]}
    if 'paths' in esri_geom:
        return {"type": "MultiLineString", "coordinates": esri_geom['paths']}
    if 'rings' in esri_geom:
        return {"type": "Polygon", "coordinates": esri_geom['rings']}
    return None

def normalize_data(source, feature):
    props = feature.get("attributes", {})
    raw_geom = feature.get("geometry", {})
    geom = esri_to_geojson(raw_geom)
    
    permit_id = props.get("GlobalID") or props.get("Permit_Number") or props.get("OBJECTID") or props.get("objectid")
    hazard_type = props.get("Item_for_Occupancy") or props.get("ACTIVITY_TYPE") or source
    description = props.get("Location") or props.get("Description_Route") or props.get("Description_of_Load")
    
    start_time = clean_time(props.get("Start_Date_of_Occupancy") or props.get("Start_Date") or props.get("Start_Date_of_Move"))
    end_time = clean_time(props.get("End_Date_of_Occupancy") or props.get("End_Date") or props.get("End_Date_of_Move"))

    metadata = {
        "status": props.get("Status"),
        "width": props.get("Load_Width_m"),
        "company": props.get("Company_Name") or props.get("Utility_Company_Name"),
        "original_fields": props
    }

    return (str(permit_id), source, hazard_type, description, start_time, end_time, Json(metadata), geom)

def ingest_layers():
    conn = get_db_connection()
    if not conn: return
    
    # 1. INITIALIZE SCHEMA FIRST
    initialize_schema(conn)

    cur = conn.cursor()
    if not URLS:
        print("WARNING: URLS list is empty!")
        return

    for source_name, url in URLS.items():
        print(f"Fetching {source_name}...")
        try:
            resp = requests.get(url)
            if resp.status_code != 200: continue
            data = resp.json()
            features = data.get("features", [])
            print(f"  Found {len(features)} permits.")
            
            for feat in features:
                record = normalize_data(source_name, feat)
                if not record[7]: continue

                sql = """
                    INSERT INTO live_permits 
                    (permit_id, source_layer, hazard_type, description, start_time, end_time, metadata, geom)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                    ON CONFLICT (permit_id) DO UPDATE SET
                        metadata = EXCLUDED.metadata,
                        end_time = EXCLUDED.end_time;
                """
                geom_json = json.dumps(record[7])
                try:
                    cur.execute(sql, (record[0], record[1], record[2], record[3], record[4], record[5], record[6], geom_json))
                except Exception as row_error:
                    conn.rollback()
                    continue
            conn.commit()
            print(f"  Successfully ingested {source_name}.")
        except Exception as e:
            conn.rollback()

    cur.close()
    conn.close()

if __name__ == "__main__":
    ingest_layers()