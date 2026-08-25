"""
Compatibility wrapper delegating to canonical Layer 5 SurfaceStorageEngine.
"""

from typing import Dict, Any, Optional
from flood_engine.surface import SurfaceStorageEngine, SurfaceStep
from flood_engine.grid import ComputationalGrid
from flood_engine.d8 import D8Terrain


class SimulationEngine:
    """Wrapper around canonical SurfaceStorageEngine for legacy simulation calls."""

    def __init__(
        self,
        grid: Optional[ComputationalGrid] = None,
        terrain: Optional[D8Terrain] = None,
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

    def mass_balance(self) -> Dict[str, Any]:
        return self.engine.mass_balance()

    def reset(self) -> None:
        self.engine.reset()
