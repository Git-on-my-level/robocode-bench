# LLM Agent Workflow

This document captures the contract between the orchestrator and the coding model for Tank Royale.

## What the model sees
- Task: write a competitive Python bot for Robocode Tank Royale that plays both 1v1 and classic melee.
- Context: summarized Tank Royale rules, Python Bot API usage, scoring, and constraints (no network, no filesystem escape, deterministic seeds). The shared doc bundle includes `SPEC.md`, `docs/TANK_ROYALE_OVERVIEW.md`, and `docs/AGENT_CONTEXT.md` with the exact battle rules, seeds, and scoring formulas the benchmark uses.
- Template: the contents of `bot_template/` copied into the variant workspace.

## What the model must output
Use the file-oriented format:
````
<file path="bot/src/main.py">
```python
# code
```
</file>

<file path="bot/bot-config.json">
```json
{ ... }
```
</file>
````

Only files under `bot/` may be modified by the model. The orchestrator writes these files straight into the workspace.

## Variant lifecycle (per SPEC.md)
1. Orchestrator composes the prompt (task + docs + template) and calls the model.
2. Workspace manager writes files to `workspaces/<model>/<variant>/bot/`.
3. Build runner compiles Python sources via `python -m py_compile`.
4. Dry-run: start headless server, launch bot alone, ensure it connects and steps.
5. If build/dry-run fails and repair is allowed, orchestrator issues one repair call with logs + file contents.
6. Tournament: run configured 1v1 + melee brackets vs baseline bots, collecting recorder JSON.
7. Scoring: aggregate per Section 9 of `SPEC.md` and write `results/metrics.json`.

## Constraints surfaced to the model
- Must subclass `robocode_tank_royale.bot_api.bot.Bot` and implement `async def run(...):` plus any event handlers.
- Use the provided `bot-config.json` shape; orchestrator sets `SERVER_URL` and secrets as env vars.
- `ScannedBotEvent` exposes `x`, `y`, `energy`, `direction`, `speed` but no bearing/distance helpers; use `bearing_to(x, y)` or `gun_bearing_to(x, y)` to aim and `distance_to(x, y)` for range-based firepower.
- The Python Bot API does not expose `set_max_speed`; movement is controlled via `set_forward` or `set_back` and capped by the engine (8 units/turn).
- No external network calls and no file I/O outside `bot/`.
- Respect turn timeout (40 ms) to avoid skipped turns.

## Files written per variant
```
prompts/               # prompt/response transcripts
bot/                   # model-written code + config
server/battle-config.json
logs/build.log         # py_compile + build output
logs/recorder.log      # one per match
results/metrics.json   # final scores (BPS/FPS/SRS)
```

## Workspace isolation
- Each model gets its own root under `workspaces/<model_id>/<variant_id>/`; nothing from other variants is visible.
- Shared docs live in `workspaces/_shared_docs/` and contain only the curated benchmark/spec files copied at workspace prep time.
- Only the bot template and those shared docs are exposed to the model; baseline or peer bots are not placed in the workspace.

Extend or shrink the prompt as long as these invariants hold; the rest of the pipeline stays deterministic via `benchmark-config.yaml` and the seed list.
