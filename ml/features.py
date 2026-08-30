"""
Hydrological Feature Extraction for Physics-Guided Machine Learning (PGML).
Transforms raw terrain, soil, drainage, and meteorology into normalized feature vectors.
"""

import math

import numpy as np

FEATURE_NAMES = [
    "elevation_m",
    "slope_gradient",
    "curve_number",
    "impervious_fraction",
    "initial_abstraction_mm",
    "dist_to_drain_m",
    "drain_capacity_factor",
    "lead_time_min",
    "rain_rate_mm_hr",
    "cumulative_rain_mm",
    "valley_dist_m",
    "lowland_sink_proximity",
]


def compute_initial_abstraction(curve_number: float) -> float:
    """SCS-CN potential maximum retention S and Initial Abstraction Ia = 0.2S (mm)."""
    cn = max(50.0, min(99.0, curve_number))
    s_mm = (25400.0 / cn) - 254.0
    return 0.2 * s_mm


def extract_cell_static_features(row: int, col: int) -> dict[str, float]:
    """Extract physical topography, soil, and drainage features for a grid cell."""
    x = col * 10.0 + 5.0
    y = row * 10.0 + 5.0
    
    # 1. Elevation (Highlands in NW, lowlands in SE)
    elevation = 20.0 - (row + col) * 0.5
    
    # 2. Slope gradient towards downslope neighbor
    slope = 0.05 + 0.02 * math.sin((row + col) / 3.0)
    
    # 3. Curve Number & Imperviousness
    # Higher CN on roads / dense urban (mid-grid & corridors)
    if row in [0, 9] or col in [0, 9]:
        cn = 92.0
        imp = 0.85
    elif abs(row - col) <= 1:  # Arterial corridor
        cn = 95.0
        imp = 0.92
    elif row >= 5 and col >= 6:  # Lowland basin
        cn = 88.0
        imp = 0.70
    else:
        cn = 84.0
        imp = 0.60

    ia_mm = compute_initial_abstraction(cn)
    
    # 4. Proximity to stormwater inlets (IN01: midtown (5,5), E001: east (7,8), OUT1: south (9,9))
    inlets = [(45.0, 45.0), (75.0, 65.0), (95.0, 95.0)]
    dists = [math.hypot(x - ix, y - iy) for ix, iy in inlets]
    dist_to_drain = min(dists)
    
    # 5. Geomorphological features
    valley_dist = abs((x - y) / 14.14)
    lowland_sink_prox = math.exp(-(((x - 85.0) / 24.0) ** 2 + ((y - 55.0) / 26.0) ** 2))
    
    return {
        "elevation_m": elevation,
        "slope_gradient": slope,
        "curve_number": cn,
        "impervious_fraction": imp,
        "initial_abstraction_mm": ia_mm,
        "dist_to_drain_m": dist_to_drain,
        "valley_dist_m": valley_dist,
        "lowland_sink_proximity": lowland_sink_prox,
    }


def build_feature_vector(
    static_feats: dict[str, float],
    lead_time_min: float,
    rain_rate_mm_hr: float,
    cumulative_rain_mm: float,
    drain_capacity_factor: float = 1.0,
) -> list[float]:
    """Combine static catchment features with dynamic meteorological/drainage state."""
    return [
        static_feats["elevation_m"],
        static_feats["slope_gradient"],
        static_feats["curve_number"],
        static_feats["impervious_fraction"],
        static_feats["initial_abstraction_mm"],
        static_feats["dist_to_drain_m"],
        drain_capacity_factor,
        lead_time_min,
        rain_rate_mm_hr,
        cumulative_rain_mm,
        static_feats["valley_dist_m"],
        static_feats["lowland_sink_proximity"],
    ]


def build_catchment_feature_matrix(
    lead_time_min: float,
    rain_rate_mm_hr: float,
    cumulative_rain_mm: float,
    drain_capacity_factor: float = 1.0,
) -> np.ndarray:
    """Build (100, N_features) feature matrix for all cells at a given time step."""
    matrix = []
    for r in range(10):
        for c in range(10):
            sf = extract_cell_static_features(r, c)
            vec = build_feature_vector(
                sf,
                lead_time_min=lead_time_min,
                rain_rate_mm_hr=rain_rate_mm_hr,
                cumulative_rain_mm=cumulative_rain_mm,
                drain_capacity_factor=drain_capacity_factor,
            )
            matrix.append(vec)
    return np.array(matrix, dtype=np.float32)
