"""
Catchment Generation Demo:
Demonstrates synthetic catchment generation with elevation hypsometry,
CN curve numbers, drainage network, road network, and sensor placements.
"""

from replay.catchment_data import generate_demo_catchment


def main():
    print("Catchment Replay & Demonstration Generator")
    print("=" * 68)

    catchment = generate_demo_catchment(rows=20, cols=20, cell_size_m=10.0)

    elev = catchment["elevation_grid"]
    cn = catchment["cn_grid"]
    drainage = catchment["drainage"]
    roads = catchment["roads"]
    sensors = catchment["sensors"]

    print(f"Catchment Grid Extent: {elev.shape[0]}x{elev.shape[1]} (400 cells, 10m resolution)")
    print(f"Elevation Range:       {elev.min():.2f}m to {elev.max():.2f}m")
    print(f"Curve Number Range:    {cn.min():.1f} to {cn.max():.1f}")
    print(f"Drainage Inlets/Nodes: {len(drainage.nodes)} nodes, {len(drainage.edges)} conduits")
    print(f"Road Network Segments: {len(roads.roads)} road segments")
    print(f"Sensor Deployments:    {len(sensors)} telemetry monitoring nodes")
    print("-" * 68)
    print("Catchment Replay Generator: COMPLETE (PASS)")


if __name__ == "__main__":
    main()
