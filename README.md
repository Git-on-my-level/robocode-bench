# Robocode Tank Royale LLM Benchmark

This monorepo hosts the Tank Royale (Robocode) benchmark described in `SPEC.md`.

What’s here:
- Python orchestrator (`src/robocode_bench`) for workspace management, build checks, and hooks for match execution.
- Bot workspace template in `bot_template/` for LLMs to edit only under `bot/`.
- Battle rules + deterministic seeds in `battle_configs/` and pinned versions in `benchmark-config.yaml`.
- Tooling stubs (`tools/`) to fetch server/recorder/GUI jars and launch the GUI locally.

Quickstart:
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m robocode_bench.orchestrator prepare-workspace --model-id demo --attempt-id A1
PYTHONPATH=src python -m robocode_bench.orchestrator build-bot --workspace workspaces/demo/A1
```

Next steps:
- Download the Tank Royale stack: `python -m robocode_bench.orchestrator download-stack`
- Wire `orchestrator.evaluate` to your match runner once server/recorder jars are present.

More detail in `docs/DEV_ENV.md` and `docs/LLM_AGENT_WORKFLOW.md`.
