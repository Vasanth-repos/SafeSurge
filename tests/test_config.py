from flood_engine.config import load_config


def test_config_loads():
    config = load_config()

    assert isinstance(config, dict)
    assert "simulation" in config
    assert "surface" in config
    assert "hydrology" in config
    assert "drainage" in config
    assert "sensor" in config
