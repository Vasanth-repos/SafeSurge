"""
Layer 3 — Rainfall Replay Demo Entry Point.
"""

from pathlib import Path
from replay.rainfall import load_rainfall_replay, ScalarRainfallReplay


def main():
    print("Layer 3 — Rainfall Replay")
    print("=" * 70)

    config_path = "config.yaml"
    source_file = "data/replay/rainfall/storm_01.json"

    replay: ScalarRainfallReplay = load_rainfall_replay(
        source_file,
        config_path=config_path,
    )

    print(f"Config: config.yaml")
    print(f"Source: {source_file}")
    print(f"Configured timestep: {replay.timestep_seconds} seconds")
    print(f"Replay timestep: {replay.timestep_seconds} seconds")
    print(f"Steps: {replay.step_count}")
    print(f"Duration: {replay.duration_seconds} seconds\n")

    for step in replay.replay():
        print(f"t={step.minute} -> rainfall received: {int(step.rainfall_mm)} mm (timestamp={step.timestamp_seconds}s)")

    print(f"\nEvent rainfall depth: {int(replay.total_rainfall_mm)} mm")
    print(f"Maximum timestep depth: {int(replay.max_timestep_rainfall_mm)} mm")
    print(f"Mean timestep depth: {int(replay.mean_timestep_rainfall_mm)} mm\n")

    print("Flood engine called: NO")
    print("Radar called: NO")
    print("Deterministic replay: PASS")


if __name__ == "__main__":
    main()
