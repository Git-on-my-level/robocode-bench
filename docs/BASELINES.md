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

## Manifest (v1)
- Source of truth: `baselines/manifest.yaml` (not copied into `_shared_docs` to avoid leaking opponents to the model).
- Shape:
  ```yaml
  version: 1
  melee_participants: 6  # total bots in classic melee battles (model + baselines)
  bots:
    - id: rammer
      name: Rammer
      path: sample_bots/rammer
      game_types: ["classic", "1v1"]
      role: "close-range rammer with heavy firepower"
    # add more entries here
  ```
- Keep paths relative to repo root; orchestrator/run scripts can resolve them before launching battles.
- If you add or swap baseline bots, update this manifest and bump `version` when behavior changes.
- Loader: `robocode_bench.baselines.load_manifest()` resolves paths relative to the repo root; pass `validate_paths=False` to inspect manifests without requiring bot files to exist locally.
