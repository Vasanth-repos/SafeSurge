import subprocess
import sys


def test_demo_runs_successfully():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flood_engine.demo",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Layer 0 environment: OK" in result.stdout
    assert "Configuration validation: PASS" in result.stdout
