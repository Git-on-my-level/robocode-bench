# Baseline Bots (stub)

Baseline bots are launched exactly like model bots and must live under `baselines/` with their own `bot-config.json`.
Populate this folder with:
- Simple reference bots (rammer, random mover, turret gunner)
- Official sample bots pinned to Tank Royale v0.34.1
- A stronger duelist baseline (e.g., `sample_bots/serious`) to sanity check match orchestration and scoring

Define each baseline in a manifest (TBD) so the orchestrator can include them in 1v1 + melee brackets.

Current sample set living under `sample_bots/`:
- `rammer`: closes distance and fires heavy shots up close.
- `spinner`: slow strafe with continuous radar/gun spin.
- `serious`: perpendicular strafe/aim with simple wall avoidance and energy-aware firepower.
