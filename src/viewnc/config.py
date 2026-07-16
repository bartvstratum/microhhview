from __future__ import annotations

import json
import sys
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "viewnc"

CONFIG_DIR = Path(user_config_dir(APP_NAME))
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "colormaps": [
        "WhiteBlueGreenYellowRed",
        "viridis",
        "RdBu_r",
        "gray",
        "turbo",
    ],
    "default_colormap": "WhiteBlueGreenYellowRed",
}


def load_config() -> dict:
    """Load the user config, creating it with defaults on first run.
    Missing keys are backfilled from DEFAULT_CONFIG so older config
    files keep working after new settings are added."""
    if not CONFIG_PATH.exists():
        print(f"viewnc: writing default config to {CONFIG_PATH}", file=sys.stderr)
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    print(f"viewnc: reading config from {CONFIG_PATH}", file=sys.stderr)
    try:
        config = json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)

    return {**DEFAULT_CONFIG, **config}


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
