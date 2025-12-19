# TransitMind: Hamilton 🚍

**A Diagnostic Digital Twin for Public Transit**

TransitMind is a real-time intelligence engine that correlates transit delays with city infrastructure constraints. Unlike standard apps that only show _that_ a bus is late, TransitMind attempts to determine **why** by analyzing the bus's spatial relationship with active construction permits, road closures, and utility work.

![Status](<https://img.shields.io/badge/Status-Phase%202%20(Integration)-blue>)
![Stack](https://img.shields.io/badge/Stack-PostGIS%20%7C%20FastAPI%20%7C%20React-green)

## 🏗 System Architecture

The system operates on a **Hybrid Pipeline** merging three distinct data layers:

1.  **Context Layer (Dynamic):** Ingests live city infrastructure data (Road Closures, Capital Projects) using an ELT pattern to identify "Friction Zones."
2.  **Foundation Layer (Static):** Maps the physical graph of the HSR transit network using GTFS Static data.
3.  **Pulse Layer (Real-Time):** _(In Progress)_ High-frequency ingestion of GTFS-Realtime telemetry to detect live schedule deviations.

> See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed engineering design and decision logs.

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 14+ with **PostGIS** extension installed.

### Installation

1.  **Clone the repository**

    ```bash
    git clone [https://github.com/360NK/transit-mind-hamilton.git](https://github.com/360NK/transit-mind-hamilton.git)
    cd transit-mind-hamilton
    ```

2.  **Set up the Environment**
    Create a `.env` file in the root directory with your credentials:

    ```env
    DB_NAME=transit_mind
    DB_USER=postgres
    DB_PASSWORD=your_password
    DB_HOST=localhost
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

### Usage

**1. Ingest City Infrastructure (The "Friction" Layer)**
Run the ELT script to fetch active permits from the City of Hamilton ArcGIS servers:

```
python ingest_permits.py
```

This populates the live_permits table and updates the disruption views.

**2. (Coming Soon) Start the Real-Time Engine**

```
python ingest_realtime.py
```

### 📂 Data Sources & Licensing

Code: MIT License. See LICENSE for details.

Transit Data: Hamilton Street Railway (HSR) Open Data.

Infrastructure Data: City of Hamilton Open Data (ArcGIS).

Contains information licensed under the Open Government Licence – Hamilton.

---

### What's Next? (According to Plan)
