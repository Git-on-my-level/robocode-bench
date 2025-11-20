# AGENTS GUIDE

Purpose: Build and evaluate Robocode Tank Royale bots written by LLMs on a fixed, reproducible benchmark.

What lives here
- Rules & scoring: SPEC.md (normative benchmark definition).
- Agent-facing context: docs/AGENT_CONTEXT.md + docs/TANK_ROYALE_OVERVIEW.md (physics, battle rules, seeds, scoring).
- Workflow: docs/LLM_AGENT_WORKFLOW.md (prompt contract, file format), docs/DEV_ENV.md (setup).
- Baselines: baselines/manifest.yaml (evaluation opponents; not exposed to models), docs/BASELINES.md (manifest shape).
- Orchestrator code: src/robocode_bench/ (workspace, battle runner, scoring, downloads).
- Bot template for models: bot_template/ (only bot/ is mutable by agents).
- Battle config + seeds: battle_configs/default.json, battle_configs/seeds.json; pinned stack versions in benchmark-config.yaml.

Core commands (run with PYTHONPATH=src)
- Prepare workspace: python -m robocode_bench.orchestrator prepare-workspace --model-id <id> --variant-id <v>
- Build bot: python -m robocode_bench.orchestrator build-bot --workspace <path>
- Download jars (optional checksums): python -m robocode_bench.orchestrator download-stack [--checksums checksums.json]
- Evaluate: python -m robocode_bench.orchestrator evaluate <workspace> --config benchmark-config.yaml --java-bin <path>

Saving curated artifacts (for deterministic replays)
- Copy a finished workspace into `bots/<model>/<variant>/`: `PYTHONPATH=src python -m robocode_bench.orchestrator save-artifact --workspace workspaces/<model>/<variant> --model-id <model> --variant-id <variant> [--dest-root bots --force]`.
- Captures `bot/src`, `bot/bot-config.json`, `prompts/initial_prompt.txt`, `prompts/initial_response.txt`, and writes `metadata.json` with model/variant ids, benchmark config path + sha256, template sha256, seeds, and per-file hashes.
- Transient outputs stay ignored (workspaces/, logs/, results/, __pycache__/, venvs, tools/bin/, recorder dumps).

Evaluation at a glance
- Uses baseline manifest for 1v1 + melee brackets; seeds from config/seeds file; battle rules from battle_configs/default.json.
- Scoring combines BPS (1v1), FPS (melee rank), SRS (stability) per scoring.py.
- Logs/results per workspace: logs/matches/*, logs/build.log, results/metrics.json.

Agent constraints (baked into prompts)
- Edit only bot/; no external network; deterministic seeds; Python bot API 0.34.1; turn timeout 40 ms; arena 800x600; game types classic + 1v1.

If you only read three files
1) SPEC.md — what “compliant” means.
2) docs/AGENT_CONTEXT.md — what the model sees about the game.
3) baselines/manifest.yaml — what you’re scored against (keep out of model context).
