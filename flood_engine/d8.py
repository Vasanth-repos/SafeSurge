"""
Layer 2 (Hardened) — DEM + D8 Terrain Flow Analysis Engine:
Deterministic 8-neighbor downslope routing with explicit terminal semantics,
flow distances, dimensionless slope ratios, terrain QA diagnostics, and multi-outlet support.
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
    slope_ratio: float          # Dimensionless slope ratio (dz / distance)
    flow_distance_m: float      # Distance to downstream cell (m)
    downstream_cell: Optional[str]
    direction: Optional[str]
    state: str                  # 'downstream', 'outlet', 'boundary_exit', 'local_sink', 'flat_sink'
    is_boundary: bool
    is_outlet: bool

    @property
    def slope(self) -> float:
        """Backwards-compatible alias for slope_ratio."""
        return self.slope_ratio


class D8Terrain:
    def __init__(
        self,
        grid: ComputationalGrid,
        cells: Dict[str, D8Cell],
        slope_grid: np.ndarray,
        flow_distance_grid: np.ndarray,
        flow_dir_grid: np.ndarray,
        downstream_grid: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.grid = grid
        self.cells = cells
        self.slope_grid = slope_grid
        self.flow_distance_grid = flow_distance_grid
        self.flow_dir_grid = flow_dir_grid
        self.downstream_grid = downstream_grid
        self.metadata = metadata or {}

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
        Computes D8 steepest-descent flow direction, slope ratio, flow distance,
        and terminal states for all valid cells in the computational grid.
        """
        rows, cols = grid.rows, grid.columns
        res = grid.resolution_m

        slope_grid = np.zeros((rows, cols), dtype=np.float64)
        flow_distance_grid = np.zeros((rows, cols), dtype=np.float64)
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

                # 1. Check if designated as explicit catchment outlet
                if is_outlet:
                    slope_grid[r, c] = 0.0
                    flow_distance_grid[r, c] = 0.0
                    flow_dir_grid[r, c] = None
                    downstream_grid[r, c] = None
                    cells_dict[cell_id] = D8Cell(
                        cell_id=cell_id,
                        row=r,
                        col=c,
                        elevation_m=curr_elev,
                        slope_ratio=0.0,
                        flow_distance_m=0.0,
                        downstream_cell=None,
                        direction=None,
                        state="outlet",
                        is_boundary=is_boundary,
                        is_outlet=True,
                    )
                    continue

                # 2. Inspect 8 neighbors in fixed deterministic order
                best_slope = 0.0
                best_dist = 0.0
                best_dir: Optional[str] = None
                best_downstream_id: Optional[str] = None
                has_equal_neighbor = False

                for direction_name, dr, dc, dist_factor in NEIGHBOR_ORDER:
                    nr, nc = r + dr, c + dc
                    distance_m = res * dist_factor

                    # Check domain bounds and validity
                    if not (0 <= nr < rows and 0 <= nc < cols):
                        continue
                    if not grid.valid_mask[nr, nc]:
                        continue

                    neighbor_elev = float(grid.elevation_m[nr, nc])
                    dz = curr_elev - neighbor_elev

                    if dz > 1e-9:
                        slope = dz / distance_m
                        # Strictly greater slope selects new steepest neighbor (tie-breaks to first encountered)
                        if slope > best_slope:
                            best_slope = slope
                            best_dist = distance_m
                            best_dir = direction_name
                            best_downstream_id = grid.indices_to_cell_id(nr, nc)
                    elif abs(dz) <= 1e-9:
                        has_equal_neighbor = True

                # 3. Classify terminal state
                if best_downstream_id is not None and best_slope > 0.0:
                    state = "downstream"
                elif is_boundary:
                    state = "boundary_exit"
                elif has_equal_neighbor:
                    state = "flat_sink"
                else:
                    state = "local_sink"

                slope_grid[r, c] = best_slope
                flow_distance_grid[r, c] = best_dist
                flow_dir_grid[r, c] = best_dir
                downstream_grid[r, c] = best_downstream_id

                cells_dict[cell_id] = D8Cell(
                    cell_id=cell_id,
                    row=r,
                    col=c,
                    elevation_m=curr_elev,
                    slope_ratio=best_slope,
                    flow_distance_m=best_dist,
                    downstream_cell=best_downstream_id,
                    direction=best_dir,
                    state=state,
                    is_boundary=is_boundary,
                    is_outlet=is_outlet,
                )

        terrain = cls(
            grid=grid,
            cells=cells_dict,
            slope_grid=slope_grid,
            flow_distance_grid=flow_distance_grid,
            flow_dir_grid=flow_dir_grid,
            downstream_grid=downstream_grid,
        )
        terrain.metadata = terrain.generate_qa_metadata()
        return terrain

    def generate_qa_metadata(self) -> Dict[str, Any]:
        """Calculates comprehensive terrain QA diagnostics and carries Layer 1 provenance."""
        val = self.validate_d8()
        slopes = [c.slope_ratio for c in self.cells.values() if c.state == "downstream"]
        elevations = [c.elevation_m for c in self.cells.values()]
        total_valid = len(self.cells)

        return {
            "grid_id": self.grid.metadata.get("grid_id"),
            "catchment_id": self.grid.metadata.get("catchment_id"),
            "grid_version": self.grid.metadata.get("grid_version"),
            "layer": "Layer 2 (Hardened) — DEM + D8 Terrain",
            "source_dem": self.grid.metadata.get("source_dem"),
            "vertical_units": "meters",
            "horizontal_units": "meters",
            "crs": self.grid.crs,
            "resolution_m": self.grid.resolution_m,
            "total_cells": self.grid.total_cells,
            "valid_cells": total_valid,
            "elevation_min_m": round(float(min(elevations)), 3) if elevations else 0.0,
            "elevation_max_m": round(float(max(elevations)), 3) if elevations else 0.0,
            "mean_slope_ratio": round(float(np.mean(slopes)), 6) if slopes else 0.0,
            "max_slope_ratio": round(float(np.max(slopes)), 6) if slopes else 0.0,
            "downstream_count": val["downstream_count"],
            "downstream_pct": round((val["downstream_count"] / max(1, total_valid)) * 100, 2),
            "outlet_count": val["outlet_count"],
            "outlet_pct": round((val["outlet_count"] / max(1, total_valid)) * 100, 2),
            "boundary_exit_count": val["boundary_exit_count"],
            "boundary_exit_pct": round((val["boundary_exit_count"] / max(1, total_valid)) * 100, 2),
            "local_sink_count": val["local_sink_count"],
            "local_sink_pct": round((val["local_sink_count"] / max(1, total_valid)) * 100, 2),
            "flat_sink_count": val["flat_sink_count"],
            "flat_sink_pct": round((val["flat_sink_count"] / max(1, total_valid)) * 100, 2),
            "validation_status": "PASS" if val["is_valid"] else "FAIL",
            "depression_policy": "Preserve potential real urban depressions; DEM conditioning is preprocessing only.",
        }

    def trace_to_terminal(self, start_cell_id: str, max_steps: int = 1000) -> List[str]:
        """
        Traces continuous downstream flow path until a terminal state is reached
        (outlet, boundary_exit, local_sink, or flat_sink).
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
        3. Slopes and flow distances are strictly non-negative.
        4. Outlets, boundary exits, and sinks have no downstream targets.
        5. Boundary exits must be valid boundary cells.
        """
        total_valid = len(self.cells)
        downstream_count = 0
        outlet_count = 0
        boundary_exit_count = 0
        sink_count = 0
        flat_count = 0
        violations = []

        valid_states = {"downstream", "outlet", "boundary_exit", "boundary", "local_sink", "flat_sink"}

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
                    if cell.slope_ratio <= 0.0:
                        violations.append(f"Cell {cid} downstream slope <= 0")
                    if cell.flow_distance_m <= 0.0:
                        violations.append(f"Cell {cid} downstream flow distance <= 0")

            elif cell.state == "outlet":
                outlet_count += 1
                if cell.downstream_cell is not None:
                    violations.append(f"Outlet cell {cid} must not have downstream target")

            elif cell.state in ("boundary_exit", "boundary"):
                boundary_exit_count += 1
                if not cell.is_boundary:
                    violations.append(f"Cell {cid} classified boundary exit but is_boundary=False")
                if cell.downstream_cell is not None:
                    violations.append(f"Boundary exit cell {cid} must not have downstream target")

            elif cell.state == "local_sink":
                sink_count += 1
                if cell.downstream_cell is not None:
                    violations.append(f"Sink cell {cid} must not have downstream target")

            elif cell.state == "flat_sink":
                flat_count += 1
                if cell.downstream_cell is not None:
                    violations.append(f"Flat sink cell {cid} must not have downstream target")

        is_valid = len(violations) == 0
        return {
            "is_valid": is_valid,
            "total_valid_cells": total_valid,
            "downstream_count": downstream_count,
            "outlet_count": outlet_count,
            "boundary_exit_count": boundary_exit_count,
            "local_sink_count": sink_count,
            "flat_sink_count": flat_count,
            "violation_count": len(violations),
            "violations": violations[:10],
        }

    def export_routing_table_csv(self, output_csv_path: Union[str, Path]) -> Path:
        """
        Exports human-readable routing mapping:
        cell_id, row, col, elevation_m, slope_ratio, flow_distance_m, direction, downstream_cell, state, is_boundary, is_outlet
        """
        csv_path = Path(output_csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "cell_id", "row", "col", "elevation_m", "slope_ratio",
                "flow_distance_m", "direction", "downstream_cell", "state", "is_boundary", "is_outlet"
            ])
            for cid in sorted(self.cells.keys()):
                c = self.cells[cid]
                writer.writerow([
                    c.cell_id, c.row, c.col, round(c.elevation_m, 4),
                    round(c.slope_ratio, 6), round(c.flow_distance_m, 2),
                    c.direction or "", c.downstream_cell or "",
                    c.state, c.is_boundary, c.is_outlet
                ])

        return csv_path

    def save_to_file(self, output_path: Union[str, Path]) -> Tuple[Path, Path, Path]:
        """Saves D8 terrain artifacts: .npz arrays, .metadata.json provenance, and .csv routing table."""
        base_path = Path(output_path)
        base_path.parent.mkdir(parents=True, exist_ok=True)
        npz_path = base_path.with_suffix(".npz")
        json_path = base_path.with_name(f"{base_path.stem}.metadata.json")
        csv_path = base_path.with_name(f"{base_path.stem}_routing.csv")

        # 1. Save NPZ arrays
        np.savez_compressed(
            npz_path,
            slope_ratio=self.slope_grid,
            flow_distance_m=self.flow_distance_grid,
            elevation_m=self.grid.elevation_m,
            flow_dirs=np.array([c.direction or "" for c in self.cells.values()]),
            downstreams=np.array([c.downstream_cell or "" for c in self.cells.values()]),
            states=np.array([c.state for c in self.cells.values()]),
        )

        # 2. Save metadata JSON
        self.metadata = self.generate_qa_metadata()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)

        # 3. Save CSV
        self.export_routing_table_csv(csv_path)

        return npz_path, json_path, csv_path
