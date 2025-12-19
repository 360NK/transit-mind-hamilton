import requests
import psycopg2
from psycopg2.extras import Json
import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

# --- 1. CONFIGURATION ---
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432") # Defaults to 5432 if not set
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
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def clean_time(epoch_ms):
    if not epoch_ms:
        return None
    return datetime.datetime.fromtimestamp(epoch_ms / 1000.0)

def esri_to_geojson(esri_geom):
    """
    The Translator: Converts Esri 'x/y' or 'paths' into standard GeoJSON
    that PostGIS can understand.
    """
    if not esri_geom:
        return None
    
    # CASE 1: It's a Point (Occupancy, Film)
    if 'x' in esri_geom and 'y' in esri_geom:
        return {
            "type": "Point",
            "coordinates": [esri_geom['x'], esri_geom['y']]
        }
    
    # CASE 2: It's a Line (Trucks, Closures)
    if 'paths' in esri_geom:
        return {
            "type": "MultiLineString",
            "coordinates": esri_geom['paths']
        }

    # CASE 3: It's a Polygon (Some Road Closures)
    if 'rings' in esri_geom:
        return {
            "type": "Polygon",
            "coordinates": esri_geom['rings']
        }
        
    return None

def normalize_data(source, feature):
    props = feature.get("attributes", {})
    raw_geom = feature.get("geometry", {})
    
    # 1. Translate Geometry
    geom = esri_to_geojson(raw_geom)

    # 2. Get ID (Added lowercase 'objectid' fix)
    permit_id = props.get("GlobalID") or props.get("Permit_Number") or props.get("OBJECTID") or props.get("objectid")
    
    # 3. Get Hazard Type
    hazard_type = props.get("Item_for_Occupancy") or props.get("ACTIVITY_TYPE") or source
    
    # 4. Get Description
    description = props.get("Location") or props.get("Description_Route") or props.get("Description_of_Load")
    
    # 5. Get Times
    start_time = clean_time(props.get("Start_Date_of_Occupancy") or props.get("Start_Date") or props.get("Start_Date_of_Move"))
    end_time = clean_time(props.get("End_Date_of_Occupancy") or props.get("End_Date") or props.get("End_Date_of_Move"))

    # 6. Metadata
    metadata = {
        "status": props.get("Status"),
        "width": props.get("Load_Width_m"),
        "company": props.get("Company_Name") or props.get("Utility_Company_Name"),
        "original_fields": props
    }

    return (
        str(permit_id),
        source,
        hazard_type,
        description,
        start_time,
        end_time,
        Json(metadata),
        geom 
    )

def ingest_layers():
    conn = get_db_connection()
    if not conn:
        return

    cur = conn.cursor()
    
    if not URLS:
        print("WARNING: URLS list is empty! Please paste your links in the script.")
        return

    for source_name, url in URLS.items():
        print(f"Fetching {source_name}...")
        try:
            resp = requests.get(url)
            if resp.status_code != 200:
                print(f"  Failed to fetch: {resp.status_code}")
                continue
                
            data = resp.json()
            features = data.get("features", [])
            print(f"  Found {len(features)} permits.")
            
            for feat in features:
                record = normalize_data(source_name, feat)
                
                # Check if geometry is valid before inserting
                if not record[7]: 
                    print(f"  Skipping row {record[0]}: No valid geometry found.")
                    continue

                # The Corrected SQL (Updates metadata, not status)
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
                    cur.execute(sql, (
                        record[0], record[1], record[2], record[3], record[4], record[5], record[6], geom_json
                    ))
                except Exception as row_error:
                    print(f"  Skipping row {record[0]}: {row_error}")
                    conn.rollback()
                    continue
                
            conn.commit()
            print(f"  Successfully ingested {source_name}.")
            
        except Exception as e:
            print(f"  Error ingesting {source_name}: {e}")
            conn.rollback()

    cur.close()
    conn.close()

if __name__ == "__main__":
    ingest_layers()