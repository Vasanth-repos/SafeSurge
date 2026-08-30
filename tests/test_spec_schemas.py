"""
Schema Compliance Tests for SafeSurge / AURA-FLOOD Spec Section 15.
Verifies all standard datasets have exact required headers and properties.
"""

import csv
import json
import os

import pytest

from data.export_schemas import OUTPUT_DIR, generate_all_spec_datasets


@pytest.fixture(scope="module")
def spec_data_files():
    """Ensure datasets are generated."""
    return generate_all_spec_datasets(OUTPUT_DIR)


def test_rainfall_csv_schema(spec_data_files):
    """rainfall.csv: timestamp, cell_id, latitude, longitude, rainfall_mm, rainfall_rate_mm_hr"""
    p = spec_data_files["rainfall.csv"]
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        expected = ["timestamp", "cell_id", "latitude", "longitude", "rainfall_mm", "rainfall_rate_mm_hr"]
        assert header == expected
        rows = list(reader)
        assert len(rows) > 0


def test_landuse_geojson_schema(spec_data_files):
    """landuse.geojson: cell_id, land_use, impervious_fraction, curve_number"""
    p = spec_data_files["landuse.geojson"]
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 100
        props = data["features"][0]["properties"]
        for key in ["cell_id", "land_use", "impervious_fraction", "curve_number"]:
            assert key in props


def test_drainage_nodes_and_edges_geojson(spec_data_files):
    """drainage_nodes.geojson & drainage_edges.geojson schemas"""
    np_ = spec_data_files["drainage_nodes.geojson"]
    ep_ = spec_data_files["drainage_edges.geojson"]
    with open(np_, "r", encoding="utf-8") as f:
        ndata = json.load(f)
        nprops = ndata["features"][0]["properties"]
        for k in ["node_id", "node_type", "invert_elevation", "base_capacity"]:
            assert k in nprops

    with open(ep_, "r", encoding="utf-8") as f:
        edata = json.load(f)
        eprops = edata["features"][0]["properties"]
        for k in ["edge_id", "from_node", "to_node", "length", "diameter", "slope", "capacity"]:
            assert k in eprops


def test_roads_geojson_schema(spec_data_files):
    """roads.geojson: road_id, road_name, geometry, road_class, speed"""
    p = spec_data_files["roads.geojson"]
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
        props = data["features"][0]["properties"]
        for k in ["road_id", "road_name", "road_class", "speed"]:
            assert k in props


def test_sensors_csv_schema(spec_data_files):
    """sensors.csv: sensor_id, timestamp, latitude, longitude, distance_cm, water_depth_cm, status, battery, rssi"""
    p = spec_data_files["sensors.csv"]
    with open(p, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        expected = ["sensor_id", "timestamp", "latitude", "longitude", "distance_cm", "water_depth_cm", "status", "battery", "rssi"]
        assert header == expected
