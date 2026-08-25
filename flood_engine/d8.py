"""
Layer 2 — DEM + D8 Terrain Flow Analysis Engine:
Deterministic 8-neighbor downslope routing, terminal state classification,
flow-path tracing, and spatial validation.
"""

from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path
import math
import json
import csv
import numpy as np

from flood_engine.grid import ComputationalGrid, GridCell


# Fixed deterministic 8-neighbor order for tie-breaking
NEIGHBOR_ORDER = [
    ("N",  -1,  0, 1.0),
    ("E",   0,  1, 1.0),
    ("S",   1,  0, 1.0),
    ("W",   0, -1, 1.0),
    ("NE", -1,  1, math.sqrt(2.0)),
    ("SE",  1,  1, math.sqrt(2.0)),
    ("SW",  1, -1, math.sqrt(2.0)),
    ("NW", -1, -1, math.sqrt(2.0)),
]


@dataclass
class D8Cell:
    cell_id: str
    row: int
    col: int
    elevation_m: float
    slope: float
    downstream_cell: Optional[str]
    direction: Optional[str]
    state: str  # 'downstream', 'outlet', 'boundary', 'local_sink', 'flat_sink'
    is_boundary: bool
    is_outlet: bool


class D8Terrain:
    def __init__(
        self,
        grid: ComputationalGrid,
        cells: Dict[str, D8Cell],
        slope_grid: np.ndarray,
        flow_dir_grid: np.ndarray,  # array of direction strings or None
        downstream_grid: np.ndarray, # array of downstream cell IDs or None
    ):
        self.grid = grid
        self.cells = cells
        self.slope_grid = slope_grid
        self.flow_dir_grid = flow_dir_grid
        self.downstream_grid = downstream_grid

    @property
    def valid_cell_count(self) -> int:
        return len(self.cells)

    def get_cell(self, cell_id: str) -> D8Cell:
        if cell_id not in self.cells:
            raise KeyError(f"Cell ID {cell_id} not in D8 terrain domain.")
        return self.cells[cell_id]

    @classmethod
    def compute_from_grid(cls, grid: ComputationalGrid) -> "D8Terrain":
        """
        Computes D8 steepest-descent flow direction, slope, and terminal states for all valid cells in the grid.
        """
        rows, cols = grid.rows, grid.columns
        res = grid.resolution_m

        slope_grid = np.zeros((rows, cols), dtype=np.float64)
        flow_dir_grid = np.full((rows, cols), None, dtype=object)
        downstream_grid = np.full((rows, cols), None, dtype=object)
        cells_dict: Dict[str, D8Cell] = {}

        for r in range(rows):
            for c in range(cols):
                if not grid.valid_mask[r, c]:
                    continue

                cell_id = grid.indices_to_cell_id(r, c)
                curr_elev = float(grid.elevation_m[r, c])
                is_boundary = bool(grid.boundary_mask[r, c])
                is_outlet = bool(grid.outlet_mask[r, c])

                # 1. Check if configured as explicit outlet
                if is_outlet:
                    slope_grid[r, c] = 0.0
                    flow_dir_grid[r, c] = None
                    downstream_grid[r, c] = None
                    cells_dict[cell_id] = D8Cell(
                        cell_id=cell_id,
                        row=r,
                        col=c,
                        elevation_m=curr_elev,
                        slope=0.0,
                        downstream_cell=None,
                        direction=None,
                        state="outlet",
                        is_boundary=is_boundary,
                        is_outlet=True,
                    )
                    continue

                # 2. Inspect 8 neighbors in fixed deterministic order
                best_slope = 0.0
                best_dir: Optional[str] = None
                best_downstream_id: Optional[str] = None
                has_equal_neighbor = False

                for direction_name, dr, dc, dist_factor in NEIGHBOR_ORDER:
                    nr, nc = r + dr, c + dc

                    # Ignore out of bounds or outside catchment/nodata cells
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    if not grid.valid_mask[nr, nc]:
                        continue

                    neighbor_elev = float(grid.elevation_m[nr, nc])
                    dz = curr_elev - neighbor_elev
                    distance_m = res * dist_factor

                    if dz > 1e-9:
                        slope = dz / distance_m
                        # Strictly greater slope selects new steepest neighbor (tie-breaks to first encountered)
                        if slope > best_slope:
                            best_slope = slope
                            best_dir = direction_name
                            best_downstream_id = grid.indices_to_cell_id(nr, nc)
                    elif abs(dz) <= 1e-9:
                        has_equal_neighbor = True

                # 3. Classify terminal state
                if best_downstream_id is not None and best_slope > 0.0:
                    state = "downstream"
                elif is_boundary:
                    state = "boundary"
                elif has_equal_neighbor:
                    state = "flat_sink"
                else:
                    state = "local_sink"

                slope_grid[r, c] = best_slope
                flow_dir_grid[r, c] = best_dir
                downstream_grid[r, c] = best_downstream_id

                cells_dict[cell_id] = D8Cell(
                    cell_id=cell_id,
                    row=r,
                    col=c,
                    elevation_m=curr_elev,
                    slope=best_slope,
                    downstream_cell=best_downstream_id,
                    direction=best_dir,
                    state=state,
                    is_boundary=is_boundary,
                    is_outlet=is_outlet,
                )

        return cls(
            grid=grid,
            cells=cells_dict,
            slope_grid=slope_grid,
            flow_dir_grid=flow_dir_grid,
            downstream_grid=downstream_grid,
        )

    def trace_to_terminal(self, start_cell_id: str, max_steps: int = 1000) -> List[str]:
        """
        Traces continuous downstream flow path from start_cell_id until a terminal cell
        (outlet, boundary, or sink) is reached. Detects loops.
        """
        path = [start_cell_id]
        visited = {start_cell_id}
        curr_id = start_cell_id

        while len(path) < max_steps:
            cell = self.get_cell(curr_id)
            downstream_id = cell.downstream_cell

            if downstream_id is None:
                # Terminal reached
                break

            if downstream_id in visited:
                # Cycle safeguard
                path.append(f"{downstream_id} (CYCLE)")
                break

            visited.add(downstream_id)
            path.append(downstream_id)
            curr_id = downstream_id

        return path

    def validate_d8(self) -> Dict[str, Any]:
        """
        Performs strict structural validation on the D8 terrain topology:
        1. Every valid cell is classified into exactly one valid state.
        2. Downstream targets exist and have strictly lower elevation.
        3. Slopes are non-negative.
        4. Outlets have no downstream targets.
        5. Boundary cells match Layer 1 definitions.
        """
        total_valid = len(self.cells)
        downstream_count = 0
        outlet_count = 0
        boundary_count = 0
        sink_count = 0
        flat_count = 0
        violations = []

        valid_states = {"downstream", "outlet", "boundary", "local_sink", "flat_sink"}

        for cid, cell in self.cells.items():
            if cell.state not in valid_states:
                violations.append(f"Cell {cid} has unknown state '{cell.state}'")

            if cell.state == "downstream":
                downstream_count += 1
                if cell.downstream_cell is None:
                    violations.append(f"Cell {cid} marked downstream but has no target")
                elif cell.downstream_cell not in self.cells:
                    violations.append(f"Cell {cid} downstream target {cell.downstream_cell} is invalid")
                else:
                    target = self.cells[cell.downstream_cell]
                    if target.elevation_m >= cell.elevation_m:
                        violations.append(f"Cell {cid} (elev={cell.elevation_m}) >= downstream {target.cell_id} (elev={target.elevation_m})")
                    if cell.slope <= 0.0:
                        violations.append(f"Cell {cid} downstream slope <= 0")

            elif cell.state == "outlet":
                outlet_count += 1
                if cell.downstream_cell is not None:
                    violations.append(f"Outlet cell {cid} must not have downstream target")

            elif cell.state == "boundary":
                boundary_count += 1
                if not cell.is_boundary:
                    violations.append(f"Cell {cid} classified boundary but is_boundary=False")

            elif cell.state == "local_sink":
                sink_count += 1
            elif cell.state == "flat_sink":
                flat_count += 1

        is_valid = len(violations) == 0
        return {
            "is_valid": is_valid,
            "total_valid_cells": total_valid,
            "downstream_count": downstream_count,
            "outlet_count": outlet_count,
            "boundary_count": boundary_count,
            "local_sink_count": sink_count,
            "flat_sink_count": flat_count,
            "violation_count": len(violations),
            "violations": violations[:10],
        }

    def export_routing_table_csv(self, output_csv_path: Union[str, Path]) -> Path:
        """
        Exports human-readable routing mapping: cell_id, row, col, elevation, slope, direction, downstream_cell, state.
        """
        csv_path = Path(output_csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "cell_id", "row", "col", "elevation_m", "slope",
                "direction", "downstream_cell", "state", "is_boundary", "is_outlet"
            ])
            for cid in sorted(self.cells.keys()):
                c = self.cells[cid]
                writer.writerow([
                    c.cell_id, c.row, c.col, round(c.elevation_m, 4),
                    round(c.slope, 6), c.direction or "", c.downstream_cell or "",
                    c.state, c.is_boundary, c.is_outlet
                ])

        return csv_path

    def save_to_file(self, output_path: Union[str, Path]) -> Tuple[Path, Path, Path]:
        """
        Saves D8 terrain artifacts: .npz arrays, .metadata.json provenance, and .csv routing table.
        """
        base_path = Path(output_path)
        base_path.parent.mkdir(parents=True, exist_ok=True)
        npz_path = base_path.with_suffix(".npz")
        json_path = base_path.with_name(f"{base_path.stem}.metadata.json")
        csv_path = base_path.with_name(f"{base_path.stem}_routing.csv")

        # 1. Save NPZ arrays
        np.savez_compressed(
            npz_path,
            slope=self.slope_grid,
            elevation_m=self.grid.elevation_m,
            flow_dirs=np.array([c.direction or "" for c in self.cells.values()]),
            downstreams=np.array([c.downstream_cell or "" for c in self.cells.values()]),
            states=np.array([c.state for c in self.cells.values()]),
        )

        # 2. Save metadata JSON
        val = self.validate_d8()
        metadata = {
            "grid_id": self.grid.metadata.get("grid_id"),
            "catchment_id": self.grid.metadata.get("catchment_id"),
            "grid_version": self.grid.metadata.get("grid_version"),
            "layer": "Layer 2 — DEM + D8 Terrain",
            "resolution_m": self.grid.resolution_m,
            "crs": self.grid.crs,
            "total_cells": self.grid.total_cells,
            "valid_cells": self.valid_cell_count,
            "downstream_cells": val["downstream_count"],
            "outlet_cells": val["outlet_count"],
            "boundary_cells": val["boundary_count"],
            "sink_cells": val["local_sink_count"] + val["flat_sink_count"],
            "validation_status": "PASS" if val["is_valid"] else "FAIL",
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # 3. Save CSV
        self.export_routing_table_csv(csv_path)

        return npz_path, json_path, csv_path
