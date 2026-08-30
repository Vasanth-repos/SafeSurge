"""
Slope-weighted 2D surface routing using D8 steepest-descent flow direction
with synchronous update rules and mass conservation.
"""

import math


def compute_surface_outflows(
    cell_storages: dict[int, float],
    flow_dir: dict[int, int | None],
    elevations: dict[int, float],
    cell_positions: dict[int, tuple[int, int]],
    dt: float = 60.0,
    k: float = 0.1,
    f_max: float = 0.5,
    cell_size_m: float = 10.0,
) -> tuple[dict[int, float], dict[int, float], float]:
    """
    PASS 1: Compute surface water transfers between cells based on snapshot storage at time t.
    Returns:
      - internal_transfers: Dict[cell_id, outflow_to_downstream_cell_m3]
      - cell_inflows: Dict[cell_id, total_inflow_from_upstream_cells_m3]
      - boundary_outflow_total: total m3 escaping beyond catchment boundary
    """
    internal_outflows: dict[int, float] = {cid: 0.0 for cid in cell_storages}
    cell_inflows: dict[int, float] = {cid: 0.0 for cid in cell_storages}
    boundary_outflow_total: float = 0.0

    for cid, storage in cell_storages.items():
        if storage <= 1e-9:
            continue

        downstream_id = flow_dir.get(cid)
        curr_elev = elevations[cid]

        if downstream_id is None or downstream_id not in elevations:
            # Boundary sink / edge cell
            # A fraction escapes boundary depending on edge gradient or default small slope
            f_boundary = min(f_max, k * math.sqrt(0.01) * dt)
            out = f_boundary * storage
            internal_outflows[cid] = out
            boundary_outflow_total += out
            continue

        down_elev = elevations[downstream_id]
        r1, c1 = cell_positions[cid]
        r2, c2 = cell_positions[downstream_id]
        dr, dc = abs(r1 - r2), abs(c1 - c2)
        dist = cell_size_m * (1.41421356 if (dr > 0 and dc > 0) else 1.0)

        drop = curr_elev - down_elev
        slope = max(0.0, drop / max(dist, 1.0))

        # f = clip(k * sqrt(slope) * dt, 0, f_max)
        fraction = min(f_max, max(0.0, k * math.sqrt(slope) * dt))
        outflow_m3 = fraction * storage

        internal_outflows[cid] = outflow_m3
        cell_inflows[downstream_id] += outflow_m3

    return internal_outflows, cell_inflows, boundary_outflow_total
