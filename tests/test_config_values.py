from flood_engine.config import load_config


def test_locked_config_values():
    config = load_config()

    assert config["simulation"]["timestep_seconds"] == 60
    assert config["simulation"]["forecast_minutes"] == 180

    assert (
        config["surface"]["routing_coefficient"]
        == 0.0008
    )

    assert (
        config["surface"]["max_routing_fraction"]
        == 0.35
    )

    assert config["hydrology"]["default_cn"] == 85

    assert (
        config["drainage"]["default_capacity_m3_s"]
        == 0.01
    )

    assert (
        config["sensor"]["heartbeat_timeout_seconds"]
        == 180
    )

    assert config["sensor"]["bias_alpha"] == 0.3

    assert (
        config["sensor"]["agreement_window_steps"]
        == 10
    )
