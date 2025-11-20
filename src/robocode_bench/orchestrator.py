from __future__ import annotations

import json
import pathlib
import subprocess
from typing import Optional

import typer
from rich import print

from .config import BenchmarkConfig
from .workspace import WorkspaceManager, WorkspacePaths
from . import tankroyale

app = typer.Typer(add_completion=False, help="Tank Royale benchmark orchestrator")


def _load_config(path: pathlib.Path) -> BenchmarkConfig:
    return BenchmarkConfig.load(path)


def _copy_battle_config(cfg: BenchmarkConfig, dest_dir: pathlib.Path) -> pathlib.Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    src = pathlib.Path(cfg.battle_files.battle_config_path)
    dest = dest_dir / src.name
    data = src.read_text(encoding="utf-8")
    dest.write_text(data, encoding="utf-8")
    seeds_src = pathlib.Path(cfg.battle_files.seeds_path)
    seeds_dest = dest_dir / seeds_src.name
    seeds_dest.write_text(seeds_src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def _run_py_compile(bot_src: pathlib.Path) -> subprocess.CompletedProcess:
    py_files = [str(p) for p in bot_src.rglob("*.py")]
    if not py_files:
        raise FileNotFoundError(f"No Python sources found under {bot_src}")
    cmd = ["python", "-m", "py_compile", *py_files]
    return subprocess.run(cmd, capture_output=True, text=True)


def _workspace_paths(workspace: pathlib.Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=workspace,
        prompts=workspace / "prompts",
        bot=workspace / "bot",
        bot_src=workspace / "bot" / "src",
        logs=workspace / "logs" / "matches",
        results=workspace / "results",
        server=workspace / "server",
    )


@app.command()
def prepare_workspace(
    model_id: str = typer.Option(..., help="Model identifier"),
    attempt_id: str = typer.Option(..., help="Attempt id"),
    workspace_root: pathlib.Path = typer.Option(pathlib.Path("workspaces"), help="Root for all workspaces"),
    template_dir: pathlib.Path = typer.Option(pathlib.Path("bot_template"), help="Template bot to copy"),
    config: pathlib.Path = typer.Option(pathlib.Path("benchmark-config.yaml"), help="Benchmark config"),
) -> None:
    """Create a new attempt workspace and copy starter bot template + battle config."""
    cfg = _load_config(config)
    manager = WorkspaceManager(workspace_root)
    paths = manager.create(model_id=model_id, attempt_id=attempt_id, template_dir=template_dir)
    _copy_battle_config(cfg, paths.server)
    print(f"[green]Workspace ready:[/green] {paths.root}")


@app.command()
def build_bot(
    workspace: pathlib.Path = typer.Argument(..., help="Path to attempt workspace root"),
) -> None:
    """Compile Python sources for the attempt and write build log."""
    paths = _workspace_paths(workspace)
    paths.logs.parent.mkdir(parents=True, exist_ok=True)
    result = _run_py_compile(paths.bot_src)
    log = (paths.root / "logs" / "build.log")
    log.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        print(f"[red]Build failed[/red] (see {log})")
        raise typer.Exit(code=result.returncode)
    print(f"[green]Build ok[/green] (log: {log})")


@app.command()
def download_stack(
    config: pathlib.Path = typer.Option(pathlib.Path("benchmark-config.yaml"), help="Benchmark config"),
    dest: pathlib.Path = typer.Option(pathlib.Path("tools/bin"), help="Where to place the jars"),
) -> None:
    """Download server/recorder/GUI jars matching the pinned versions."""
    cfg = _load_config(config)
    artifacts = tankroyale.download_stack(
        server=cfg.versions.server,
        recorder=cfg.versions.recorder,
        gui=cfg.versions.gui,
        dest_dir=dest,
    )
    for name, path in artifacts.items():
        print(f"[green]{name}[/green]: {path}")


@app.command()
def evaluate(
    workspace: pathlib.Path = typer.Argument(..., help="Attempt workspace root"),
    config: pathlib.Path = typer.Option(pathlib.Path("benchmark-config.yaml"), help="Benchmark config"),
    server_jar: Optional[pathlib.Path] = typer.Option(None, help="Path to robocode-tankroyale-server jar"),
    recorder_jar: Optional[pathlib.Path] = typer.Option(None, help="Path to robocode-tankroyale-recorder jar"),
) -> None:
    """
    Run the full benchmark loop for a prepared workspace.

    This implementation runs build + dry-run skeletons and reserves hooks for
    spawning the server/recorder and actual matches. Hook up your battle runner
    here once jars are downloaded.
    """
    cfg = _load_config(config)
    paths = _workspace_paths(workspace)

    # Step 1: build
    result = _run_py_compile(paths.bot_src)
    build_log = paths.root / "logs" / "build.log"
    build_log.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        print(f"[red]Build failed[/red]; see {build_log}")
        raise typer.Exit(result.returncode)

    if server_jar or recorder_jar:
        print(
            "[yellow]Server/recorder paths supplied but match runner is not wired yet; "
            "extend evaluate() to launch battles.[/yellow]"
        )

    # Step 2: dry-run placeholder (extend with server + recorder)
    metrics = {
        "benchmark_id": cfg.benchmark_id,
        "status": "built",
        "notes": "Dry-run and tournament execution not yet wired; integrate server + bot launcher.",
    }
    results_path = paths.results / "metrics.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"[yellow]Skipping match execution[/yellow]. Metrics stub written to {results_path}")


if __name__ == "__main__":
    app()
