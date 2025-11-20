#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from robocode_bench import orchestrator  # type: ignore
from robocode_bench.config import BenchmarkConfig


def _bot_name(bot_dir: pathlib.Path) -> str:
    cfg_path = bot_dir / "bot-config.json"
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text())
            if isinstance(data, dict):
                return str(data.get("name", bot_dir.name))
        except Exception:
            pass
    return bot_dir.name


def _validate_config(bot_dir: pathlib.Path) -> Tuple[list[str], dict]:
    cfg_path = bot_dir / "bot-config.json"
    errors: list[str] = []
    data: dict = {}
    try:
        raw = cfg_path.read_text()
        data = json.loads(raw)
    except FileNotFoundError:
        errors.append("bot-config.json missing")
    except json.JSONDecodeError as exc:
        errors.append(f"bot-config.json invalid JSON: {exc}")
    else:
        required = ["name", "version", "authors", "description", "gameTypes", "countryCodes"]
        for key in required:
            if not data.get(key):
                errors.append(f"Missing or empty required field '{key}'")
    return errors, data


def run_static(workspace: pathlib.Path) -> str:
    paths = orchestrator._workspace_paths(workspace)
    log_dir = paths.root / "logs" / "sanity"
    log_dir.mkdir(parents=True, exist_ok=True)
    result = orchestrator._run_py_compile(paths.bot_src)
    cfg_errors, cfg_data = _validate_config(paths.bot)
    log_path = log_dir / "static.log"
    log_path.write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
    summary = {
        "check": "static",
        "status": "ok" if result.returncode == 0 and not cfg_errors else "failed",
        "py_compile_exit": result.returncode,
        "config_errors": cfg_errors,
        "bot_config": cfg_data,
        "log": str(log_path),
    }
    summary_path = paths.root / "results" / "sanity_static.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if summary["status"] != "ok":
        raise SystemExit(f"Static check failed; see {log_path}")
    print(f"[static] ok -> logs: {log_path}")
    return str(summary_path)


def run_match(workspace: pathlib.Path, opponent: str, rounds: int, seed: int | None, server_jar: pathlib.Path | None, recorder_jar: pathlib.Path | None, java_bin: pathlib.Path | None) -> str:
    cfg = BenchmarkConfig.load(pathlib.Path("benchmark-config.yaml"))
    paths = orchestrator._workspace_paths(workspace)
    defaults = orchestrator._default_stack_paths(cfg)
    server_path = pathlib.Path(server_jar or defaults["server"]).resolve()
    recorder_path = pathlib.Path(recorder_jar).resolve() if recorder_jar else None
    java_bin = java_bin or orchestrator._default_java_bin()
    if not server_path.exists():
        raise SystemExit(f"Server jar not found: {server_path}")
    if recorder_path and not recorder_path.exists():
        raise SystemExit(f"Recorder jar not found: {recorder_path}")

    opp_dir = ROOT / "sample_bots" / opponent
    if not opp_dir.exists():
        raise SystemExit(f"Unknown opponent '{opponent}'. Expected directory: {opp_dir}")

    # Ensure code compiles before launching the battle.
    build = orchestrator._run_py_compile(paths.bot_src)
    if build.returncode != 0:
        raise SystemExit("py_compile failed; run the static check and fix errors before running matches.")

    battle_config = orchestrator._load_battle_config(cfg)
    game_setup = orchestrator._battle_setup_from_config(battle_config, game_type="1v1", participants=2)
    game_setup["numberOfRounds"] = rounds
    seed_to_use = seed if seed is not None else (cfg.seeds[0] if cfg.seeds else 1)

    port = orchestrator._find_free_port(0)
    logs_dir = paths.root / "logs" / "sanity" / opponent
    logs_dir.mkdir(parents=True, exist_ok=True)

    model_name = _bot_name(paths.bot)
    opponent_name = _bot_name(opp_dir)

    results = orchestrator._launch_battle(
        server_jar=server_path,
        recorder_jar=recorder_path,
        expected=[model_name, opponent_name],
        bot_dirs=[paths.bot, opp_dir],
        game_setup=game_setup,
        seed=seed_to_use,
        logs_dir=logs_dir,
        java_bin=java_bin,
        port=port,
        timeout_seconds=180,
    )

    # Winner is highest totalScore.
    ordering = sorted(results, key=lambda r: r.get("totalScore", 0), reverse=True)
    winner = ordering[0]["name"] if ordering else None
    summary = {
        "check": opponent,
        "status": "ok" if results else "failed",
        "seed": seed_to_use,
        "rounds": rounds,
        "winner": winner,
        "results": results,
        "logs_dir": str(logs_dir),
    }
    summary_path = paths.root / "results" / f"sanity_{opponent}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[{opponent}] winner={winner} -> logs: {logs_dir}")
    return str(summary_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight sanity checks for a bot workspace.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path, help="Path to the variant workspace root (contains bot/)")
    parser.add_argument(
        "--check",
        required=True,
        choices=["static", "spinner", "serious"],
        help="Which sanity step to run",
    )
    parser.add_argument("--rounds", type=int, default=2, help="Number of rounds for spinner/serious matches")
    parser.add_argument("--seed", type=int, default=None, help="Seed for spinner/serious matches (defaults to first benchmark seed)")
    parser.add_argument("--server-jar", type=pathlib.Path, help="Optional path to server jar")
    parser.add_argument("--recorder-jar", type=pathlib.Path, help="Optional path to recorder jar")
    parser.add_argument("--java-bin", type=pathlib.Path, help="Optional path to java executable")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.exists():
        raise SystemExit(f"Workspace does not exist: {workspace}")

    if args.check == "static":
        run_static(workspace)
    else:
        opponent = args.check
        run_match(
            workspace=workspace,
            opponent=opponent,
            rounds=args.rounds,
            seed=args.seed,
            server_jar=args.server_jar,
            recorder_jar=args.recorder_jar,
            java_bin=args.java_bin,
        )


if __name__ == "__main__":
    main()
