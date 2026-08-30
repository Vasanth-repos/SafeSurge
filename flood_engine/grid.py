"""
ComputationalGrid: Spatial domain representation distinguishing catchment boundaries,
DEM nodata, boundary cells, and outlets with O(1) cell lookup and provenance metadata.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class GridCell:
    cell_id: str
    row: int
    col: int
    elevation_m: float
    latitude: float
    longitude: float
    area_m2: float
    is_catchment: bool
    is_nodata: bool
    is_valid: bool
    is_boundary: bool
    is_outlet: bool


class ComputationalGrid:
    def __init__(
        self,
        elevation_m: np.ndarray,
        latitude: np.ndarray,
        longitude: np.ndarray,
        resolution_m: float = 10.0,
        crs: str = "EPSG:32644",
        catchment_mask: np.ndarray | None = None,
        dem_nodata_mask: np.ndarray | None = None,
        boundary_mask: np.ndarray | None = None,
        outlet_mask: np.ndarray | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.elevation_m = np.asarray(elevation_m, dtype=np.float64)
        self.latitude = np.asarray(latitude, dtype=np.float64)
        self.longitude = np.asarray(longitude, dtype=np.float64)
        self.rows, self.columns = self.elevation_m.shape
        self.resolution_m = float(resolution_m)
        self.cell_area_m2 = float(self.resolution_m ** 2)
        self.crs = str(crs)

        # 1. Catchment vs DEM Nodata separation
        if catchment_mask is not None:
            self.catchment_mask = np.asarray(catchment_mask, dtype=bool)
        else:
            self.catchment_mask = np.ones((self.rows, self.columns), dtype=bool)

        if dem_nodata_mask is not None:
            self.dem_nodata_mask = np.asarray(dem_nodata_mask, dtype=bool)
        else:
            self.dem_nodata_mask = ~np.isfinite(self.elevation_m) | (self.elevation_m < -9000.0)

        # Valid computational cell = inside catchment AND valid DEM
        self.valid_mask = self.catchment_mask & (~self.dem_nodata_mask)

        # 2. Boundary Mask
        if boundary_mask is not None:
            self.boundary_mask = np.asarray(boundary_mask, dtype=bool) & self.valid_mask
        else:
            self.boundary_mask = self.compute_boundary_mask()

        # 3. Outlet Mask
        if outlet_mask is not None:
            self.outlet_mask = np.asarray(outlet_mask, dtype=bool) & self.boundary_mask
        else:
            self.outlet_mask = np.zeros((self.rows, self.columns), dtype=bool)

        # 4. Metadata & Provenance
        self.metadata = metadata or {
            "grid_id": f"GRID_{self.rows}x{self.columns}_{int(self.resolution_m)}M_V1",
            "catchment_id": "DEMO_CATCHMENT",
            "grid_version": "1.0.0",
            "source_dem": "synthetic_or_processed",
            "vertical_units": "meters",
            "horizontal_units": "meters",
            "crs": self.crs,
            "resolution_m": self.resolution_m,
        }

        self.validate_grid()

    @property
    def total_cells(self) -> int:
        return self.rows * self.columns

    @property
    def valid_cells_count(self) -> int:
        return int(np.sum(self.valid_mask))

    def validate_grid(self):
        """Validates numerical integrity of the computational grid."""
        if self.elevation_m.ndim != 2:
            raise ValueError(f"elevation_m must be 2D array, got {self.elevation_m.ndim}D")
        if self.latitude.shape != (self.rows, self.columns):
            raise ValueError("latitude array shape does not match elevation shape")
        if self.longitude.shape != (self.rows, self.columns):
            raise ValueError("longitude array shape does not match elevation shape")
        if self.resolution_m <= 0:
            raise ValueError(f"resolution_m must be positive, got {self.resolution_m}")
        if not np.any(self.valid_mask):
            raise ValueError("Grid contains no valid computational cells.")

    def compute_boundary_mask(self) -> np.ndarray:
        """
        Derives boundary cells: valid catchment cells that have at least one 8-neighbor
        outside the catchment domain or outside the grid extent.
        """
        b_mask = np.zeros((self.rows, self.columns), dtype=bool)
        d_rows = [-1, -1, -1, 0, 0, 1, 1, 1]
        d_cols = [-1, 0, 1, -1, 1, -1, 0, 1]

        for r in range(self.rows):
            for c in range(self.columns):
                if not self.valid_mask[r, c]:
                    continue

                # Check 8-neighbors
                is_edge = False
                for dr, dc in zip(d_rows, d_cols):
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < self.rows and 0 <= nc < self.columns):
                        is_edge = True
                        break
                    if not self.valid_mask[nr, nc]:
                        is_edge = True
                        break

                if is_edge:
                    b_mask[r, c] = True

        return b_mask

    def set_outlets(self, outlets: list[str | tuple[int, int]]) -> None:
        """
        Assigns explicit catchment outlets.
        Validates:
        1. Cell is within catchment domain
        2. Cell has valid DEM elevation
        3. Cell lies on the catchment boundary
        """
        self.outlet_mask.fill(False)
        for out in outlets:
            if isinstance(out, str):
                r, c = self.cell_id_to_indices(out)
            else:
                r, c = out

            if not (0 <= r < self.rows and 0 <= c < self.columns):
                raise ValueError(f"Outlet ({r}, {c}) is outside grid bounds.")

            if not self.catchment_mask[r, c]:
                raise ValueError(f"Outlet at ({r}, {c}) is outside the modeled catchment polygon.")

            if self.dem_nodata_mask[r, c]:
                raise ValueError(f"Outlet at ({r}, {c}) has no valid DEM elevation data (nodata).")

            if not self.boundary_mask[r, c]:
                raise ValueError(f"Outlet at ({r}, {c}) must lie on the catchment boundary.")

            self.outlet_mask[r, c] = True

    def indices_to_cell_id(self, r: int, c: int) -> str:
        """Maps (row, col) to canonical string ID: C00001, C00002, etc."""
        index = r * self.columns + c + 1
        return f"C{index:05d}"

    def cell_id_to_indices(self, cell_id: str) -> tuple[int, int]:
        """Parses cell_id string back to (row, col) in O(1) time."""
        clean = cell_id.upper().replace("C", "")
        index = int(clean) - 1
        if index < 0 or index >= self.total_cells:
            raise IndexError(f"Cell ID {cell_id} out of bounds for grid with {self.total_cells} cells.")
        return divmod(index, self.columns)

    def get_cell(self, cell_id: str) -> GridCell:
        """Direct O(1) indexed cell retrieval."""
        r, c = self.cell_id_to_indices(cell_id)
        return GridCell(
            cell_id=cell_id,
            row=r,
            col=c,
            elevation_m=float(self.elevation_m[r, c]),
            latitude=float(self.latitude[r, c]),
            longitude=float(self.longitude[r, c]),
            area_m2=self.cell_area_m2,
            is_catchment=bool(self.catchment_mask[r, c]),
            is_nodata=bool(self.dem_nodata_mask[r, c]),
            is_valid=bool(self.valid_mask[r, c]),
            is_boundary=bool(self.boundary_mask[r, c]),
            is_outlet=bool(self.outlet_mask[r, c]),
        )

    @property
    def cells(self) -> dict[str, GridCell]:
        """Returns all valid computational cells in the grid indexed by cell_id."""
        cell_dict = {}
        for r in range(self.rows):
            for c in range(self.columns):
                if self.valid_mask[r, c]:
                    cid = self.indices_to_cell_id(r, c)
                    cell_dict[cid] = self.get_cell(cid)
        return cell_dict

    def iter_cells(self) -> list[GridCell]:
        """Iterates across all valid computational cells in the grid."""
        return list(self.cells.values())

    def save_to_file(self, output_path: str | Path) -> tuple[Path, Path]:
        """
        Exports the computational grid to a compressed .npz archive alongside a .json metadata sidecar.
        """
        base_path = Path(output_path)
        base_path.parent.mkdir(parents=True, exist_ok=True)
        npz_path = base_path.with_suffix(".npz")
        json_path = base_path.with_suffix(".json")

        np.savez_compressed(
            npz_path,
            elevation_m=self.elevation_m,
            latitude=self.latitude,
            longitude=self.longitude,
            catchment_mask=self.catchment_mask,
            dem_nodata_mask=self.dem_nodata_mask,
            boundary_mask=self.boundary_mask,
            outlet_mask=self.outlet_mask,
        )

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)

        return npz_path, json_path

    @classmethod
    def load_from_file(cls, path: str | Path) -> "ComputationalGrid":
        """Loads a ComputationalGrid from .npz and .json artifacts."""
        base_path = Path(path)
        npz_path = base_path.with_suffix(".npz")
        json_path = base_path.with_suffix(".json")

        if not npz_path.exists():
            raise FileNotFoundError(f"Grid data archive not found: {npz_path}")

        data = np.load(npz_path)
        meta = {}
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

        res_m = float(meta.get("resolution_m", 10.0))
        crs = str(meta.get("crs", "EPSG:32644"))

        return cls(
            elevation_m=data["elevation_m"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            resolution_m=res_m,
            crs=crs,
            catchment_mask=data["catchment_mask"],
            dem_nodata_mask=data["dem_nodata_mask"],
            boundary_mask=data["boundary_mask"],
            outlet_mask=data["outlet_mask"],
            metadata=meta,
        )

    @classmethod
    def create_synthetic_demo_grid(
        cls,
        rows: int = 20,
        cols: int = 20,
        resolution_m: float = 10.0,
        crs: str = "EPSG:32644",
    ) -> "ComputationalGrid":
        """
        Creates the standard Layer 1 demonstration grid with defined catchment boundary,
        natural valley topography, and an outfall outlet.
        """
        elevation = np.zeros((rows, cols), dtype=np.float64)
        lat = np.zeros((rows, cols), dtype=np.float64)
        lon = np.zeros((rows, cols), dtype=np.float64)
        catchment = np.ones((rows, cols), dtype=bool)
        nodata = np.zeros((rows, cols), dtype=bool)

        for r in range(rows):
            for c in range(cols):
                base_elev = 30.0 - 0.7 * r - 0.5 * c
                valley_dist = abs(r - c)
                valley_dip = max(0.0, 3.5 - 0.5 * valley_dist)
                elevation[r, c] = max(10.0, base_elev - valley_dip)
                # Metric or geographic coordinates
                lat[r, c] = float(r * resolution_m)
                lon[r, c] = float(c * resolution_m)

        # Carve small non-catchment corners for realistic boundary polygon test
        catchment[0, cols - 1] = False
        catchment[0, cols - 2] = False

        grid = cls(
            elevation_m=elevation,
            latitude=lat,
            longitude=lon,
            resolution_m=resolution_m,
            crs=crs,
            catchment_mask=catchment,
            dem_nodata_mask=nodata,
            metadata={
                "grid_id": "SYNTHETIC_DEMO_20x20_10M_V1",
                "catchment_id": "CHENNAI_URBAN_DEMO",
                "grid_version": "1.1.0",
                "source_dem": "synthetic_hypsometry",
                "vertical_units": "meters",
                "crs": crs,
                "resolution_m": resolution_m,
            },
        )

        # Set designated primary catchment outlet at the lowest boundary cell (19, 19)
        grid.set_outlets([(rows - 1, cols - 1)])
        return grid
