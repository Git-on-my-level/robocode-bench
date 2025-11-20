from __future__ import annotations

import asyncio
import json
import os
import pathlib
import signal
import subprocess
import sys
import socket
from typing import Dict, List, Optional, Sequence

import typer
from rich import print

from .config import BenchmarkConfig
from .workspace import WorkspaceManager, WorkspacePaths
from . import tankroyale
from .scoring import (
    BotAggregate,
    MatchMetrics,
    RoundScore,
    ScoreWeights,
    compute_bps,
    compute_final_score,
    compute_fps,
    compute_srs,
    normalize_scores,
)
from .baselines import load_manifest

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


def _default_stack_paths(cfg: BenchmarkConfig, tools_dir: pathlib.Path = pathlib.Path("tools") / "bin") -> dict[str, pathlib.Path]:
    return {
        "server": tools_dir / f"robocode-tankroyale-server-{cfg.versions.server}.jar",
        "recorder": tools_dir / f"robocode-tankroyale-recorder-{cfg.versions.recorder}.jar",
    }


def _default_java_bin() -> Optional[pathlib.Path]:
    candidates = [
        pathlib.Path(os.environ.get("JAVA_BIN")) if os.environ.get("JAVA_BIN") else None,
        pathlib.Path("/opt/homebrew/opt/openjdk@17/bin/java"),
    ]
    for cand in candidates:
        if cand and cand.exists():
            return cand
    return None


def _find_free_port(preferred: int = tankroyale.DEFAULT_PORT) -> int:
    """Return an available TCP port (prefers the default, falls back to OS-assigned)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", preferred))
            return s.getsockname()[1]
        except OSError:
            s.bind(("", 0))
            return s.getsockname()[1]


def _load_battle_config(cfg: BenchmarkConfig) -> dict:
    path = pathlib.Path(cfg.battle_files.battle_config_path)
    return json.loads(path.read_text())


def _battle_setup_from_config(battle_config: dict, game_type: str, participants: int) -> dict:
    bf = battle_config.get("battlefield", {})
    return {
        "gameType": game_type,
        "arenaWidth": bf.get("width", 800),
        "isArenaWidthLocked": True,
        "arenaHeight": bf.get("height", 600),
        "isArenaHeightLocked": True,
        "minNumberOfParticipants": battle_config.get("minNumberOfParticipants", max(2, participants)),
        "isMinNumberOfParticipantsLocked": True,
        "maxNumberOfParticipants": participants,
        "isMaxNumberOfParticipantsLocked": False,
        "numberOfRounds": battle_config.get("numberOfRounds", 10),
        "isNumberOfRoundsLocked": True,
        "gunCoolingRate": battle_config.get("gunCoolingRate", 0.1),
        "isGunCoolingRateLocked": True,
        "maxInactivityTurns": battle_config.get("maxInactivityTurns", 450),
        "isMaxInactivityTurnsLocked": True,
        "turnTimeout": battle_config.get("turnTimeout", 40),
        "isTurnTimeoutLocked": True,
        "readyTimeout": battle_config.get("readyTimeout", 10000),
        "isReadyTimeoutLocked": True,
        "defaultTurnsPerSecond": battle_config.get("turnsPerSecond", 60),
    }


def _launch_python_bot(bot_dir: pathlib.Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("SERVER_URL", f"ws://localhost:{port}")
    env.setdefault("PYTHONPATH", os.pathsep.join([env.get("PYTHONPATH", ""), str(pathlib.Path(__file__).resolve().parents[2] / "src")]).strip(os.pathsep))
    main_path = bot_dir / "main.py"
    if not main_path.exists():
        nested = bot_dir / "src" / "main.py"
        if nested.exists():
            main_path = nested
    if not main_path.exists():
        raise FileNotFoundError(f"Cannot find main.py under {bot_dir}")
    cwd = bot_dir
    if main_path.parent != bot_dir:
        try:
            rel = main_path.relative_to(bot_dir)
        except ValueError:
            rel = main_path.name
        entry = str(rel)
    else:
        entry = main_path.name
    return subprocess.Popen([sys.executable, entry], cwd=cwd, env=env)


async def _controller_run(expected_bots: Sequence[str], game_setup: dict, seed: int, port: int) -> list[dict]:
    import websockets

    url = f"ws://localhost:{port}"
    async with websockets.connect(url) as ws:
        msg = json.loads(await ws.recv())
        assert msg.get("type") == "ServerHandshake", f"Unexpected message: {msg}"
        server_session = msg["sessionId"]
        ctrl = {
            "type": "ControllerHandshake",
            "sessionId": server_session,
            "name": "bench-controller",
            "version": "0.1",
            "author": "bench",
        }
        await ws.send(json.dumps(ctrl))

        bots: dict[str, dict] = {}
        while len(bots) < len(expected_bots):
            payload = json.loads(await ws.recv())
            if payload.get("type") == "BotListUpdate":
                for bot in payload.get("bots", []):
                    bots[bot["name"]] = bot
        missing = [name for name in expected_bots if name not in bots]
        if missing:
            raise RuntimeError(f"Missing bots in lobby: {missing}")
        addresses = [{"host": bots[name]["host"], "port": bots[name]["port"]} for name in expected_bots]
        setup = dict(game_setup)
        setup["seed"] = seed
        start_game = {
            "type": "StartGame",
            "botAddresses": addresses,
            "gameSetup": setup,
        }
        await ws.send(json.dumps(start_game))

        game_results: list[dict] | None = None
        while True:
            try:
                payload = json.loads(await ws.recv())
            except websockets.ConnectionClosed:
                break
            if payload.get("type") == "GameEndedEventForObserver":
                game_results = payload.get("results", [])
                break
        return game_results or []


def _results_to_roundscores(results: list[dict], participants: int, rounds: int) -> Dict[str, List[Dict]]:
    # Treat aggregate game results as a single pseudo-round averaged per round for scoring.
    scores: Dict[str, List[Dict]] = {}
    if not results:
        return scores
    # Rank by totalScore descending.
    sorted_results = sorted(results, key=lambda r: r.get("totalScore", 0), reverse=True)
    for rank_idx, res in enumerate(sorted_results, start=1):
        total = res.get("totalScore", 0.0)
        roundsafe = max(1, rounds)
        entry = {
            "round_number": 1,
            "total_score": total / roundsafe,
            "bullet_damage": res.get("bulletDamage", 0.0) / roundsafe,
            "bullet_damage_bonus": res.get("bulletDamageBonus", 0.0) / roundsafe,
            "ram_damage": res.get("ramDamage", 0.0) / roundsafe,
            "ram_damage_bonus": res.get("ramDamageBonus", 0.0) / roundsafe,
            "survival_score": res.get("survival", 0.0) / roundsafe,
            "last_survivor_bonus": res.get("lastSurvivorBonus", 0.0) / roundsafe,
            "rank": rank_idx,
        }
        scores.setdefault(res.get("name", f"bot_{rank_idx}"), []).append(entry)
    return scores


def _launch_battle(
    server_jar: pathlib.Path,
    recorder_jar: Optional[pathlib.Path],
    expected: Sequence[str],
    bot_dirs: Sequence[pathlib.Path],
    game_setup: dict,
    seed: int,
    logs_dir: pathlib.Path,
    port: int = tankroyale.DEFAULT_PORT,
    java_bin: Optional[pathlib.Path] = None,
    timeout_seconds: int = 300,
) -> list[dict]:
    """Start server/recorder, launch bots, run controller, and return game results."""
    server_log = logs_dir / f"server_seed{seed}.log"
    recorder_log = logs_dir / f"recorder_seed{seed}.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    loops: list[subprocess.Popen] = []
    server = tankroyale.start_server(
        server_jar,
        server_log,
        game_types=[game_setup["gameType"]],
        port=port,
        tps=game_setup.get("defaultTurnsPerSecond", 60),
        java_bin=java_bin,
    )
    recorder_proc: Optional[tankroyale.TankRoyaleProcess] = None
    try:
        if not tankroyale.wait_for_port(port=port, timeout=10):
            raise RuntimeError("Server WebSocket not ready in time")
        if recorder_jar:
            recorder_proc = tankroyale.start_recorder(recorder_jar, recorder_log, server_url=f"ws://localhost:{port}", java_bin=java_bin)
        loops = [_launch_python_bot(p, port) for p in bot_dirs]
        results: list[dict] = []
        try:
            wait_timeout = max(30, timeout_seconds)
            results = asyncio.run(asyncio.wait_for(_controller_run(expected, game_setup, seed, port), timeout=wait_timeout))
        finally:
            for proc in loops:
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.send_signal(signal.SIGTERM)
        return results
    finally:
        if recorder_proc:
            recorder_proc.stop()
        server.stop()


@app.command()
def prepare_workspace(
    model_id: str = typer.Option(..., help="Model identifier"),
    variant_id: str = typer.Option(..., help="Variant id (run/build flavor for a model)"),
    workspace_root: pathlib.Path = typer.Option(pathlib.Path("workspaces"), help="Root for all workspaces"),
    template_dir: pathlib.Path = typer.Option(pathlib.Path("bot_template"), help="Template bot to copy"),
    config: pathlib.Path = typer.Option(pathlib.Path("benchmark-config.yaml"), help="Benchmark config"),
    shared_docs: List[pathlib.Path] = typer.Option(
        [
            pathlib.Path("SPEC.md"),
            pathlib.Path("docs/LLM_AGENT_WORKFLOW.md"),
            pathlib.Path("docs/TANK_ROYALE_OVERVIEW.md"),
            pathlib.Path("docs/AGENT_CONTEXT.md"),
        ],
        help="Files or directories to copy into workspaces/_shared_docs for all models to read",
    ),
) -> None:
    """Create a new variant workspace and copy starter bot template + battle config."""
    cfg = _load_config(config)
    manager = WorkspaceManager(workspace_root)
    paths = manager.create(model_id=model_id, variant_id=variant_id, template_dir=template_dir, shared_docs=shared_docs)
    _copy_battle_config(cfg, paths.server)
    print(f"[green]Workspace ready:[/green] {paths.root}")
    if paths.shared_docs:
        print(f"[green]Shared docs:[/green] {paths.shared_docs}")


@app.command()
def build_bot(
    workspace: pathlib.Path = typer.Argument(..., help="Path to variant workspace root"),
) -> None:
    """Compile Python sources for the variant and write build log."""
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
    checksums: Optional[pathlib.Path] = typer.Option(None, help="Optional JSON/YAML file with sha256 checksums keyed by artifact name"),
) -> None:
    """Download server/recorder/GUI jars matching the pinned versions."""
    cfg = _load_config(config)
    checksum_map: Dict[str, str] = {}
    if checksums and checksums.exists():
        try:
            data = json.loads(checksums.read_text())
        except json.JSONDecodeError:
            import yaml

            data = yaml.safe_load(checksums.read_text())
        if isinstance(data, dict):
            checksum_map = {k: str(v) for k, v in data.items()}
    artifacts = tankroyale.download_stack(
        server=cfg.versions.server,
        recorder=cfg.versions.recorder,
        gui=cfg.versions.gui,
        dest_dir=dest,
        checksums=checksum_map,
    )
    for name, path in artifacts.items():
        print(f"[green]{name}[/green]: {path}")


@app.command()
def evaluate(
    workspace: pathlib.Path = typer.Argument(..., help="Variant workspace root"),
    config: pathlib.Path = typer.Option(pathlib.Path("benchmark-config.yaml"), help="Benchmark config"),
    server_jar: Optional[pathlib.Path] = typer.Option(None, help="Path to robocode-tankroyale-server jar"),
    recorder_jar: Optional[pathlib.Path] = typer.Option(None, help="Path to robocode-tankroyale-recorder jar"),
    baseline_manifest: pathlib.Path = typer.Option(pathlib.Path("baselines/manifest.yaml"), help="Baseline manifest (not shared with models)"),
    java_bin: Optional[pathlib.Path] = typer.Option(None, help="Path to java binary (defaults to JAVA_BIN env or Homebrew openjdk@17)"),
) -> None:
    """
    Run the full benchmark loop for a prepared variant workspace.

    Builds the bot, then executes 1v1 and melee matches against the baseline
    manifest using the pinned battle config + seeds. Recorder jars are optional;
    when supplied they will write logs under workspace/logs/matches.
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

    # Resolve jars (default to tools/bin/<version>.jar)
    defaults = _default_stack_paths(cfg)
    server_path = pathlib.Path(server_jar or defaults["server"]).resolve()
    recorder_path = pathlib.Path(recorder_jar).resolve() if recorder_jar else None
    if not server_path.exists():
        print(f"[red]Server jar not found[/red]: {server_path}")
        raise typer.Exit(1)
    if recorder_path and not recorder_path.exists():
        print(f"[red]Recorder jar not found[/red]: {recorder_path}")
        raise typer.Exit(1)

    seeds = cfg.seeds
    if not seeds:
        print("[red]No seeds configured[/red]; ensure benchmark-config.yaml or seeds file includes at least one seed.")
        raise typer.Exit(1)

    battle_config = _load_battle_config(cfg)
    manifest = load_manifest(baseline_manifest, root=pathlib.Path.cwd(), validate_paths=True)
    java_bin = java_bin or _default_java_bin()
    if java_bin and not java_bin.exists():
        print(f"[red]Java binary not found[/red]: {java_bin}")
        raise typer.Exit(1)
    if not java_bin:
        print("[red]No Java runtime found[/red]; set JAVA_BIN or pass --java-bin.")
        raise typer.Exit(1)

    # Discover bot names from configs
    def _bot_name(bot_dir: pathlib.Path) -> str:
        cfg_path = bot_dir / "bot-config.json"
        if cfg_path.exists():
            try:
                return json.loads(cfg_path.read_text()).get("name", bot_dir.name)
            except Exception:
                return bot_dir.name
        return bot_dir.name

    model_bot_name = _bot_name(paths.bot)

    per_baseline: Dict[str, MatchMetrics] = {}
    ffa_rounds: List[RoundScore] = []

    # 1v1 bracket: model vs each baseline for all seeds.
    for base in manifest.bots:
        if "1v1" not in base.game_types:
            continue
        rounds: List[RoundScore] = []
        game_setup = _battle_setup_from_config(battle_config, "1v1", participants=2)
        for seed in seeds:
            port = _find_free_port(0)
            results = _launch_battle(
                server_jar=server_path,
                recorder_jar=recorder_path,
                expected=[model_bot_name, _bot_name(base.path)],
                bot_dirs=[paths.bot, base.path],
                game_setup=game_setup,
                seed=seed,
                logs_dir=paths.logs,
                java_bin=java_bin,
                port=port,
                timeout_seconds=cfg.resource_limits.match_timeout_seconds,
            )
            round_map = _results_to_roundscores(results, participants=2, rounds=game_setup["numberOfRounds"])
            for entry in round_map.get(model_bot_name, []):
                rounds.append(RoundScore(**entry))
        if rounds:
            per_baseline[base.id] = MatchMetrics(rounds=rounds)

    # Melee/Classic bracket
    melee_participants = max(2, manifest.melee_participants)
    if manifest.bots:
        game_setup = _battle_setup_from_config(battle_config, "classic", participants=melee_participants)
        # Cycle baselines to fill slots (excluding model).
        from itertools import cycle, islice

        baseline_cycle = cycle(manifest.bots)
        for seed in seeds:
            port = _find_free_port(0)
            opponents = list(islice(baseline_cycle, melee_participants - 1))
            expected_names = [model_bot_name] + [_bot_name(op.path) for op in opponents]
            bot_dirs = [paths.bot] + [op.path for op in opponents]
            results = _launch_battle(
                server_jar=server_path,
                recorder_jar=recorder_path,
                expected=expected_names,
                bot_dirs=bot_dirs,
                game_setup=game_setup,
                seed=seed,
                logs_dir=paths.logs,
                java_bin=java_bin,
                port=port,
                timeout_seconds=cfg.resource_limits.match_timeout_seconds,
            )
            round_map = _results_to_roundscores(results, participants=melee_participants, rounds=game_setup["numberOfRounds"])
            for entry in round_map.get(model_bot_name, []):
                ffa_rounds.append(RoundScore(**entry))

    # Aggregate scoring
    avg_totals = [m.avg_total_score for m in per_baseline.values()] if per_baseline else []
    norm_values = normalize_scores(avg_totals) if avg_totals else []
    normalization = {bid: norm_values[idx] for idx, bid in enumerate(per_baseline.keys())}
    bps = compute_bps(per_baseline, normalization, alpha=ScoreWeights().alpha_winrate) if per_baseline else 0.0
    fps = compute_fps(ffa_rounds, participants=melee_participants) if ffa_rounds else 0.0

    agg = BotAggregate(match_metrics=per_baseline.copy())
    if ffa_rounds:
        agg.match_metrics["ffa"] = MatchMetrics(rounds=ffa_rounds)
    srs = compute_srs(agg, variance_normalizer=1.0)

    final = compute_final_score(bps, fps, srs)
    metrics = {
        "benchmark_id": cfg.benchmark_id,
        "status": "completed",
        "bps": final.bps,
        "fps": final.fps,
        "srs": final.srs,
        "bot_score": final.bot_score,
        "per_baseline": {bid: {"avg_total_score": m.avg_total_score, "avg_rank": m.avg_rank, "winrate_round": m.winrate_round} for bid, m in per_baseline.items()},
        "ffa_rounds": len(ffa_rounds),
        "baseline_manifest_version": manifest.version,
        "notes": "Scores are per-match aggregates treated as pseudo-rounds; hook up recorder parsing for per-round fidelity.",
    }
    results_path = paths.results / "metrics.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"[green]Evaluation complete[/green]. Results: {results_path}")


if __name__ == "__main__":
    app()
