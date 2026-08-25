"""
Main FastAPI Application for Urban Flood Nowcasting & Response System.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.services.simulation_service import SimulationService
from backend.api.rainfall import router as rainfall_router
from backend.api.sensors import router as sensors_router
from backend.api.flood import router as flood_router
from backend.api.routes import router as routes_router
from backend.api.diagnostics import router as diagnostics_router
from backend.api.scenarios import router as scenarios_router

# Initialize core simulation service
sim_service = SimulationService(config_path="config/defaults.yaml")

app = FastAPI(
    title="Urban Flood Nowcasting & Response System",
    description="Real-time hydrological flood forecasting, sensor validation & fusion, mass conservation diagnostics, and risk-aware emergency routing.",
    version="1.0.0",
)

# CORS middleware for development and external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(rainfall_router)
app.include_router(sensors_router)
app.include_router(flood_router)
app.include_router(routes_router)
app.include_router(diagnostics_router)
app.include_router(scenarios_router)

# Mount frontend if exists
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def root():
    return {
        "system": "Urban Flood Nowcasting & Response System",
        "status": "ONLINE",
        "api_docs": "/docs",
        "dashboard_ui": "/static/index.html",
        "version": "1.0.0",
    }
