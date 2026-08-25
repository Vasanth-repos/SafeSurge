"""
Layer 19 — Dependency Injection Providers for FastAPI:
Provides centralized singleton access to SimulationManager, SensorValidator, and Routing services.
"""

from backend.services.simulation_manager import SimulationManager

_sim_manager = SimulationManager(config_path="config.yaml")


def get_simulation_manager() -> SimulationManager:
    return _sim_manager
