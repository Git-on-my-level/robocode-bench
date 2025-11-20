from __future__ import annotations

import pathlib
import json
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, validator


class GenerationLimits(BaseModel):
    max_input_tokens: int = Field(..., description="Max prompt tokens")
    max_output_tokens: int = Field(..., description="Max model output tokens")
    temperature: float = Field(..., ge=0.0, le=1.0)
    top_p: float = Field(..., ge=0.0, le=1.0)
    max_calls: int = Field(..., ge=1)


class VariantPolicy(BaseModel):
    variants: int = 1
    allow_repair: bool = True


class BattleFiles(BaseModel):
    battle_config_path: pathlib.Path
    seeds_path: pathlib.Path

    @validator("battle_config_path", "seeds_path", pre=True)
    def _expand_path(cls, value: str | pathlib.Path) -> pathlib.Path:  # noqa: N805
        return pathlib.Path(value).expanduser()


class ResourceLimits(BaseModel):
    bot_cpu: float = 1.0
    bot_memory_mb: int = 512
    match_timeout_seconds: int = 300
    build_cpu: float = 2.0
    build_memory_mb: int = 4096
    build_timeout_seconds: int = 120


class TankRoyaleVersions(BaseModel):
    server: str
    recorder: str
    gui: str
    python_bot_api: str


class BenchmarkConfig(BaseModel):
    benchmark_id: str
    versions: TankRoyaleVersions
    generation_limits: GenerationLimits
    variant_policy: VariantPolicy
    battle_files: BattleFiles
    resource_limits: ResourceLimits
    seeds: List[int]

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "BenchmarkConfig":
        cfg_path = pathlib.Path(path)
        with cfg_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        data.setdefault("seeds", [])
        if not data.get("seeds"):
            seeds_path = data.get("battle_files", {}).get("seeds_path")
            if seeds_path:
                spath = pathlib.Path(seeds_path)
                if not spath.is_absolute():
                    spath = cfg_path.parent / spath
                if spath.exists():
                    loaded = json.loads(spath.read_text())
                    if isinstance(loaded, list):
                        data["seeds"] = loaded
        # Backward compatibility: rename attempt_policy -> variant_policy
        if "attempt_policy" in data and "variant_policy" not in data:
            data["variant_policy"] = data.pop("attempt_policy")
        if "variant_policy" in data and "variants" not in data["variant_policy"]:
            attempts = data["variant_policy"].pop("attempts", None)
            if attempts is not None:
                data["variant_policy"]["variants"] = attempts
        return cls(**data)

    def ensure_paths(self, root: Optional[pathlib.Path] = None) -> "BenchmarkConfig":
        """Return a copy with paths resolved relative to root if provided."""
        root = root or pathlib.Path.cwd()
        data = self.dict()
        battle = data.get("battle_files", {})
        if "battle_config_path" in battle:
            battle["battle_config_path"] = str((root / battle["battle_config_path"]).resolve())
        if "seeds_path" in battle:
            battle["seeds_path"] = str((root / battle["seeds_path"]).resolve())
        data["battle_files"] = battle
        return BenchmarkConfig(**data)
