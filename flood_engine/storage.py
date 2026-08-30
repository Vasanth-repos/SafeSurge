"""
Cell storage and synchronous water balance state management.
"""



class GridCellState:
    def __init__(
        self,
        cell_id: int,
        row: int,
        col: int,
        elevation: float,
        cn_value: float = 75.0,
        area_m2: float = 100.0,
    ):
        self.cell_id = cell_id
        self.row = row
        self.col = col
        self.elevation = elevation
        self.cn_value = cn_value
        self.area_m2 = area_m2

        self.storage_m3: float = 0.0
        self.depth_cm: float = 0.0
        self.inflow_m3: float = 0.0
        self.outflow_m3: float = 0.0
        self.drained_m3: float = 0.0
        self.runoff_m3: float = 0.0

    def update_depth(self):
        self.depth_cm = (self.storage_m3 / self.area_m2) * 100.0


def synchronous_storage_update(
    cells: dict[int, GridCellState],
    incremental_runoffs: dict[int, float],
    surface_inflows: dict[int, float],
    surface_outflows: dict[int, float],
    drain_captures: dict[int, float],
) -> None:
    """
    Applies the conservation-governed storage update across all cells synchronously:
    S_{t+1} = max(0, S_t + Runoff_t + Inflow_t - Outflow_t - DrainCapture_t)
    """
    next_storages: dict[int, float] = {}

    for cid, cell in cells.items():
        r_in = incremental_runoffs.get(cid, 0.0)
        s_in = surface_inflows.get(cid, 0.0)
        s_out = surface_outflows.get(cid, 0.0)
        d_cap = drain_captures.get(cid, 0.0)

        # Available water before exit
        available = cell.storage_m3 + r_in + s_in

        # Safeguard: cannot drain/exit more water than available
        total_exit = s_out + d_cap
        if total_exit > available and total_exit > 1e-9:
            scale = available / total_exit
            s_out *= scale
            d_cap *= scale

        s_next = max(0.0, available - s_out - d_cap)
        next_storages[cid] = s_next

        # Record timestep diagnostics
        cell.runoff_m3 = r_in
        cell.inflow_m3 = s_in
        cell.outflow_m3 = s_out
        cell.drained_m3 = d_cap

    # Commit snapshot to all cells
    for cid, cell in cells.items():
        cell.storage_m3 = next_storages[cid]
        cell.update_depth()
