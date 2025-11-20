# Robocode Tank Royale Notes

Collected reference notes from the official Tank Royale docs and schemas to guide benchmark + bot work without re-reading the upstream repo.

## Architecture & Components
- Game is fully deterministic per turn: bots send an **intent** each turn, server applies all intents to produce the next state.
- Communication is WebSocket + JSON (schemas in `schema/schemas`). Bots/observers/controllers are decoupled; any language can implement the protocol.
- Core roles: **server** runs battles and enforces rules; **bots** send intents only and see limited state; **observers** get full read-only state; **controllers** can start/stop/pause/resume/change TPS etc.; **GUI** and **recorder** are observer/controller implementations; **Booter** can launch local bots and inject boot-id into handshake.

## Bot Lifecycle & Protocol (schemas/README.md)
- Join: server sends `server-handshake` (session-id, optional secret). Bot replies `bot-handshake` (session-id, secret, optional boot-id). Observers/controllers use corresponding handshakes. A `bot-list-update` is broadcast on join/leave.
- Start game: controller sends `start-game` with selected bots. Server sends `game-started-event-for-bot`; each bot must reply `bot-ready` before the ready timer expires. If min participants (rule) are not met before timeout, game is aborted.
- Turn loop: each turn server sends `tick-event-for-bot` (bot state, bullet states, per-turn events) to bots and `tick-event-for-observer` to observers/controllers. Bot must send `bot-intent` before **turn timeout** (typically 30–50 ms configurable per battle); otherwise it receives `skipped-turn-event`.
- Round/game events: `round-started-event`, `round-ended-event`, `won-round-event`, `game-ended-event-*`, `game-aborted-event`.
- Control: controller can `pause-game`, `resume-game`, `next-turn` (single-step while paused), `stop-game` (abort), `change-tps`, and `set-debugging-enabled-for-bot`. Debug graphics from bots are only drawn if the bot is permitted.

## Key Message Schemas
- `bot-intent`: per-turn commands; omitted fields reuse last set value.
  - Movement/aim: `turnRate`, `gunTurnRate`, `radarTurnRate` (deg/turn); `targetSpeed` (units/turn).
  - Firing: `firepower` (0.1–3.0; exclusive min 0).
  - Adjust flags: `adjustGunForBodyTurn`, `adjustRadarForBodyTurn`, `adjustRadarForGunTurn`.
  - Utility: `rescan` (reuse previous radar direction/sweep), `fireAssist`, `teamMessages` (array up to 4 per turn), `debugGraphics` (string), `stdOut`/`stdErr`, color overrides for body/turret/radar/gun/bullet/scan/tracks.
- `tick-event-for-bot`: contains `roundNumber`, `botState`, `bulletStates` (bullets fired by this bot), and `events` (per-turn event list).
- `bot-state` (fields visible to the bot about itself): `energy`, `x`, `y`, `direction`, `gunDirection`, `radarDirection`, `radarSweep`, `speed`, `turnRate`, `gunTurnRate`, `radarTurnRate`, `gunHeat`, `enemyCount`, optional colors, `isDroid`, `isDebuggingEnabled`.
- Team messaging: `team-message` schema supports addressed or broadcast messages; bots receive them via `team-message-event`.

## Game Rules & Physics (articles/physics.md, tutorial/getting-started.md, articles/tank-royale.md)
- Time is turn-based; rounds start at turn 1; typical turn timeout 30–50 ms (battle rule).
- Energy: bots start at 100 energy (Droids: 120, but no scanner). Energy is spent when firing and lost on damage; bots with 0 energy are disabled. Friendly fire does not cause damage.
- Movement:
  - Acceleration 1 unit/turn; deceleration 2 units/turn; max speed 8 units/turn.
  - Body turn rate max: `10 - 0.75 * |speed|` deg/turn (4 deg/turn at max speed).
  - Gun turn rate max 20 deg/turn; radar turn rate max 45 deg/turn.
- Radar: detects bots within 1200 units inside its sweep arc (angle between previous and current radar direction). Zero sweep => no scans; `scanned-bot-event` fires only when within sweep.
- Bullets:
  - Firepower 0.1–3.0; energy cost equals firepower; cannot fire if `gunHeat > 0`.
  - Gun heat added per shot: `(1 + firepower) / 5`; guns start hot at heat 3 each round.
  - Bullet speed: `20 - 3 * firepower` units/turn (19.7 at power 0.1; 11 at power 3).
  - Damage when hit: `4 * firepower` plus `2 * (firepower - 1)` if firepower > 1.
  - Energy gain to shooter on hit: `3 * firepower`.
- Collisions:
  - Bot-bot collision: each takes 0.6 damage; ramming (moving forward into opponent) still stops the bot but yields ram score bonus.
  - Wall collision damage: `abs(speed)/2 - 1` (floored at 0); bot stops.
- Turn limits: if intent not received before timeout, turn is skipped; movement/fire not updated; `skipped-turn-event` emitted.

## Scoring (articles/scoring.md)
- Bullet damage: +1 point per damage done.
- Bullet damage bonus: +20% of all damage done to a bot when you kill it with bullets.
- Survival: +50 points each time another bot dies while you are alive.
- Last survivor: +10 points per opponent killed (awarded to final survivor).
- Ram damage: +2 points per damage done by ramming.
- Ram damage bonus: +30% of all ram damage inflicted on a bot you kill by ramming.
- Totals determine ranks; 1sts/2nds/3rds count placements per round (not directly scored).

## Game Types (articles/game_types.md)
- `classic`: 800x600 arena; min 2 participants; no max.
- `1v1`: 800x600; exactly 2 participants.
- `melee`: 1000x1000; min 10 participants; no max. Custom game types are supported via config.

## Practical Benchmark Hints
- To run bots without the provided APIs, implement the WebSocket protocol: handle handshakes, send a `bot-intent` every tick before timeout, and process `tick-event-for-bot` plus per-turn events.
- Intents can omit unchanged fields; server reuses last values. Use `rescan` if you want to repeat the previous radar sweep without changing angles.
- Respect turn timeout to avoid skipped turns; for LLM bots include a fast-path fallback intent.
- Debug drawing allowed only if controller enables it; otherwise server drops `debugGraphics`.
- Booter can launch bots locally and supply `boot-id` for metadata; not required if you connect directly.
