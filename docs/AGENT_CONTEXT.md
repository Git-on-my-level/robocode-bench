# Agent Context for Tank Royale Benchmark

This bundle is all the info you get inside the workspace. Use it to design a competitive Python bot without guessing hidden rules.

## What you are building
- A Python 3.10+ bot using `robocode-tank-royale==0.34.1`; subclass `Bot`, implement `async def run()` and event handlers.
- Your bot plays both 1v1 duels and classic melee on the same arena. Baseline opponents are fixed but undisclosed; assume a mix of rammers, strafers, and turret gunners.
- Only edit files under `bot/`. No external network calls; stay within the workspace filesystem.

## Arena & battle rules (pinned)
- Battlefield: `800 x 600`
- Game types enabled: `classic`, `1v1`
- Rounds per battle: `10`
- Seeds (per battle): `[1843, 99127, 8734, 42199, 14, 901, 712, 827, 102233, 19937]`
- Turn timeout: `40 ms`; turns per second: `60`
- Gun cooling rate: `0.1`; guns start hot each round
- Max inactivity turns: `450`; ready timeout: `10_000` ms
- Arena walls on; self color allowed

## Tournament format (v1.0 defaults)
- 1v1: your bot vs each baseline across the seed list above, 10 rounds per battle.
- Melee: your bot + multiple baselines (no teams) in classic mode; same seeds + 10 rounds per battle. Plan for at least 6 total participants.
- Battle rules come from `battle-config.json` in your workspace; seeds are copied into `server/seeds.json`.

## Scoring (normalized per SPEC)
- Per round: Tank Royale totals (bullet/ram damage + bonuses, survival, last survivor).
- 1v1 metric per baseline: `α * winrate_round + (1-α) * normalized_avg_total_score` with `α = 0.7`.
- FFA metric: rank_score = `(N - rank) / (N - 1)` averaged over rounds.
- Stability: penalizes crashes/skipped turns variance; avoid timeouts and hanging loops.

## Physics cheat sheet
- Max speed 8 u/t; accel 1, decel 2.
- Body turn rate: `10 - 0.75 * |speed|` deg/t (≈4 at max speed).
- Gun turn max 20 deg/t; radar turn max 45 deg/t.
- Firepower 0.1–3.0; bullet speed `20 - 3*power`; gun heat added `(1 + power) / 5`; cannot fire if `gunHeat > 0`.
- Energy: start ~100; firing costs firepower; bullet hit returns `3 * power`; wall hits cause damage; ram deals damage/bonus but stops you.
- Radar scans inside its sweep arc (previous→current direction); scanning every turn is key.

## Practical constraints & tips
- Keep per-turn work <40 ms; prefer simple math over heavy loops. Await `go()` every turn.
- Maintain radar lock or sweep continuously; consider narrow lock when tracking and wide sweep when blind.
- Energy management beats alpha striking: lower firepower when far/low energy.
- Avoid walls: add margin checks or perpendicular strafing.
- Determinism: seeds and configs are fixed—no randomness needed beyond your own tactics.
