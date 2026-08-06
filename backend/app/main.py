import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.data import seed
from app.db import SessionLocal
from app.init_db import init_db
from app.routers import dashboard, feedback, forecast, ingest, observability, recommend, surges
from app.services import surge_watcher

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title="Utility Grid Copilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast.router)
app.include_router(recommend.router)
app.include_router(ingest.router)
app.include_router(ingest.rag_router)
app.include_router(observability.router)
app.include_router(surges.router)
app.include_router(dashboard.router)
app.include_router(feedback.router)


async def _surge_watcher_loop():
    while True:
        await asyncio.sleep(settings.surge_check_interval_seconds)
        try:
            db = SessionLocal()
            try:
                await asyncio.to_thread(surge_watcher.run_surge_check_all_regions, db)
            finally:
                db.close()
        except Exception:
            # An asyncio.create_task task that raises just dies silently —
            # surge detection would stop forever with no signal. Catching
            # here means one bad iteration can't take down the whole loop.
            logger.exception("Surge watcher loop iteration failed, will retry next interval")


@app.on_event("startup")
def on_startup():
    init_db()
    seed.seed_demand_data()
    seed.seed_california_demand()
    seed.seed_procedures()
    asyncio.create_task(_surge_watcher_loop())
    logger.info("Surge watcher background loop started (interval=%ss)", settings.surge_check_interval_seconds)


@app.get("/health")
def health():
    return {"status": "ok"}
