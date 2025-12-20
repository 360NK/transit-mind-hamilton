import time
import requests
import psycopg2
import datetime
import os
from google.transit import gtfs_realtime_pb2
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

FEED_URL = "https://opendata.hamilton.ca/GTFS-RT/GTFS_VehiclePositions.pb"
print(f"🔌 TARGET DATABASE: {os.getenv('DB_NAME')}")

DB_PARAMS = {
    "dbname": "transit_mind",
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    try:
        return psycopg2.connect(**DB_PARAMS)
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None
    
def initialize_schema(conn):
    """
    Creates the hypertable for storing millions of vehicle pings.
    """
    cur = conn.cursor()
    print("🔨 Verifying Real-Time Schema...")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS live_vehicle_positions (
            id BIGSERIAL PRIMARY KEY,
            vehicle_id VARCHAR(50),
            trip_id VARCHAR(100),
            route_id VARCHAR(50),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            bearing DOUBLE PRECISION,
            speed DOUBLE PRECISION,
            timestamp TIMESTAMPTZ,
            geom GEOMETRY(POINT, 4326)
        );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_pos_time ON live_vehicle_positions(timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_pos_geom ON live_vehicle_positions USING GIST(geom);")

    conn.commit()
    print("✅ Real-Time Schema Ready.")

def fetch_and_process(conn):
    print(f"📡 Fetching live data...")
    try:
        response = requests.get(FEED_URL)
        if response.status_code != 200:
            print(f"❌ Failed to fetch feed: HTTP {response.status_code}")
            return
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        cur = conn.cursor()
        count = 0

        insert_query = """
            INSERT INTO live_vehicle_positions 
            (vehicle_id, trip_id, route_id, latitude, longitude, bearing, speed, timestamp, geom)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
        """

        for entity in feed.entity:
            if entity.HasField('vehicle'):
                v = entity.vehicle

                veh_id = v.vehicle.id
                trip_id = v.trip.trip_id if v.HasField('trip') else None
                route_id = v.trip.route_id if v.HasField('trip') else None
                
                if not v.HasField('position'):
                    continue
                    
                lat = v.position.latitude
                lon = v.position.longitude
                bearing = v.position.bearing
                speed = v.position.speed

                ts = datetime.datetime.fromtimestamp(v.timestamp)

                cur.execute(insert_query, (
                    veh_id, trip_id, route_id, lat, lon, bearing, speed, ts, lon, lat
                ))
                count += 1

        conn.commit()
        cur.close()
        print(f"✅ Inserted {count} vehicle positions at {datetime.datetime.now().strftime('%H:%M:%S')}")
              
    except Exception as e:
        print(f"❌ Error processing feed: {e}")
        conn.rollback()

if __name__ == "__main__":
    print("🚌 Starting TransitMind Pulse Engine...")
    print("Press Ctrl+C to stop.")
    
    # 1. Connect & Init
    conn = get_db_connection()
    if conn:
        initialize_schema(conn)
        conn.close() # Close init connection

    # 2. Start Loop
    try:
        while True:
            # Re-connect every loop to handle timeouts gracefully
            loop_conn = get_db_connection()
            if loop_conn:
                fetch_and_process(loop_conn)
                loop_conn.close()
            
            # HSR updates every ~30 seconds
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n🛑 Ingestion stopped by user.")