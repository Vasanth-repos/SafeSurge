from pathlib import Path
import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"


def validate_config(config: dict) -> None:
    """Validate required Layer-0 configuration values."""

    required_sections = [
        "simulation",
        "surface",
        "hydrology",
        "drainage",
        "sensor",
    ]

    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"Missing configuration section: {section}"
            )

    if config["simulation"]["timestep_seconds"] <= 0:
        raise ValueError(
            "simulation.timestep_seconds must be > 0"
        )

    if config["simulation"]["forecast_minutes"] <= 0:
        raise ValueError(
            "simulation.forecast_minutes must be > 0"
        )

    if not 0 < config["surface"]["max_routing_fraction"] <= 1:
        raise ValueError(
            "surface.max_routing_fraction must be in (0, 1]"
        )

    if not 0 < config["hydrology"]["default_cn"] <= 100:
        raise ValueError(
            "hydrology.default_cn must be in (0, 100]"
        )

    if config["drainage"]["default_capacity_m3_s"] < 0:
        raise ValueError(
            "drainage.default_capacity_m3_s cannot be negative"
        )

    if not 0 < config["sensor"]["bias_alpha"] <= 1:
        raise ValueError(
            "sensor.bias_alpha must be in (0, 1]"
        )

    if config["sensor"]["heartbeat_timeout_seconds"] <= 0:
        raise ValueError(
            "sensor.heartbeat_timeout_seconds must be > 0"
        )

    if config["sensor"]["agreement_window_steps"] <= 0:
        raise ValueError(
            "sensor.agreement_window_steps must be > 0"
        )


def load_config(path: Path = CONFIG_PATH) -> dict:
    """Load the shared project configuration."""
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError(
            "config.yaml must contain a YAML mapping."
        )

    validate_config(config)

    return config
