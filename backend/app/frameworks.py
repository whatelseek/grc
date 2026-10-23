"""Access to control frameworks (currently CIS Controls) extracted from their source."""

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_FRAMEWORK = "cis"
DEFAULT_VERSION = "v8.1.2"


@lru_cache
def load_framework(framework: str = DEFAULT_FRAMEWORK, version: str = DEFAULT_VERSION) -> dict:
    with (DATA_DIR / f"{framework}_{version}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def safeguards(framework: str = DEFAULT_FRAMEWORK, version: str = DEFAULT_VERSION) -> dict[str, dict]:
    """safeguard id -> the safeguard, with its control's number and title attached."""
    out: dict[str, dict] = {}
    for control in load_framework(framework, version)["controls"]:
        for safeguard in control["safeguards"]:
            out[safeguard["id"]] = {
                **safeguard,
                "control": control["number"],
                "control_title": control["title"],
            }
    return out


def in_scope(framework: str, version: str, target_ig: int) -> list[dict]:
    """Safeguards a client aiming at `target_ig` has to cover; groups are cumulative."""
    return [s for s in safeguards(framework, version).values() if s["ig"] <= target_ig]
