from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import List

import yaml


@dataclass
class BaselineBot:
    id: str
    name: str
    path: pathlib.Path
    game_types: List[str]
    role: str = ""


@dataclass
class BaselineManifest:
    version: int
    melee_participants: int
    bots: List[BaselineBot]


def load_manifest(
    manifest_path: pathlib.Path = pathlib.Path("baselines/manifest.yaml"),
    root: pathlib.Path | None = None,
    validate_paths: bool = True,
) -> BaselineManifest:
    """
    Read the baseline manifest (not shared with models) describing 1v1/melee opponents.

    Paths in the manifest are resolved relative to the manifest file unless absolute.
    """
    path = manifest_path
    if not path.is_absolute() and root:
        path = root / path
    path = path.resolve()
    data = yaml.safe_load(path.read_text())
    base_dir = root or path.parent.parent  # repo root if manifest is under baselines/
    bots: List[BaselineBot] = []
    for entry in data.get("bots", []):
        raw_path = pathlib.Path(entry["path"])
        resolved = raw_path if raw_path.is_absolute() else (base_dir / raw_path)
        if validate_paths and not resolved.exists():
            raise FileNotFoundError(f"Baseline path missing: {resolved}")
        bots.append(
            BaselineBot(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                path=resolved,
                game_types=entry.get("game_types", ["classic", "1v1"]),
                role=entry.get("role", ""),
            )
        )
    return BaselineManifest(
        version=int(data.get("version", 1)),
        melee_participants=int(data.get("melee_participants", max(2, len(bots)))),
        bots=bots,
    )
