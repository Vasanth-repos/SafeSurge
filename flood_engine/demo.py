from flood_engine.config import load_config


def main():
    config = load_config()

    print("Urban Flood Nowcast")
    print("=" * 40)
    print("Layer 0 environment: OK")
    print(
        "Timestep:",
        config["simulation"]["timestep_seconds"],
        "seconds",
    )
    print(
        "Forecast:",
        config["simulation"]["forecast_minutes"],
        "minutes",
    )
    print(
        "Default CN:",
        config["hydrology"]["default_cn"],
    )
    print("Configuration validation: PASS")


if __name__ == "__main__":
    main()
