import asyncio
import collections
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

import cv2
import numpy as np
from ultralytics import YOLO

from ..config import settings
from ..database import SessionLocal
from ..models import TableZone, Visit, Snapshot, SystemAlert
from .stream_manager import stream_manager
from .websocket_hub import ws_hub

logger = logging.getLogger("restaurant.ai_worker")


class AIWorker:
    """
    Decoupled Computer Vision & Analytics Processing Worker.
    Performs YOLOv11 person detection, pose standing filter, polygon containment,
    table dwell timing, alert triggering, and database persistence.
    """
    def __init__(self):
        self.is_running: bool = False
        self.worker_thread: Optional[threading.Thread] = None

        self.model: Optional[YOLO] = None
        self.pose_model: Optional[YOLO] = None

        self.table_zones: Dict[str, Dict[str, Any]] = {}
        self.table_states: Dict[str, Dict[str, Any]] = {}
        self.latest_telemetry: Dict[str, Any] = {}
        self.annotated_jpeg: Optional[bytes] = None

        self.last_snapshot_time: float = 0.0
        self.processing_fps: float = 0.0

        # Loop reference for async websocket broadcast from background thread
        self.async_loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.async_loop = loop
        if self.is_running:
            return

        self._load_models()
        self._load_table_zones()

        self.is_running = True
        self.worker_thread = threading.Thread(target=self._processing_loop, daemon=True, name="AIEngineWorker")
        self.worker_thread.start()
        logger.info("AI Analytics Worker thread started.")

    def stop(self):
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        logger.info("AI Analytics Worker thread stopped.")

    def reload_zones(self):
        self._load_table_zones()
        logger.info("Reloaded table zones from database.")

    def _load_models(self):
        try:
            logger.info(f"Loading YOLO detection model from {settings.YOLO_MODEL_PATH}...")
            self.model = YOLO(settings.YOLO_MODEL_PATH)
            logger.info(f"Loading YOLO pose model from {settings.YOLO_POSE_MODEL_PATH}...")
            self.pose_model = YOLO(settings.YOLO_POSE_MODEL_PATH)
            logger.info("YOLO models loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading YOLO models: {e}")

    def _load_table_zones(self):
        db = SessionLocal()
        try:
            zones = db.query(TableZone).filter(TableZone.is_active == True).all()
            new_zones = {}
            for zone in zones:
                poly = json.loads(zone.polygon_coords) if zone.polygon_coords else []
                top = json.loads(zone.top_coords) if zone.top_coords else []
                new_zones[zone.name] = {
                    "id": zone.id,
                    "polygon": np.array(poly, dtype=np.int32) if poly else np.array([]),
                    "top": np.array(top, dtype=np.int32) if top else np.array([]),
                    "raw_polygon": poly,
                    "raw_top": top,
                    "seats": zone.seats,
                }
            self.table_zones = new_zones

            # Initialize states for any newly discovered tables
            for name, z in self.table_zones.items():
                if name not in self.table_states:
                    self.table_states[name] = {
                        "status": "FREE",
                        "guests": 0,
                        "raw_guest_history": collections.deque(maxlen=15),
                        "state_changed_at": time.time(),
                        "visit_started_at": None,
                        "dwell_seconds": 0,
                        "alert_sent_idle": False,
                    }
        except Exception as e:
            logger.error(f"Failed to load table zones from DB: {e}")
        finally:
            db.close()

    def _processing_loop(self):
        last_frame_number = -1
        fps_timer = time.time()
        fps_frame_counter = 0

        while self.is_running:
            frame_num, frame, _ = stream_manager.get_latest_frame()

            if frame is None or frame_num == last_frame_number:
                time.sleep(0.005)
                continue

            last_frame_number = frame_num
            fps_frame_counter += 1

            now = time.time()
            if now - fps_timer >= 1.0:
                self.processing_fps = fps_frame_counter / (now - fps_timer)
                fps_frame_counter = 0
                fps_timer = now

            # Process frame
            try:
                self._analyze_frame(frame.copy(), now)
            except Exception as e:
                logger.error(f"Error analyzing frame: {e}", exc_info=True)
                time.sleep(0.05)

    def _analyze_frame(self, frame: np.ndarray, current_time: float):
        h, w = frame.shape[:2]

        # 1. Detect people
        person_boxes = []
        if self.model:
            results = self.model(frame, conf=settings.CONFIDENCE_THRESHOLD, classes=[0], verbose=False)[0]
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                person_boxes.append((x1, y1, x2, y2))

        # 2. Detect standing vs sitting keypoints with pose model
        standing_centroids = set()
        if self.pose_model and person_boxes:
            pose_results = self.pose_model(frame, conf=settings.POSE_CONFIDENCE_THRESHOLD, verbose=False)[0]
            if pose_results.keypoints is not None:
                for kpts in pose_results.keypoints.data:
                    # Filter standing people: height ratio of ankles vs hips
                    # Keypoints: 11, 12 = hips; 15, 16 = ankles
                    if len(kpts) > 16:
                        hip_y = (kpts[11][1].item() + kpts[12][1].item()) / 2.0
                        ankle_y = (kpts[15][1].item() + kpts[16][1].item()) / 2.0
                        if hip_y > 0 and ankle_y > 0:
                            # If person is fully upright with straight legs, mark as standing
                            leg_len = ankle_y - hip_y
                            if leg_len > h * 0.18:
                                cx = (kpts[11][0].item() + kpts[12][0].item()) / 2.0
                                standing_centroids.add((int(cx), int(hip_y)))

        # 3. Associate detected persons with table zones
        seated_per_table = {name: 0 for name in self.table_zones}
        for (x1, y1, x2, y2) in person_boxes:
            cx = (x1 + x2) // 2
            cy = int(y1 + (y2 - y1) * 0.75)  # approximate seat/hip point

            # Check if person is identified as a standing passerby
            is_standing = any(abs(cx - scx) < 40 and abs(cy - scy) < 60 for scx, scy in standing_centroids)
            if is_standing:
                continue

            for name, z in self.table_zones.items():
                if len(z["polygon"]) >= 3:
                    inside = cv2.pointPolygonTest(z["polygon"], (float(cx), float(cy)), False) >= 0
                    if inside:
                        seated_per_table[name] += 1
                        break

        # 4. State Machine & Hysteresis for each table
        total_guests = 0
        occupied_count = 0
        total_seats = 0
        db_visits_to_save = []
        new_alerts = []

        for name, z in self.table_zones.items():
            state = self.table_states.setdefault(name, {
                "status": "FREE",
                "guests": 0,
                "raw_guest_history": collections.deque(maxlen=15),
                "state_changed_at": current_time,
                "visit_started_at": None,
                "dwell_seconds": 0,
                "alert_sent_idle": False,
            })

            detected_guests = seated_per_table.get(name, 0)
            state["raw_guest_history"].append(detected_guests)

            # Mode/majority filtering
            recent_counts = list(state["raw_guest_history"])
            smoothed_guests = max(set(recent_counts), key=recent_counts.count)

            elapsed_in_state = current_time - state["state_changed_at"]

            if state["status"] == "FREE":
                if smoothed_guests > 0 and elapsed_in_state >= settings.OCCUPY_HYSTERESIS_SECONDS:
                    state["status"] = "OCCUPIED"
                    state["guests"] = smoothed_guests
                    state["state_changed_at"] = current_time
                    state["visit_started_at"] = current_time
                    state["dwell_seconds"] = 0
                    state["alert_sent_idle"] = False
            elif state["status"] == "OCCUPIED":
                dwell = int(current_time - state["visit_started_at"]) if state["visit_started_at"] else 0
                state["dwell_seconds"] = dwell

                if smoothed_guests == 0:
                    if elapsed_in_state >= settings.FREE_HYSTERESIS_SECONDS:
                        # Conclude visit
                        if dwell >= 10:  # Ignore fleeting false occupancy
                            db_visits_to_save.append({
                                "table_name": name,
                                "started_at": datetime.utcfromtimestamp(state["visit_started_at"]),
                                "ended_at": datetime.utcfromtimestamp(current_time),
                                "duration_seconds": dwell,
                                "guest_count": state["guests"]
                            })
                            new_alerts.append({
                                "type": "TABLE_CLEARED",
                                "title": f"{name} Available",
                                "message": f"{name} is now cleared and ready for next guests.",
                                "severity": "INFO"
                            })

                        state["status"] = "FREE"
                        state["guests"] = 0
                        state["state_changed_at"] = current_time
                        state["visit_started_at"] = None
                        state["dwell_seconds"] = 0
                else:
                    state["guests"] = smoothed_guests

                    # Check dwell threshold alert (> 15 minutes)
                    if dwell >= settings.ALERT_IDLE_TABLE_MINUTES * 60 and not state["alert_sent_idle"]:
                        state["alert_sent_idle"] = True
                        new_alerts.append({
                            "type": "LONG_DWELL",
                            "title": f"{name} Long Visit",
                            "message": f"Guests at {name} have been seated for {dwell // 60} minutes.",
                            "severity": "WARNING"
                        })

            if state["status"] == "OCCUPIED":
                occupied_count += 1
                total_guests += state["guests"]
            total_seats += z["seats"]

        # 5. Check High Capacity Alert
        utilization_pct = (total_guests / total_seats * 100.0) if total_seats > 0 else 0.0
        if utilization_pct >= settings.ALERT_CAPACITY_PERCENT:
            new_alerts.append({
                "type": "HIGH_CAPACITY",
                "title": "High Dining Utilization",
                "message": f"Floor capacity is currently at {utilization_pct:.1f}% ({total_guests}/{total_seats} seats).",
                "severity": "WARNING"
            })

        # 6. Database saves (visits, snapshot, alerts)
        self._save_db_records(db_visits_to_save, new_alerts, occupied_count, total_guests, utilization_pct, current_time)

        # 7. Render high-res modern visualization overlays
        self._render_overlay(frame, seated_per_table)

        # 8. Compile live telemetry & broadcast via WebSockets
        telemetry = {
            "type": "telemetry",
            "timestamp": int(current_time),
            "fps": round(self.processing_fps, 1),
            "occupied_tables": occupied_count,
            "total_tables": len(self.table_zones),
            "total_guests": total_guests,
            "total_seats": total_seats,
            "utilization_pct": round(utilization_pct, 1),
            "tables": {
                name: {
                    "status": s["status"],
                    "guests": s["guests"],
                    "seats": self.table_zones[name]["seats"],
                    "dwell_seconds": s["dwell_seconds"],
                    "dwell_formatted": f"{s['dwell_seconds'] // 60}m {s['dwell_seconds'] % 60}s" if s['dwell_seconds'] else "–",
                }
                for name, s in self.table_states.items()
            }
        }
        self.latest_telemetry = telemetry

        if self.async_loop and self.async_loop.is_running() and ws_hub.client_count > 0:
            asyncio.run_coroutine_threadsafe(ws_hub.broadcast(telemetry), self.async_loop)

    def _render_overlay(self, frame: np.ndarray, seated_per_table: Dict[str, int]):
        """Draw aesthetic glassmorphism-style borders and badges on tables."""
        for name, z in self.table_zones.items():
            state = self.table_states.get(name, {})
            is_occ = state.get("status") == "OCCUPIED"

            # Color scheme: Emerald green for free, Coral Crimson for occupied
            color = (60, 60, 240) if is_occ else (80, 220, 100)

            # Draw table zone polygon
            if len(z["polygon"]) >= 3:
                overlay = frame.copy()
                cv2.fillPoly(overlay, [z["polygon"]], color)
                cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
                cv2.polylines(frame, [z["polygon"]], True, color, 2, cv2.LINE_AA)

            # Draw table top outline if specified
            if len(z["top"]) >= 3:
                cv2.polylines(frame, [z["top"]], True, (255, 255, 255), 1, cv2.LINE_AA)

            # Compute label position
            if len(z["polygon"]) > 0:
                cx, cy = z["polygon"].mean(axis=0).astype(int)
                badge_text = f"{name}: {state.get('guests', 0)}/{z['seats']}"
                if is_occ and state.get("dwell_seconds"):
                    badge_text += f" ({state.get('dwell_seconds') // 60}m)"

                # Draw modern pill badge
                (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                cv2.rectangle(frame, (cx - tw // 2 - 8, cy - th - 8), (cx + tw // 2 + 8, cy + 6), (20, 24, 30), -1)
                cv2.rectangle(frame, (cx - tw // 2 - 8, cy - th - 8), (cx + tw // 2 + 8, cy + 6), color, 1)
                cv2.putText(frame, badge_text, (cx - tw // 2, cy - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # Encode annotated JPEG
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.JPEG_QUALITY])
        self.annotated_jpeg = buf.tobytes()

    def _save_db_records(self, visits, alerts, occupied_count, total_guests, util_pct, current_time):
        should_snapshot = (current_time - self.last_snapshot_time >= 5.0)
        if not visits and not alerts and not should_snapshot:
            return

        db = SessionLocal()
        try:
            # Save finished visits
            for v in visits:
                record = Visit(
                    table_name=v["table_name"],
                    started_at=v["started_at"],
                    ended_at=v["ended_at"],
                    duration_seconds=v["duration_seconds"],
                    guest_count=v["guest_count"]
                )
                db.add(record)

            # Save alerts
            for a in alerts:
                # Deduplicate recent identical alerts within 5 minutes
                existing = db.query(SystemAlert).filter(
                    SystemAlert.alert_type == a["type"],
                    SystemAlert.title == a["title"],
                    SystemAlert.is_dismissed == False
                ).first()
                if not existing:
                    alt = SystemAlert(
                        alert_type=a["type"],
                        title=a["title"],
                        message=a["message"],
                        severity=a["severity"]
                    )
                    db.add(alt)

            # Periodic 5-second snapshots
            if current_time - self.last_snapshot_time >= 5.0:
                snap = Snapshot(
                    recorded_at=datetime.utcnow(),
                    occupied_tables=occupied_count,
                    total_guests=total_guests,
                    utilization_pct=util_pct
                )
                db.add(snap)
                self.last_snapshot_time = current_time

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist records to DB: {e}")
        finally:
            db.close()


ai_worker = AIWorker()
