import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.data import seed
from app.init_db import init_db
from app.routers import forecast, ingest, observability, recommend

logging.basicConfig(level=logging.INFO)

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
app.include_router(observability.router)


@app.on_event("startup")
def on_startup():
    init_db()
    seed.seed_demand_data()
    seed.seed_procedures()


@app.get("/health")
def health():
    return {"status": "ok"}
