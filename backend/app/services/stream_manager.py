import time
import threading
import logging
import cv2
from typing import Optional, Tuple
import numpy as np
from ..config import settings

logger = logging.getLogger("restaurant.stream_manager")


class StreamManager:
    """
    Decoupled video ingestion engine supporting RTSP IP cameras, video files, and webcams.
    Uses a zero-latency single-frame buffer to prevent RTSP queue buildup.
    """
    def __init__(self):
        self.source_url: str = settings.STREAM_SOURCE
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running: bool = False
        self.worker_thread: Optional[threading.Thread] = None

        self._frame_lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_jpeg: Optional[bytes] = None
        self.frame_number: int = 0
        self.fps: float = 30.0
        self.width: int = 1280
        self.height: int = 720
        self.is_connected: bool = False

    def start(self, source_url: Optional[str] = None):
        if source_url:
            self.source_url = source_url

        if self.is_running:
            self.stop()

        self.is_running = True
        self.worker_thread = threading.Thread(target=self._capture_loop, daemon=True, name="StreamIngestWorker")
        self.worker_thread.start()
        logger.info(f"Stream ingestion started for: {self.source_url}")

    def stop(self):
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_connected = False
        logger.info("Stream ingestion stopped.")

    def update_source(self, new_source: str):
        logger.info(f"Switching video stream source to: {new_source}")
        self.source_url = new_source
        self.start(new_source)

    def get_latest_frame(self) -> Tuple[int, Optional[np.ndarray], Optional[bytes]]:
        with self._frame_lock:
            return self.frame_number, self.latest_frame, self.latest_jpeg

    def _open_capture(self) -> bool:
        # Check if source is numeric webcam index
        if self.source_url.isdigit():
            src = int(self.source_url)
        else:
            src = self.source_url

        logger.info(f"Opening video source: {src}")
        self.cap = cv2.VideoCapture(src)

        # Optimization for RTSP streams to reduce latency buffer
        if isinstance(src, str) and src.lower().startswith("rtsp"):
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.cap.isOpened():
            logger.warning(f"Failed to open video source: {src}")
            return False

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        self.is_connected = True
        logger.info(f"Stream opened successfully. Resolution: {self.width}x{self.height} @ {self.fps:.1f} FPS")
        return True

    def _capture_loop(self):
        reconnect_delay = 2.0

        while self.is_running:
            if self.cap is None or not self.cap.isOpened():
                if not self._open_capture():
                    time.sleep(reconnect_delay)
                    continue

            ret, frame = self.cap.read()

            # Handle end of file (loop playback for demonstration / CCTV test footage)
            if not ret or frame is None:
                if isinstance(self.source_url, str) and not self.source_url.lower().startswith("rtsp"):
                    # Loop local video file
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.01)
                    continue
                else:
                    logger.warning("RTSP / Camera frame drop or disconnect. Attempting reconnect...")
                    self.cap.release()
                    self.cap = None
                    self.is_connected = False
                    time.sleep(reconnect_delay)
                    continue

            # Encode JPEG for fast web delivery
            _, jpeg_buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.JPEG_QUALITY])

            with self._frame_lock:
                self.latest_frame = frame
                self.latest_jpeg = jpeg_buffer.tobytes()
                self.frame_number += 1

            # Respect target FPS pace when playing from file
            if not (isinstance(self.source_url, str) and self.source_url.lower().startswith("rtsp")):
                time.sleep(1.0 / max(10, self.fps))


stream_manager = StreamManager()
