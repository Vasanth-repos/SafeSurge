"""
Layer 9 — Water Depth Engine & Spatial Road Inundation Field:
Transforms surface flood storage (m³) into cell-average water depth (m/cm)
and projects modeled depths onto GIS road geometries via area-weighted spatial overlay.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import transform

EPSILON_AREA_M2 = 1e-9
EPSILON_STORAGE_M3 = 1e-9
EPSILON_DEPTH_M = 1e-9


def validate_metric_crs(crs_string: str) -> None:
    crs = CRS.from_user_input(crs_string)
    if not crs.is_projected:
        raise ValueError(f"Layer 9 requires a projected metric CRS, got geographic/unprojected: {crs_string}")


def validate_storage(storage_m3: float) -> float:
    if isinstance(storage_m3, bool):
        raise ValueError("Storage must be numeric.")

    try:
        val = float(storage_m3)
    except (TypeError, ValueError) as exc:
        raise ValueError("Storage must be numeric.") from exc

    if not math.isfinite(val):
        raise ValueError("Storage must be finite.")

    if val < -EPSILON_STORAGE_M3:
        raise ValueError(f"Negative surface storage encountered: {val} m³.")

    return max(0.0, val)


def validate_cell_area(cell: Any, tolerance_m2: float = 0.01) -> None:
    geom = getattr(cell, "geometry", None)
    area = getattr(cell, "area_m2", None)
    if geom is not None and area is not None:
        geom_area = getattr(geom, "area", None)
        if geom_area is not None and abs(geom_area - area) > tolerance_m2:
            raise ValueError(
                f"Area mismatch for cell {getattr(cell, 'cell_id', 'unknown')}: "
                f"metadata area={area} m², geometry area={geom_area} m²"
            )


def storage_to_depth_m(storage_m3: float, area_m2: float) -> float:
    storage = validate_storage(storage_m3)
    if isinstance(area_m2, bool):
        raise ValueError("Area must be numeric.")

    try:
        area = float(area_m2)
    except (TypeError, ValueError) as exc:
        raise ValueError("Area must be numeric.") from exc

    if not math.isfinite(area):
        raise ValueError("Area must be finite.")

    if area <= EPSILON_AREA_M2:
        raise ValueError(f"Cell area must be > 0, got {area}")

    return storage / area


def depth_m_to_cm(depth_m: float) -> float:
    if isinstance(depth_m, bool):
        raise ValueError("Depth must be numeric.")

    val = float(depth_m)
    if val < -EPSILON_DEPTH_M:
        raise ValueError(f"Depth cannot be negative: {val}")

    return max(0.0, val) * 100.0


@dataclass(frozen=True)
class CellDepth:
    cell_id: str
    timestamp_seconds: int
    storage_m3: float
    area_m2: float
    depth_m: float
    depth_cm: float
    source: str = "MODEL"


def depth_field_cm(cell_depths: Mapping[str, CellDepth]) -> dict[str, float]:
    return {cell_id: result.depth_cm for cell_id, result in cell_depths.items()}


@dataclass(frozen=True)
class DepthThresholds:
    low_cm: float = 5.0
    moderate_cm: float = 15.0
    severe_cm: float = 30.0


def classify_depth(
    depth_cm: float,
    thresholds: DepthThresholds | None = None,
) -> str:
    t = thresholds or DepthThresholds()
    d = float(depth_cm)
    if d < t.low_cm:
        return "LOW"
    if d < t.moderate_cm:
        return "MODERATE"
    if d < t.severe_cm:
        return "SEVERE"
    return "CRITICAL"


@dataclass(frozen=True)
class RoadFeature:
    road_id: str
    geometry: object
    width_m: float | None = None
    source_crs: str = "EPSG:4326"
    width_source: str = "ASSUMED"

    def __post_init__(self):
        if not self.road_id:
            raise ValueError("road_id cannot be empty")
        if self.geometry is None:
            raise ValueError("geometry cannot be None")
        if getattr(self.geometry, "is_empty", False):
            raise ValueError(f"Road {self.road_id} geometry cannot be empty")
        if not getattr(self.geometry, "is_valid", True):
            raise ValueError(f"Road {self.road_id} geometry is invalid")

        if isinstance(self.geometry, (LineString, MultiLineString)):
            if self.width_m is None or self.width_m <= 0:
                raise ValueError(f"Line-based road '{self.road_id}' requires width_m > 0.")


@dataclass(frozen=True)
class RoadCellContribution:
    road_id: str
    cell_id: str
    intersection_area_m2: float
    cell_depth_cm: float


@dataclass(frozen=True)
class RoadDepth:
    road_id: str
    timestamp_seconds: int
    weighted_depth_m: float | None
    weighted_depth_cm: float | None
    max_intersecting_cell_depth_cm: float | None
    total_road_area_m2: float
    covered_road_area_m2: float
    coverage_fraction: float
    coverage_status: str  # "FULL", "PARTIAL", "NO_COVERAGE"
    source: str = "MODEL"


@dataclass(frozen=True)
class DepthResult:
    timestamp_seconds: int
    cells: dict[str, CellDepth]
    roads: dict[str, RoadDepth]
    source: str = "MODEL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_seconds": self.timestamp_seconds,
            "source": self.source,
            "cells": [
                {
                    "cell_id": cd.cell_id,
                    "storage_m3": round(cd.storage_m3, 6),
                    "area_m2": round(cd.area_m2, 2),
                    "depth_cm": round(cd.depth_cm, 4),
                }
                for cd in self.cells.values()
            ],
            "roads": [
                {
                    "road_id": rd.road_id,
                    "weighted_depth_cm": round(rd.weighted_depth_cm, 4) if rd.weighted_depth_cm is not None else None,
                    "max_intersecting_cell_depth_cm": round(rd.max_intersecting_cell_depth_cm, 4) if rd.max_intersecting_cell_depth_cm is not None else None,
                    "coverage_fraction": round(rd.coverage_fraction, 4),
                    "coverage_status": rd.coverage_status,
                }
                for rd in self.roads.values()
            ],
        }


def transform_geometry_to_grid(
    geometry: Any,
    source_crs: str,
    grid_crs: str,
) -> Any:
    src = CRS.from_user_input(source_crs)
    tgt = CRS.from_user_input(grid_crs)
    if src == tgt:
        return geometry
    transformer = Transformer.from_crs(src, tgt, always_xy=True)
    return transform(transformer.transform, geometry)


def road_to_polygon(
    geometry: Any,
    width_m: float | None,
) -> Any:
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry

    if isinstance(geometry, (LineString, MultiLineString)):
        if width_m is None or width_m <= 0:
            raise ValueError("Line-based road requires positive width_m.")
        return geometry.buffer(width_m / 2.0)

    raise ValueError(f"Unsupported road geometry type: {type(geometry)}")


class DepthEngine:
    def __init__(
        self,
        grid_crs: str = "EPSG:32644",
        full_coverage_threshold: float = 0.95,
    ):
        validate_metric_crs(grid_crs)
        self.grid_crs = grid_crs
        self.full_coverage_threshold = float(full_coverage_threshold)

    def compute_cell_depths(
        self,
        grid: Any,
        surface_storage_m3_by_cell: Mapping[str, float],
        timestamp_seconds: int,
    ) -> dict[str, CellDepth]:
        # Validate unknown cell IDs
        if hasattr(grid, "cells"):
            grid_cell_map = grid.cells
        elif hasattr(grid, "iter_cells"):
            grid_cell_map = {c.cell_id: c for c in grid.iter_cells()}
        else:
            raise AttributeError("Grid must expose 'cells' mapping or 'iter_cells()' method.")

        grid_ids = set(grid_cell_map.keys())
        unknown = set(surface_storage_m3_by_cell.keys()) - grid_ids
        if unknown:
            raise ValueError(f"Unknown cell IDs in storage input: {sorted(unknown)}")

        results: dict[str, CellDepth] = {}
        for cid, cell in grid_cell_map.items():
            storage = float(surface_storage_m3_by_cell.get(cid, 0.0))
            validate_cell_area(cell)

            area = float(getattr(cell, "area_m2", getattr(grid, "cell_area_m2", 100.0)))
            d_m = storage_to_depth_m(storage, area)
            d_cm = depth_m_to_cm(d_m)

            results[cid] = CellDepth(
                cell_id=cid,
                timestamp_seconds=int(timestamp_seconds),
                storage_m3=storage,
                area_m2=area,
                depth_m=d_m,
                depth_cm=d_cm,
                source="MODEL",
            )
        return results

    def compute_road_depths(
        self,
        cell_depths: Mapping[str, CellDepth],
        roads: Sequence[RoadFeature],
        timestamp_seconds: int,
        grid: Any,
    ) -> dict[str, RoadDepth]:
        # Build cell polygons dictionary
        cell_polys: dict[str, Polygon] = {}
        if hasattr(grid, "cells"):
            cells_iterable = grid.cells.values()
        elif hasattr(grid, "iter_cells"):
            cells_iterable = grid.iter_cells()
        else:
            cells_iterable = []

        res_m = float(getattr(grid, "resolution_m", 10.0))
        _ = res_m

        for cell in cells_iterable:
            cid = cell.cell_id
            geom = getattr(cell, "geometry", None)
            if geom is not None and isinstance(geom, (Polygon, MultiPolygon)):
                cell_polys[cid] = geom
            else:
                # Regular grid polygon fallback from cell center/coordinates
                # Coordinates in projected grid CRS
                r = getattr(cell, "row", 0)
                c = getattr(cell, "column", getattr(cell, "col", 0))
                min_x = c * res_m
                min_y = r * res_m
                max_x = min_x + res_m
                max_y = min_y + res_m
                cell_polys[cid] = Polygon([
                    (min_x, min_y),
                    (max_x, min_y),
                    (max_x, max_y),
                    (min_x, max_y),
                    (min_x, min_y),
                ])

        road_results: dict[str, RoadDepth] = {}

        for road in roads:
            # 1. Transform to grid CRS
            proj_geom = transform_geometry_to_grid(
                geometry=road.geometry,
                source_crs=road.source_crs,
                grid_crs=self.grid_crs,
            )

            # 2. Convert to road surface polygon
            road_poly = road_to_polygon(proj_geom, road.width_m)
            total_road_area = float(road_poly.area)

            if total_road_area <= EPSILON_AREA_M2:
                road_results[road.road_id] = RoadDepth(
                    road_id=road.road_id,
                    timestamp_seconds=int(timestamp_seconds),
                    weighted_depth_m=None,
                    weighted_depth_cm=None,
                    max_intersecting_cell_depth_cm=None,
                    total_road_area_m2=0.0,
                    covered_road_area_m2=0.0,
                    coverage_fraction=0.0,
                    coverage_status="NO_COVERAGE",
                    source="MODEL",
                )
                continue

            # 3. Intersect against computational cells
            covered_area = 0.0
            weighted_depth_m_accum = 0.0
            max_depth_cm: float | None = None

            for cid, c_poly in cell_polys.items():
                if not road_poly.intersects(c_poly):
                    continue

                inter = road_poly.intersection(c_poly)
                inter_area = float(inter.area)
                if inter_area <= EPSILON_AREA_M2:
                    continue

                c_depth = cell_depths[cid]
                covered_area += inter_area
                weighted_depth_m_accum += inter_area * c_depth.depth_m

                if max_depth_cm is None or c_depth.depth_cm > max_depth_cm:
                    max_depth_cm = c_depth.depth_cm

            # 4. Compute coverage and weighted depth
            cov_fraction = min(1.0, max(0.0, covered_area / total_road_area))
            if covered_area <= EPSILON_AREA_M2:
                cov_status = "NO_COVERAGE"
                weighted_m = None
                weighted_cm = None
            elif cov_fraction >= self.full_coverage_threshold:
                cov_status = "FULL"
                weighted_m = weighted_depth_m_accum / covered_area
                weighted_cm = weighted_m * 100.0
            else:
                cov_status = "PARTIAL"
                weighted_m = weighted_depth_m_accum / covered_area
                weighted_cm = weighted_m * 100.0

            road_results[road.road_id] = RoadDepth(
                road_id=road.road_id,
                timestamp_seconds=int(timestamp_seconds),
                weighted_depth_m=weighted_m,
                weighted_depth_cm=weighted_cm,
                max_intersecting_cell_depth_cm=max_depth_cm,
                total_road_area_m2=total_road_area,
                covered_road_area_m2=covered_area,
                coverage_fraction=cov_fraction,
                coverage_status=cov_status,
                source="MODEL",
            )

        return road_results

    def compute(
        self,
        grid: Any,
        surface_storage_m3_by_cell: Mapping[str, float],
        roads: Sequence[RoadFeature],
        timestamp_seconds: int,
    ) -> DepthResult:
        cells = self.compute_cell_depths(
            grid=grid,
            surface_storage_m3_by_cell=surface_storage_m3_by_cell,
            timestamp_seconds=timestamp_seconds,
        )
        roads_res = self.compute_road_depths(
            cell_depths=cells,
            roads=roads,
            timestamp_seconds=timestamp_seconds,
            grid=grid,
        )
        return DepthResult(
            timestamp_seconds=int(timestamp_seconds),
            cells=cells,
            roads=roads_res,
            source="MODEL",
        )
