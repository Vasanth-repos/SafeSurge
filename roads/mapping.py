"""
Layer 17 — Road-Cell Spatial Intersection Mapper:
Maps linear or polygon road GIS geometries to computational grid cells using Shapely STRtree indexing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from roads.models import Road, RoadCellExposure


class RoadSpatialMapper:
    def __init__(
        self,
        roads: Sequence[Road],
        cell_geometries: Mapping[str, BaseGeometry],
    ):
        self.roads = {r.road_id: r for r in roads}
        self.cell_geometries = dict(cell_geometries)

        # Build STRtree spatial index over cells
        self.cell_ids = list(self.cell_geometries.keys())
        self.cell_geom_list = [self.cell_geometries[cid] for cid in self.cell_ids]
        self.tree = STRtree(self.cell_geom_list)

        # Precompute road-cell exposures
        self._exposures_by_road: dict[str, list[RoadCellExposure]] = {}
        self._precompute_exposures()

    def _precompute_exposures(self) -> None:
        for r_id, road in self.roads.items():
            exposures: list[RoadCellExposure] = []
            if road.length_m <= 0:
                continue

            # Query candidate intersecting cells via STRtree
            candidate_indices = self.tree.query(road.geometry)
            for idx in candidate_indices:
                cell_id = self.cell_ids[idx]
                cell_geom = self.cell_geom_list[idx]

                if road.geometry.intersects(cell_geom):
                    inter = road.geometry.intersection(cell_geom)
                    inter_len = inter.length if hasattr(inter, "length") else 0.0
                    if inter_len > 0:
                        frac = inter_len / road.length_m
                        exposures.append(
                            RoadCellExposure(
                                road_id=r_id,
                                cell_id=cell_id,
                                intersection_length_m=inter_len,
                                exposure_fraction=frac,
                            )
                        )

            self._exposures_by_road[r_id] = exposures

    def get_exposures(self, road_id: str) -> list[RoadCellExposure]:
        return self._exposures_by_road.get(road_id, [])

    def get_all_exposures(self) -> dict[str, list[RoadCellExposure]]:
        return dict(self._exposures_by_road)
