import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.init_db import init_db
from app.routers import forecast, ingest, recommend

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Utility Grid Copilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast.router)
app.include_router(recommend.router)
app.include_router(ingest.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
