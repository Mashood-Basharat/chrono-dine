# ChronoDine: Enterprise Restaurant Intelligence Platform

ChronoDine is an enterprise computer vision and hospitality analytics platform designed to optimize dining room turnover, monitor table occupancy, and streamline front-of-house operations in real time. 

By integrating with standard security infrastructure (RTSP IP camera streams, local video recordings, or direct USB webcams), ChronoDine utilizes dual-model deep learning (YOLOv11 object detection and skeletal pose estimation) to distinguish seated patrons from standing staff, monitor individual table dwell times, and synchronize live dining availability with a hostess waitlist hub.

---

## 1. Executive Overview

Managing dining room capacity and turn times has traditionally required manual observation by floor managers and host staff. ChronoDine automates this process through passive video ingestion and edge intelligence:

* **Automated Dwell Tracking:** Measures the exact duration of each dining session from seating to departure.
* **Staff Filtering:** Employs skeletal pose keypoints to ensure standing servers, bussers, and passing guests do not register as seated customers.
* **Interactive In-Browser Calibration:** Allows operators to define and adjust table boundaries directly on the live camera stream without modifying code or restarting services.
* **Low-Latency Telemetry:** Pushes frame-by-frame state changes to connected web clients via bidirectional WebSockets, with automatic HTTP polling fallback.
* **Enterprise Persistence:** Supports scalable PostgreSQL deployments with connection pooling, as well as zero-configuration SQLite operation with Write-Ahead Logging (WAL).

---

## 2. System Architecture

ChronoDine uses a decoupled worker architecture to guarantee that computationally intensive computer vision tasks never impede web request handling or live client streaming.

```
+-------------------------------------------------------------------------+
|                              VIDEO INGESTION                            |
|  RTSP Camera / IP Stream / Webcam / Local MP4                           |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                         STREAM MANAGER SERVICE                          |
|  - Decoupled frame grabber thread                                       |
|  - Single-frame drop buffer (prevents queue buildup & latency)          |
|  - Automatic reconnection handling                                      |
+-------------------------------------------------------------------------+
            |                                           |
            | (Clean frames)                            | (Raw JPEG)
            v                                           v
+-----------------------------------+       +-----------------------------+
|        AI INFERENCE WORKER        |       |    STREAMING API ENDPOINT   |
|  - YOLOv11 Object Detection       |       |    /api/live/stream/raw     |
|  - YOLOv11 Pose Estimation        |       +-----------------------------+
|  - Polygon Containment Testing    |
|  - Hysteresis & State Machine     |
|  - Dwell Timing & Visit Closure   |
+-----------------------------------+
       |                     |
       v                     v
+---------------+   +-----------------------------------------------------+
| PERSISTENCE   |   |                   WEBSOCKET HUB                     |
| PostgreSQL /  |   |  - Telemetry event dispatcher                       |
| SQLite (WAL)  |   |  - /api/live/ws endpoint                            |
+---------------+   +-----------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                           CHRONODINE WEB APP                            |
|  - Live Floor Plan HUD & Metrics                                        |
|  - Interactive Calibration Studio                                       |
|  - Hostess Waitlist & Seating Hub                                       |
|  - Analytics, Turn Velocity & CSV Reports                               |
+-------------------------------------------------------------------------+
```

---

## 3. Core Features

### 3.1. Zero-Latency Stream Ingestion
The stream ingestion pipeline isolates the video capture loop from the rest of the application. By enforcing a single-frame buffer, ChronoDine eliminates latency drift common in RTSP network streams. The service handles transient network disconnects with exponential backoff and automatic socket re-establishment.

### 3.2. Dual-Model Computer Vision Engine
1. **Person Detection:** YOLOv11 scans frames to identify bounding boxes for individuals in the dining area.
2. **Pose Analysis:** YOLOv11 Pose evaluates skeletal keypoints (hips, knees, and ankles). If a person within a table zone is standing or walking through, they are filtered out to prevent false-positive occupancy triggers.
3. **State Hysteresis:** State transitions (Free to Occupied, Occupied to Free) require persistence across configurable temporal thresholds to filter out transient movements.

### 3.3. In-Browser Calibration Studio
Floor managers can calibrate dining layouts directly in the web browser:
* Visual canvas superimposed on the clean live video stream.
* Point-and-click polygon drawing to define table boundary zones.
* Instant synchronization: New table zones are committed to the database and hot-reloaded into the AI worker without interrupting active monitoring.

### 3.4. Hostess Waitlist and Seating Hub
* Centralized queue management for walk-in parties and reservations.
* Dynamic wait-time counters with overdue notifications.
* Direct seating workflow: Assign waiting parties to available tables identified by the vision system.

### 3.5. Operational Alerts and Analytics
* **Automated Triggers:** Real-time warnings generated for excessive dwell time (tables exceeding target dining durations), high floor utilization, and newly cleared tables ready for seating.
* **Data Export:** Full historical logs of visits, party sizes, and seated durations downloadable in CSV format.

---

## 4. Technology Stack

### Backend
* **Runtime:** Python 3.10+ (Python 3.12 recommended)
* **Web Framework:** FastAPI with Uvicorn ASGI server
* **WebSockets:** WebSockets and wsproto protocol engines
* **Database ORM:** SQLAlchemy 2.0 with connection pooling
* **Database Engines:** PostgreSQL (production) or SQLite 3 with WAL mode (local development)

### Computer Vision and Artificial Intelligence
* **Inference Framework:** Ultralytics YOLOv11
* **Computer Vision:** OpenCV (cv2)
* **Mathematical Operations:** NumPy

### Frontend
* **Architecture:** Modular Single Page Application (SPA)
* **Styling:** Vanilla CSS3 design system with custom properties and responsive layout
* **Visual Components:** HTML5 Canvas for drawing calibration zones and rendering rolling time-series charts
* **Networking:** Native WebSocket client with automatic HTTP polling fallback

---

## 5. Repository Structure

```
ChronoDine/
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |   |-- alerts.py           # Operational alert endpoints
|   |   |   |-- analytics.py        # Reporting, summaries, and CSV exports
|   |   |   |-- calibration.py      # In-browser table polygon endpoints
|   |   |   |-- live.py             # Video streaming and WebSocket handlers
|   |   |   |-- settings.py         # Runtime configuration endpoints
|   |   |   `-- waitlist.py         # Hostess queue management
|   |   |-- services/
|   |   |   |-- ai_worker.py        # YOLOv11 detection and pose pipeline
|   |   |   |-- stream_manager.py   # RTSP and video ingestion worker
|   |   |   `-- websocket_hub.py    # Live WebSocket connection manager
|   |   |-- config.py               # Pydantic environment configuration
|   |   |-- database.py             # SQLAlchemy engine and session pool
|   |   |-- main.py                 # FastAPI application factory and lifecycle
|   |   |-- models.py               # Database schemas
|   |   `-- schemas.py              # API request and response models
|   `-- requirements.txt            # Python package dependencies
|-- frontend/
|   |-- css/
|   |   `-- styles.css              # User interface design system
|   |-- js/
|   |   |-- app.js                  # Application routing and state management
|   |   |-- canvas_calibration.js   # Interactive canvas drawing tool
|   |   |-- charts.js               # Canvas-based time-series occupancy graph
|   |   |-- waitlist.js             # Front-of-house queue manager
|   |   `-- websocket.js            # Resilient WebSocket client
|   `-- index.html                  # Single Page Application entrypoint
|-- models/                         # YOLOv11 weight files (.pt)
|-- videos/                         # Test recordings and demo CCTV footage
|-- .env.example                    # Environment configuration template
|-- .gitignore                      # Version control exclusion rules
|-- docker-compose.yml              # PostgreSQL and backend container definition
|-- Dockerfile                      # Production container build specification
|-- LICENSE                         # MIT open source license
|-- run.bat                         # Windows execution script
|-- tables.json                     # Default table zone coordinates
`-- table_tops.json                 # Default tabletop coordinates
```

---

## 6. Installation and Setup

### 6.1. Prerequisites
* Python 3.10 or higher (Python 3.12 recommended)
* Git
* (Optional) Docker and Docker Compose for PostgreSQL containerization

### 6.2. Local Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd ChronoDine
   ```

2. **Create and activate a virtual environment:**
   * On Windows:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   * On Linux/macOS:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

4. **Verify model weights:**
   Ensure the following pre-trained weight files are present in the `models/` directory:
   * `models/yolo11s.pt`
   * `models/yolo11s-pose.pt`

   *(Note: Model weights and sample video recordings are excluded from git tracking to maintain a compact repository).*

5. **Run the application:**
   * Using the Windows launcher:
     ```cmd
     run.bat
     ```
   * Or using Uvicorn directly:
     ```bash
     python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
     ```

6. **Access the application:**
   Open a browser and navigate to:
   ```text
   http://localhost:8000
   ```

---

## 7. Containerized Deployment with Docker and PostgreSQL

To run the full stack with dedicated PostgreSQL containerization:

1. **Review configuration in `.env`:**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. **Start the containers:**
   ```bash
   docker-compose up -d --build
   ```

3. **Service Details:**
   * **PostgreSQL (`chronodine_postgres`):** Port 5432, persistent volume mounted to `pgdata`
   * **ChronoDine Web Service (`chronodine_app`):** Port 8000 with healthcheck dependencies

4. **Shutdown containers:**
   ```bash
   docker-compose down
   ```

---

## 8. Configuration Reference

Configuration parameters can be defined via environment variables or inside a `.env` file:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | String | `sqlite:///./restaurant_app.db` | SQLAlchemy connection string (PostgreSQL or SQLite). |
| `DB_POOL_SIZE` | Integer | `10` | Base database connection pool size. |
| `DB_MAX_OVERFLOW` | Integer | `20` | Maximum overflow connections allowed in pool. |
| `STREAM_SOURCE` | String | `videos/Cctv Resturant.mp4` | RTSP URI (`rtsp://...`), local video path, or webcam index (`0`). |
| `STREAM_FPS_TARGET` | Integer | `25` | Target playback pace for file-based streams. |
| `JPEG_QUALITY` | Integer | `80` | Compression quality for streamed JPEG frames (1-100). |
| `YOLO_MODEL_PATH` | String | `models/yolo11s.pt` | Path to detection weights file. |
| `YOLO_POSE_MODEL_PATH` | String | `models/yolo11s-pose.pt` | Path to pose estimation weights file. |
| `CONFIDENCE_THRESHOLD` | Float | `0.25` | Person detection minimum confidence (0.05 - 0.95). |
| `POSE_CONFIDENCE_THRESHOLD` | Float | `0.30` | Keypoint estimation minimum confidence (0.05 - 0.95). |
| `OCCUPY_HYSTERESIS_SECONDS` | Float | `1.0` | Required continuous occupancy before triggering state change. |
| `FREE_HYSTERESIS_SECONDS` | Float | `1.5` | Required continuous emptiness before table registers as free. |
| `DEFAULT_SEATS_PER_TABLE` | Integer | `4` | Default seat capacity assigned to newly created tables. |
| `ALERT_IDLE_TABLE_MINUTES` | Integer | `15` | Seated duration threshold for generating dwell alerts. |
| `ALERT_CAPACITY_PERCENT` | Integer | `85` | Dining room utilization threshold for high-capacity warnings. |

---

## 9. API Reference

### 9.1. Live Streaming and Telemetry
* `GET /api/live/stream`
  * Returns an MJPEG stream with overlaid table polygons, occupancy indicators, and timers.
* `GET /api/live/stream/raw`
  * Returns a clean MJPEG video stream for use with the browser calibration canvas.
* `GET /api/live/telemetry`
  * Returns an immediate JSON snapshot of table statuses, guest totals, and utilization.
* `GET /api/live/snapshot`
  * Downloads the current camera frame as a high-resolution JPEG attachment.
* `WS /api/live/ws`
  * Bidirectional WebSocket endpoint broadcasting live telemetry and operational state changes.

### 9.2. Calibration
* `GET /api/calibration/zones`
  * Retrieves all defined table zones, vertex coordinates, and seat capacities.
* `POST /api/calibration/zones`
  * Creates a new table zone from canvas coordinates. Hot-reloads the AI engine.
* `PUT /api/calibration/zones/{zone_id}`
  * Updates coordinates, label, or seat capacity of an existing zone.
* `DELETE /api/calibration/zones/{zone_id}`
  * Removes a table zone from monitoring.
* `POST /api/calibration/import-seed`
  * Initializes default layout polygons from seed configuration files.

### 9.3. Waitlist Management
* `GET /api/waitlist`
  * Retrieves the list of active waiting and recently seated parties.
* `POST /api/waitlist`
  * Adds a new party to the waitlist queue.
* `PUT /api/waitlist/{party_id}/seat?table_name={name}`
  * Marks a party as seated and associates them with a designated table.
* `PUT /api/waitlist/{party_id}/status`
  * Updates party status (`WAITING`, `SEATED`, `CANCELLED`, `NO_SHOW`).
* `DELETE /api/waitlist/{party_id}`
  * Removes a party record from the queue.

### 9.4. Analytics and Reporting
* `GET /api/analytics/summary`
  * Aggregates total visits, average dining duration, and party size statistics.
* `GET /api/analytics/history?minutes={int}`
  * Time-series occupancy snapshots for chart rendering.
* `GET /api/analytics/visits?limit={int}`
  * Paginated list of concluded dining sessions.
* `GET /api/analytics/tables`
  * Individual turnover and dwell performance broken down by table.
* `GET /api/analytics/export/csv`
  * Generates and downloads a complete activity log as a CSV spreadsheet.

### 9.5. Alerts and Configuration
* `GET /api/alerts`
  * Returns active operational warnings and notifications.
* `PUT /api/alerts/{alert_id}/dismiss`
  * Marks an alert as resolved.
* `POST /api/alerts/dismiss-all`
  * Resolves all active alerts.
* `GET /api/settings`
  * Returns current runtime parameters and video source connection status.
* `POST /api/settings`
  * Modifies camera sources and detection thresholds on the fly.

---

## 10. Calibration Workflow

1. Navigate to the **Calibration Studio** tab in the dashboard (`http://localhost:8000/#calibration`).
2. Click **Draw Zone (Polygon)**.
3. Click around the perimeter of the dining area surrounding a table (including chair space).
4. Double-click the final point to close the boundary.
5. In the sidebar, specify the **Table Label** (e.g., "Table 7") and the **Seat Capacity**.
6. Click **Save to AI Engine**.
7. The new table polygon immediately appears on the **Live Floor** HUD and begins reporting occupancy metrics.

---

## 11. Testing with External Camera Streams

To connect ChronoDine to external cameras without dedicated hardware:

* **Mobile Device as RTSP Camera:**
  Install an RTSP streaming utility (such as IP Webcam on Android or Live-Reporter on iOS). Connect your mobile device to the same local Wi-Fi network and input the stream address into the **Settings** panel:
  ```text
  rtsp://<device-ip>:8080/h264_pcm.sdp
  ```
* **Integrated USB Webcam:**
  Set the video source to `0` or `1` in the **Settings** panel to utilize a direct local camera interface.

---

## 12. Operational Notes

This software is designed for deployment on edge servers or local appliances with access to restaurant camera networks. Ensure local regulations regarding camera placement, patron privacy, and automated video processing are observed in production environments.
