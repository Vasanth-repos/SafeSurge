"""
Compatibility wrapper delegating to canonical Layer 5 SurfaceStorageEngine.
"""

from typing import Any

from flood_engine.d8 import D8Terrain
from flood_engine.grid import ComputationalGrid
from flood_engine.surface import SurfaceStep, SurfaceStorageEngine


class SimulationEngine:
    """Wrapper around canonical SurfaceStorageEngine for legacy simulation calls."""

    def __init__(
        self,
        grid: ComputationalGrid | None = None,
        terrain: D8Terrain | None = None,
        config_path: str = "config.yaml",
    ):
        if grid is None:
            grid = ComputationalGrid.create_synthetic_demo_grid(rows=20, cols=20, resolution_m=10.0)
        if terrain is None:
            terrain = D8Terrain.compute_from_grid(grid)

        self.engine = SurfaceStorageEngine(
            grid=grid,
            terrain=terrain,
            config_path=config_path,
        )

    def step(self, timestamp_seconds: int, runoff_volume_m3: Any) -> SurfaceStep:
        return self.engine.step(timestamp_seconds, runoff_volume_m3)

    def mass_balance(self) -> dict[str, Any]:
        return self.engine.mass_balance()

    def reset(self) -> None:
        self.engine.reset()
