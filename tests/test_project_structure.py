from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_required_directories_exist():
    required = [
        "flood_engine",
        "sensors",
        "routing",
        "replay",
        "backend",
        "frontend",
        "tests",
        "data",
    ]

    for directory in required:
        assert (ROOT / directory).is_dir()


def test_required_config_exists():
    assert (ROOT / "config.yaml").is_file()
