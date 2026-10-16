import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Response, HTTPException
from fastapi.responses import StreamingResponse
from ..services.websocket_hub import ws_hub
from ..services.stream_manager import stream_manager
from ..services.ai_worker import ai_worker

router = APIRouter(prefix="/api/live", tags=["Live"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_hub.connect(websocket)
    try:
        # Immediately push initial state
        if ai_worker.latest_telemetry:
            await websocket.send_json(ai_worker.latest_telemetry)

        # Keep alive and receive any client ping/pong messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_hub.disconnect(websocket)
    except Exception:
        await ws_hub.disconnect(websocket)


def _generate_mjpeg(raw: bool = False):
    while True:
        if raw:
            _, _, jpeg = stream_manager.get_latest_frame()
        else:
            jpeg = ai_worker.annotated_jpeg or stream_manager.latest_jpeg

        if jpeg is None:
            time.sleep(0.04)
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
        time.sleep(0.033)  # ~30 fps cap


@router.get("/stream")
def live_stream():
    """Live video stream with AI detection and table overlay."""
    return StreamingResponse(_generate_mjpeg(raw=False), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/stream/raw")
def raw_stream():
    """Clean live video stream without overlays (for interactive calibration canvas)."""
    return StreamingResponse(_generate_mjpeg(raw=True), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/telemetry")
def get_telemetry():
    """Get the latest real-time restaurant statistics."""
    return ai_worker.latest_telemetry or {
        "status": "initializing",
        "occupied_tables": 0,
        "total_tables": len(ai_worker.table_zones),
        "total_guests": 0,
        "utilization_pct": 0.0,
    }


@router.get("/snapshot")
def capture_snapshot():
    """Download current video frame as JPEG file."""
    jpeg = ai_worker.annotated_jpeg or stream_manager.latest_jpeg
    if not jpeg:
        raise HTTPException(status_code=503, detail="Camera feed not available")
    filename = f"floor-snapshot-{int(time.time())}.jpg"
    return Response(content=jpeg, media_type="image/jpeg",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
