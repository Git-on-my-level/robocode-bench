# Development Environment

This repository is intentionally minimal but is structured to run the Tank Royale benchmark described in `SPEC.md`.

## Prerequisites
- Python 3.10+
- Java 17+ (for Tank Royale server/recorder/GUI jars)
- `pip install -r requirements.txt`

Optional but recommended:
- `uv` or `pipx` for isolated installations
- Docker, if you prefer containerizing bot runs

## Layout
- `benchmark-config.yaml` pins versions, seeds, and resource limits.
- `battle_configs/` holds the battle rules and deterministic seeds.
- `bot_template/` is copied into each workspace to bootstrap an LLM-authored bot.
- `src/robocode_bench/` contains the orchestrator, scoring, and workspace helpers.
- `tools/` holds helper scripts (download Tank Royale stack, launch GUI).

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m robocode_bench.orchestrator prepare-workspace --model-id demo --attempt-id A1
PYTHONPATH=src python -m robocode_bench.orchestrator build-bot --workspace workspaces/demo/A1
```

To download the Tank Royale server/recorder/GUI jars into `tools/bin`:
```bash
python -m robocode_bench.orchestrator download-stack --config benchmark-config.yaml
```

## Notes
- The orchestrator is designed to run headless benchmark matches; the GUI launcher in `tools/run_gui.sh` is for local debugging only.
- Resource limits described in `SPEC.md` should be enforced by your container/runtime; hooks are provided in the orchestrator to track crashes/timeouts.
- Recorder output parsing and match orchestration live in `src/robocode_bench`; extend these modules if you need tighter integration with your infra.
