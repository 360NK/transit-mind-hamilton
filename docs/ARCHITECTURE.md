# TransitMind: Master System Design Document

**Version:** 2.0 (Reactive Diagnostics Era)  
**Location:** Hamilton, ON  
**Status:** Phase 1 & 2 Complete. Phase 3 In Progress.

## 1. System Overview

TransitMind is a **Diagnostic Digital Twin** for Hamilton’s public transit. [cite_start]Unlike standard apps that only show _that_ a bus is late, TransitMind determines **why** it is late by correlating real-time vehicle positions with city infrastructure data (permits, closures, construction)[cite: 1, 6].

## 2. The Core Engine Architecture

[cite_start]The system utilizes a Hybrid Pipeline that merges static schedules, dynamic city infrastructure, and real-time telemetry[cite: 1].

### A. The Context Layer (City Infrastructure) - COMPLETE

- [cite_start]**Source:** City of Hamilton ArcGIS FeatureServers (7 Layers)[cite: 1, 7].
- [cite_start]**Ingestion Pattern:** ELT (Extract-Load-Transform)[cite: 2].
- [cite_start]**Storage:** Raw JSON blobs are loaded directly into the `live_permits` table[cite: 2, 3, 11].
- [cite_start]**Standardization:** SQL Views parse this JSON on-the-fly to create standardized layers[cite: 3, 7].

**Key Data Models:**

- [cite_start]`live_permits` (Table): Stores geometry, time windows, and raw metadata[cite: 12, 13, 14].
- [cite_start]`vw_road_closures` (View): Identifies "Hard Blocks" where Cost = Infinity[cite: 9, 10].
- [cite_start]`vw_utility_permits` (View): Identifies "Friction/Slow Zones"[cite: 8, 9].
- [cite_start]`vw_capital_projects` (View): Strategic long-term schedule buffers[cite: 7, 8].

### B. The Foundation Layer (Static Network) - COMPLETE

- [cite_start]**Source:** HSR `google_transit.zip` (GTFS Static)[cite: 3].
- [cite_start]**Ingestion Pattern:** ETL (Extract-Transform-Load)[cite: 4].
- [cite_start]**Frequency:** Low (Static Schedule)[cite: 4].

**Key Data Models:**

- [cite_start]`routes`: Definitions of bus lines (e.g., "10 B-LINE")[cite: 24, 25, 26].
- [cite_start]`shape_geoms`: The physical polylines defining the path of the bus[cite: 35, 36, 37].
- [cite_start]`stops`: Physical locations of transit points[cite: 29, 30].
- [cite_start]`trips`: Unique identifiers for every scheduled run[cite: 40, 41].

### C. The Pulse Layer (Real-Time Telemetry) - NEXT STEP

- **Source:** HSR GTFS-Realtime Feed (VehiclePositions.pb).
- **Ingestion Pattern:** High-Frequency Polling (Every 15-30s).
- **Tech Stack:** Python (Protobuf decoder) -> PostGIS.
- **Target Storage:** `live_vehicle_positions` (Hypertable) storing `vehicle_id`, `trip_id`, `geom`, and `delay_seconds`.

## 3. The Intelligence Engine (The "Mind")

### A. The Intersection Engine

- [cite_start]**The "Magic Query":** Uses `ST_DWithin` with a 15-meter buffer to detect spatial overlaps between `shape_geoms` (bus paths) and `vw_all_disruptions` (permits)[cite: 45, 46, 47].
- [cite_start]**Optimization:** \* **Current:** Standard SQL View `vw_all_disruptions`[cite: 43, 44].
  - **Planned:** Materialized View refreshing every 60s to reduce calculation load on the "Magic Query."

### B. The Causality Logic (Phase 3)

1.  **Identify:** Bus X is delayed > 5 mins (detected via GTFS-RT).
2.  [cite_start]**Scan:** Is Bus X currently inside or approaching a `vw_road_closure` or `vw_utility_permit` polygon?[cite: 46].
3.  [cite_start]**Attribute:** If YES, flag the delay with the Permit ID and Description (e.g., "Delayed by Watermain Repair")[cite: 47].

## 4. Visualization & Frontend

- **Framework:** React + FastAPI + Deck.gl (for high-performance WebGL rendering).
- **Visual Layers:**
  - **Base Map:** Dark mode (Mapbox/MapLibre).
  - **Context Layer:** `live_permits` rendered as semi-transparent polygons (Red = Closure, Orange = Friction).
  - **Diagnostic Overlay:** Heatmaps showing areas of high "Friction" (clusters of delays + active permits).

## 5. Deviation & Decision Log (ADR)

| ID          | Date       | Status   | Decision                          | Reason                                                                                                                                        |
| :---------- | :--------- | :------- | :-------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| **ADR-001** | 2025-12-01 | Accepted | Use ELT for City Data             | ArcGIS schemas change too often. Storing raw JSON allows us to fix parsers without re-downloading data.                                       |
| **ADR-002** | 2025-12-15 | Accepted | 15m Spatial Buffer                | Roads have width. A simple line intersection misses permits on the curb or adjacent lane.                                                     |
| **ADR-003** | 2025-12-19 | Proposed | Materialized Views                | Running `ST_DWithin` on 200 buses vs 100 permits every second is too slow. Caching for 60s is acceptable.                                     |
| **ADR-004** | 2025-12-19 | Proposed | Use ST_DWithin over ST_Intersects | ST_DWithin uses spatial indexes more efficiently for "Radius Searches" and handles the "Line vs. Point" issue better than hard intersections. |
