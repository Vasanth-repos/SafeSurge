"""
Main Application Entrypoint (Layer 19):
Mounts all REST API routers, provides /health liveness probe,
and orchestrates requests across backend domain services.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.api.rainfall import router as rainfall_router
from backend.api.simulation import router as simulation_router
from backend.api.sensors import router as sensors_router
from backend.api.flood import router as flood_router
from backend.api.roads import router as roads_router
from backend.api.routes import router as routes_router
from backend.api.diagnostics import router as diagnostics_router
from backend.api.scenarios import router as scenarios_router
from backend.api.snapshots import router as snapshots_router
from backend.api.dashboard import router as dashboard_router
from backend.services.simulation_service import SimulationService

# Core simulation service instance for legacy scenario endpoints
sim_service = SimulationService(config_path="config/defaults.yaml")

app = FastAPI(
    title="Urban Flood Nowcasting & Response System",
    description="Real-time hydrological flood forecasting, sensor validation & fusion, multi-criteria anomalies, and risk-aware emergency routing.",
    version="1.0.0",
)

# CORS middleware for frontend and external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe for backend orchestrator."""
    return {"status": "ok"}


# Mount domain API routers
app.include_router(rainfall_router)
app.include_router(simulation_router)
app.include_router(sensors_router)
app.include_router(flood_router)
app.include_router(roads_router)
app.include_router(routes_router)
app.include_router(diagnostics_router)
app.include_router(scenarios_router)
app.include_router(snapshots_router)
app.include_router(dashboard_router)

# Mount static frontend build if present
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
