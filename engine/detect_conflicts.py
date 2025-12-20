import psycopg2
import os
import time
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432")
}

def detect_conflicts():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # THE DIAGNOSTIC QUERY
        sql = """
        WITH 
        -- 1. Standardize All Disruptions First
        -- This ensures we always have 'disruption_type', 'end_time', etc.
        active_disruptions AS (
            -- We pull directly from live_permits to bypass the view logic
            SELECT 
                hazard_type as disruption_type, 
                metadata->>'status' as status, 
                description,
                start_time,
                end_time,
                geom 
            FROM live_permits 
            WHERE end_time > NOW()
            
            UNION ALL
            
            -- Keep the original view data too so we don't lose real city data
            SELECT disruption_type, status, description, start_time, end_time, geom 
            FROM vw_all_disruptions 
            WHERE end_time > NOW()
        ),
        
        -- CHECK A: Hard Blocks (Route Severed)
        -- FIXED: Now joins 'active_disruptions' instead of raw 'vw_road_closures'
        check_a_hard_blocks AS (
            SELECT 
                r.route_short_name,
                d.disruption_type,
                d.description,
                'CRITICAL' as severity
            FROM routes r
            JOIN trips t ON r.route_id = t.route_id
            JOIN shape_geoms s ON t.shape_id = s.shape_id
            JOIN active_disruptions d ON ST_Intersects(s.geom, d.geom)
            WHERE TRIM(d.disruption_type) = 'CLOSURE' -- Specific filter for closures
            GROUP BY r.route_short_name, d.disruption_type, d.description
        ),

        -- CHECK B: The "Local Squeeze" (Friction % Calculation)
        -- Logic: If a permit touches the route, how much of the 10m-wide road does it consume?
        check_b_squeeze AS (
            SELECT 
                r.route_short_name,
                d.disruption_type,
                d.description,
                -- THE MATH TRAP FIX:
                -- Denominator is based on the INTERSECTION length, not the ROUTE length.
                CASE 
                    WHEN ST_Length(ST_Intersection(s.geom, d.geom)) < 1 THEN 0 
                    ELSE (
                        ST_Area(ST_Intersection(ST_Buffer(s.geom, 5), d.geom)) -- Area of overlap
                        / 
                        (ST_Length(ST_Intersection(s.geom, d.geom)) * 10) -- Area of ideal road (10m wide)
                    ) * 100
                END as blockage_pct
            FROM routes r
            JOIN trips t ON r.route_id = t.route_id
            JOIN shape_geoms s ON t.shape_id = s.shape_id
            JOIN active_disruptions d ON ST_Intersects(s.geom, d.geom)
            WHERE d.disruption_type != 'CLOSURE' -- Closures are handled in Check A
            GROUP BY r.route_short_name, d.disruption_type, d.description, s.geom, d.geom
        ),

        -- CHECK C: Accessibility (Stop Encapsulation)
        -- Logic: HAMILTON RULE - Only flag if the stop is STRICTLY INSIDE the polygon.
        check_c_stops AS (
            SELECT 
                s.stop_name,
                s.stop_id,
                d.disruption_type,
                d.description
            FROM stops s
            JOIN active_disruptions d 
            -- Uses ST_Intersects for strict containment (Stop must be INSIDE work zone)
            ON ST_Intersects(s.geom, d.geom) 
        ),

        -- CHECK D: Live Confirmation (Real-Time)
        -- Logic: Is a bus currently driving through a permit zone?
        check_d_live AS (
            SELECT DISTINCT ON (vehicle_id)
                vehicle_id,
                route_id,
                d.description,
                speed
            FROM live_vehicle_positions p
            JOIN active_disruptions d ON ST_Intersects(p.geom, d.geom)
            WHERE p.timestamp > NOW() - INTERVAL '2 minutes' -- Only fresh data
            ORDER BY vehicle_id, timestamp DESC
        )

        -- AGGREGATE REPORT
        SELECT 'HARD_BLOCK' as type, route_short_name as id, description, severity::text as metric FROM check_a_hard_blocks
        UNION ALL
        SELECT 'SQUEEZE' as type, route_short_name as id, description, ROUND(blockage_pct)::text || '%' as metric FROM check_b_squeeze WHERE blockage_pct > 15
        UNION ALL
        SELECT 'STOP_CLOSED' as type, stop_name as id, description, 'INACCESSIBLE' as metric FROM check_c_stops
        UNION ALL
        SELECT 'LIVE_IMPACT' as type, vehicle_id as id, description, speed::text || ' km/h' as metric FROM check_d_live;
        """

        cur.execute(sql)
        results = cur.fetchall()

        # --- THE DASHBOARD ---
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"🧠 TRANSITMIND: DIAGNOSTIC ENGINE (HAMILTON CONFIG)")
        print(f"================================================================================")
        print(f"{'TYPE':<15} | {'TARGET':<15} | {'METRIC':<12} | {'CAUSE'}")
        print(f"--------------------------------------------------------------------------------")
        
        if not results:
            print("✅ SYSTEM NOMINAL. No critical conflicts detected.")
        
        for row in results:
            alert_type, target, desc, metric = row
            # Truncate long descriptions
            desc_short = (desc[:40] + '..') if desc and len(desc) > 40 else str(desc)
            
            # Color coding
            color = "\033[97m" # White
            if alert_type == "HARD_BLOCK": color = "\033[91m" # Red
            elif alert_type == "LIVE_IMPACT": color = "\033[93m" # Yellow
            elif alert_type == "STOP_CLOSED": color = "\033[96m" # Cyan
            
            print(f"{color}{alert_type:<15} | {target:<15} | {metric:<12} | {desc_short}\033[0m")

        print(f"================================================================================")
        conn.close()

    except Exception as e:
        print(f"❌ Analysis Error: {e}")

if __name__ == "__main__":
    while True:
        detect_conflicts()
        time.sleep(10) # Run analysis every 10 seconds