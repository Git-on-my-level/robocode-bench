from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
from typing import Dict, Iterable, Sequence

from .config import BenchmarkConfig


class ArtifactError(Exception):
    """Raised when a workspace cannot be saved as an artifact."""


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        yield path


def sha256_directory(root: pathlib.Path) -> str:
    """Hash file names + contents under a directory for reproducibility."""
    if not root.is_dir():
        raise ArtifactError(f"Directory not found: {root}")
    digest = hashlib.sha256()
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _collect_hashes(root: pathlib.Path, items: Sequence[pathlib.Path]) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for path in items:
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files[rel] = _sha256_file(path)
            continue
        for file_path in _iter_files(path):
            rel = file_path.relative_to(root).as_posix()
            files[rel] = _sha256_file(file_path)
    return files


def save_workspace_artifact(
    *,
    workspace: pathlib.Path,
    dest_root: pathlib.Path,
    model_id: str,
    variant_id: str,
    benchmark_config: pathlib.Path,
    template_dir: pathlib.Path,
    force: bool = False,
) -> pathlib.Path:
    """
    Copy curated files from a workspace into bots/<model>/<variant>/ with metadata.

    Returns the destination path.
    """
    ws_root = workspace.resolve()
    prompts_dir = ws_root / "prompts"
    bot_dir = ws_root / "bot"
    bot_src = bot_dir / "src"
    bot_config = bot_dir / "bot-config.json"
    required = [
        bot_src,
        bot_config,
        prompts_dir / "initial_prompt.txt",
        prompts_dir / "initial_response.txt",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise ArtifactError(f"Missing required workspace files: {', '.join(missing)}")

    cfg_path = pathlib.Path(benchmark_config).resolve()
    if not cfg_path.exists():
        raise ArtifactError(f"Benchmark config not found: {cfg_path}")
    template_path = pathlib.Path(template_dir).resolve()
    if not template_path.exists():
        raise ArtifactError(f"Template directory not found: {template_path}")

    dest = pathlib.Path(dest_root).resolve() / model_id / variant_id
    if dest.exists():
        if not force:
            raise ArtifactError(f"Destination already exists: {dest}")
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    dest_bot = dest / "bot"
    dest_prompts = dest / "prompts"
    dest_bot.mkdir(parents=True, exist_ok=True)
    dest_prompts.mkdir(parents=True, exist_ok=True)

    shutil.copy2(bot_config, dest_bot / "bot-config.json")
    shutil.copytree(bot_src, dest_bot / "src", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    shutil.copy2(prompts_dir / "initial_prompt.txt", dest_prompts / "initial_prompt.txt")
    shutil.copy2(prompts_dir / "initial_response.txt", dest_prompts / "initial_response.txt")

    cfg = BenchmarkConfig.load(cfg_path)
    metadata = {
        "model_id": model_id,
        "variant_id": variant_id,
        "benchmark_config_path": str(cfg_path),
        "benchmark_config_sha256": _sha256_file(cfg_path),
        "template_sha256": sha256_directory(template_path),
        "seeds": cfg.seeds,
        "files": _collect_hashes(dest, [dest_bot, dest_prompts]),
    }
    metadata_path = dest / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return dest
