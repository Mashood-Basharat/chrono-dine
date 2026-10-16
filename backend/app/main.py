import asyncio
import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .database import engine, Base, SessionLocal
from .models import TableZone
from .services.stream_manager import stream_manager
from .services.ai_worker import ai_worker
from .api import live, calibration, waitlist, analytics, alerts, settings as api_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("restaurant.main")


def auto_seed_default_zones():
    """Ensure initial table polygons exist if database was just created."""
    db = SessionLocal()
    try:
        count = db.query(TableZone).count()
        if count == 0:
            logger.info("Initializing default table zones from configuration files...")
            tables_file = "tables.json"
            tops_file = "table_tops.json"
            tables = {}
            tops = {}
            if os.path.exists(tables_file):
                with open(tables_file) as f:
                    tables = json.load(f)
            if os.path.exists(tops_file):
                with open(tops_file) as f:
                    tops = json.load(f)

            for name, poly in tables.items():
                top = tops.get(name, [])
                zone = TableZone(
                    name=name,
                    polygon_coords=json.dumps(poly),
                    top_coords=json.dumps(top),
                    seats=4,
                    is_active=True
                )
                db.add(zone)
            db.commit()
            logger.info(f"Seeded {len(tables)} initial table zones into database.")
    except Exception as e:
        logger.error(f"Error seeding default table zones: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Restaurant Analytics Platform...")
    Base.metadata.create_all(bind=engine)
    auto_seed_default_zones()

    # Start video ingestion
    stream_manager.start()

    # Start decoupled AI analytics worker with current async event loop
    loop = asyncio.get_running_loop()
    ai_worker.start(loop=loop)

    yield

    # Shutdown
    logger.info("Shutting down Restaurant Analytics Platform...")
    ai_worker.stop()
    stream_manager.stop()


app = FastAPI(
    title="ChronoDine Enterprise Restaurant Intelligence Platform",
    description="Real-Time Restaurant Table Occupancy, Dwell-Time Tracking & Calibration Platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(live.router)
app.include_router(calibration.router)
app.include_router(waitlist.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(api_settings.router)

# Mount Frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
