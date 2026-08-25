"""
DEM Preprocessing: Priority Flood Fill (Depression Filling) and D8 Flow Direction Assignment.
"""

from typing import Dict, List, Optional, Tuple
import heapq
import numpy as np


def cell_to_id(r: int, c: int, cols: int) -> int:
    return r * cols + c


def id_to_cell(cell_id: int, cols: int) -> Tuple[int, int]:
    return divmod(cell_id, cols)


def priority_flood_fill(elevation_grid: np.ndarray) -> np.ndarray:
    """
    Priority-flood algorithm to remove local depressions/pits in DEM.
    Maintains water flow continuity from boundaries inward.
    """
    rows, cols = elevation_grid.shape
    filled = np.full_like(elevation_grid, fill_value=np.inf, dtype=np.float64)
    visited = np.zeros((rows, cols), dtype=bool)

    # Min-priority queue of (elevation, r, c)
    pq: List[Tuple[float, int, int]] = []

    # Initialize with all boundary cells
    for r in range(rows):
        for c in (0, cols - 1):
            if not visited[r, c]:
                visited[r, c] = True
                filled[r, c] = float(elevation_grid[r, c])
                heapq.heappush(pq, (filled[r, c], r, c))

    for c in range(cols):
        for r in (0, rows - 1):
            if not visited[r, c]:
                visited[r, c] = True
                filled[r, c] = float(elevation_grid[r, c])
                heapq.heappush(pq, (filled[r, c], r, c))

    # 8-neighbor offsets
    d_rows = [-1, -1, -1, 0, 0, 1, 1, 1]
    d_cols = [-1, 0, 1, -1, 1, -1, 0, 1]

    while pq:
        h, r, c = heapq.heappop(pq)
        for dr, dc in zip(d_rows, d_cols):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                visited[nr, nc] = True
                # Elevate pit neighbor if lower than current spillway height
                neighbor_orig = float(elevation_grid[nr, nc])
                filled[nr, nc] = max(h, neighbor_orig)
                heapq.heappush(pq, (filled[nr, nc], nr, nc))

    return filled


def compute_d8_flow_directions(
    elevation_grid: np.ndarray, cell_size_m: float = 10.0
) -> Dict[int, Optional[int]]:
    """
    Computes D8 flow direction for each cell to its steepest descent neighbor.
    Returns mapping: cell_id -> downstream_neighbor_cell_id (or None if boundary sink/outlet).
    """
    rows, cols = elevation_grid.shape
    flow_dir: Dict[int, Optional[int]] = {}

    d_rows = [-1, -1, -1, 0, 0, 1, 1, 1]
    d_cols = [-1, 0, 1, -1, 1, -1, 0, 1]
    # Distances for 8 directions (orthogonal = 1.0, diagonal = sqrt(2))
    distances = [
        cell_size_m * (1.41421356 if dr != 0 and dc != 0 else 1.0)
        for dr, dc in zip(d_rows, d_cols)
    ]

    for r in range(rows):
        for c in range(cols):
            cid = cell_to_id(r, c, cols)
            curr_elev = elevation_grid[r, c]

            max_slope = 0.0
            steepest_neighbor_id: Optional[int] = None

            for dr, dc, dist in zip(d_rows, d_cols, distances):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    drop = curr_elev - elevation_grid[nr, nc]
                    if drop > 0:
                        slope = drop / dist
                        if slope > max_slope:
                            max_slope = slope
                            steepest_neighbor_id = cell_to_id(nr, nc, cols)

            flow_dir[cid] = steepest_neighbor_id

    return flow_dir
