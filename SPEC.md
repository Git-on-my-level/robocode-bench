# LLM Robocode Coding Benchmark Specification

Version 1.0 — Tank Royale (Robocode) benchmark for LLM coding agents

---

## 0. Overview

This document defines a prescriptive benchmark for evaluating AI coding agents (LLMs) by having them generate Robocode Tank Royale bots that battle in a shared arena.

The benchmark is tied specifically to:

* **Robocode Tank Royale Server & Recorder** (Maven group `dev.robocode.tankroyale`) ([Maven Repository][1])
* **Robocode Tank Royale Bot APIs** (Python and/or Java/.NET) ([PyPI][2])
* **Official Robocode Tank Royale rules and scoring** as defined in the docs. ([Robocode][3])

This specification is intended for implementers of the benchmarking system, not for end-users or bot authors.

---

### Terminology

In this document, a single run of the pipeline for a given model (code generation + build + evaluation) is called a **variant**. Earlier drafts used the term “attempt”; treat “variant” as the canonical term.

---

## 1. Scope, Goals, and Non-Goals

### 1.1 Scope

The benchmark measures, for each coding agent:

* Ability to understand Tank Royale’s API and game rules.
* Ability to write correct, efficient, event-driven bot code.
* Quality of strategy (movement, targeting, radar, energy management).
* Robustness to compilation/runtime errors and tournament conditions.

### 1.2 Goals

The benchmark MUST:

1. Use Robocode Tank Royale as the *only* arena implementation.
2. Be deterministic and reproducible given the same model outputs.
3. Provide a fully automated pipeline:

   * Prompt model → generate bot source → build → run matches via Tank Royale server → collect results → compute scores.
4. Use Tank Royale’s scoring as the primary performance signal, with additional stability metrics. ([Robocode Dev][4])

### 1.3 Non-Goals

The benchmark does NOT aim to:

* Train bots or run RL loops; bots MUST be static at evaluation time.
* Evaluate GUI interaction.
* Allow bots to call external network services at runtime.

---

## 2. Tank Royale–Specific Environment

### 2.1 Game Components

The benchmark MUST use the following official components: ([Maven Repository][1])

* **Server**: `dev.robocode.tankroyale:robocode-tankroyale-server`
* **Recorder**: `dev.robocode.tankroyale:robocode-tankroyale-recorder`
* **Optional GUI**: `dev.robocode.tankroyale:robocode-tankroyale-gui` (not used in benchmark runs but useful during development).
* **Booter** (optional): `dev.robocode.tankroyale:robocode-tankroyale-booter`

The benchmark MUST run the **server and recorder headless**, without the GUI, to ensure automation.

### 2.2 Game Rules and Mechanics (Normative References)

The benchmark MUST follow Tank Royale rules as per the official docs, including: ([Robocode Dev][5])

* **Turn-based simulation** with a fixed turn timeout (e.g., 30–50 ms, configurable as a battle rule).
* **Bots & Teams**: this benchmark uses *non-team* classic battles only (no team bots in v1).
* **Energy model** (one pool per bot) with:

  * Damage from bullets and ramming.
  * Energy cost for firing bullets and collisions.
* **Gun, radar, and body** as separate controllable parts:

  * Body movement and turning.
  * Gun turning and firing obey gun heat and cooling rules.
  * Radar turning and scanning arc.
* **Skipped turns** when a bot exceeds its turn time budget.
* **Scoring system**:

  * Bullet Damage, Bullet Damage Bonus.
  * Survival Score, Last Survivor Bonus.
  * Ram Damage, Ram Damage Bonus.
  * Total score as sum of above, plus counts of 1st/2nd/3rd placements per round. ([Robocode Dev][4])

The benchmark MUST NOT alter the internal scoring formulas; instead it reads them from Tank Royale’s battle results.

### 2.3 Battle Configuration

For benchmark v1.0, the following server battle rules MUST be used (values can be configured via the server’s battle configuration mechanism):

* **Battlefield size**: `800 x 600` units (Tank Royale default).
* **Game types**:

  * 1v1 (two bots only) for duels.
  * Melee/classic for FFA (≥ 4 bots). ([Robocode][6])
* **Rounds per battle**: 10.
* **Maximum turns per round**: server default; MUST be fixed and logged.
* **Turn timeout**: 40 ms.
* **Gun cooling rate and other physics**: server defaults; MUST be logged and kept constant across runs. ([Robocode Dev][5])

The specific battle rule configuration MUST be stored as a JSON/YAML file checked into version control and referenced by the orchestrator.

---

## 3. Supported Bot Languages and APIs

### 3.1 Language Policy in v1.0

To avoid ambiguity and multi-language fairness issues, benchmark v1.0 MUST support exactly **one primary implementation language**, plus optionally one secondary language for baselines.

Recommended:

* **Primary**: Python 3.10+ using the official Tank Royale Python Bot API `robocode-tank-royale`. ([PyPI][2])
* **Optional secondary** (for baselines only): Java 17 or .NET using their official Bot APIs. ([NuGet][7])

All model-generated bots in v1.0 MUST use Python + the Python Bot API.

### 3.2 Python Bot API Usage (Normative)

Bots MUST subclass `robocode_tank_royale.bot_api.bot.Bot` and implement at least: ([PyPI][2])

* `async def run(self) -> None` as the main behavior loop.
* Event handlers such as:

  * `on_scanned_bot(self, e: ScannedBotEvent)`
  * `on_hit_by_bullet(self, e: HitByBulletEvent)`
  * Others as needed (e.g., wall hits, death, bullet hit, etc.).

Bots MUST be launched via an `async main()` and `asyncio.run(main())` pattern, as in the official example.

### 3.3 Bot Configuration and Metadata

The Python Bot API supports configuration via a JSON file or environment variables. ([PyPI][2])

The benchmark MUST use **JSON config files** placed in each bot’s workspace, plus environment variables for server connection:

* **Config file**: `bot-config.json` in the bot workspace root.

  * Contains at least:

    * `name`
    * `version`
    * `authors`
    * `description` (optional)
    * `homepage` (optional)
    * `countryCodes` (optional)
    * `gameTypes` (MUST include `"classic"` and/or `"1v1"` as appropriate)
    * `platform`, `progLang` (optional but recommended).
* **Environment variables** (set by orchestrator when launching bot process):

  * `SERVER_URL` (e.g., `ws://server:7654`)
  * `SERVER_SECRET` if the server requires secrets (MUST be set by orchestrator, never by the model).

If the Python API requires any additional config fields, these MUST be documented and included in the template given to the model.

---

## 4. System Architecture (Tank Royale Specific)

### 4.1 Components

1. **Benchmark Orchestrator**
2. **Model Adapter**
3. **Workspace Manager**
4. **Build & Packaging Runner** (Python environment setup)
5. **Tank Royale Server & Recorder**
6. **Match Runner** (server orchestration per battle)
7. **Scoring Engine** (reads Tank Royale results + additional metrics)
8. **Storage & Logging**
9. **(Optional) Leaderboard Service**

The orchestrator MUST be able to run a full evaluation for a given model via a single CLI/API entrypoint (e.g., `evaluate_model --model-id=<id> --config=...`).

### 4.2 Process Topology (Per Match)

* One **Tank Royale Server process**, configured for the desired battle.
* One **Tank Royale Recorder** (if separate) to record battles to file. ([Maven Repository][1])
* One OS process per bot:

  * Each bot connects to the server via WebSocket using the Python Bot API. ([PyPI][2])

All these processes MUST be run inside a container or sandbox for resource control and security.

---

## 5. Workspace and Build Pipeline

### 5.1 Workspace Layout

For each model `M` and variant `V`, the Workspace Manager MUST create:

```text
/workspaces/
  M/
    variant_V/
      prompts/
        initial_prompt.txt
        initial_response.txt
        repair_prompt.txt      # if used
        repair_response.txt    # if used
      bot/
        src/
          main.py              # or package directory
          ... other .py files ...
        bot-config.json
        venv/                  # optional, can be shared image-level instead
      server/
        battle-config.json
      logs/
        build.log
        server.log
        recorder.log
        matches/
          match_*.json
      results/
        metrics.json
```

### 5.2 Build & Packaging (Python)

For Python bots, building is minimal but MUST be explicit:

1. Create a virtual environment or use a pinned Docker image including:

   * Python 3.10+
   * `robocode-tank-royale` at pinned version (e.g., `0.34.1`). ([PyPI][2])
2. Verify that `main.py` or equivalent is executable:

   * Run `python -m py_compile` on all `.py` files.
3. If compilation (syntax) fails:

   * Record failure and optionally perform a repair attempt (see Section 7).

---

## 6. Model Interaction Protocol (Tank Royale–Specific)

### 6.1 Context Provided to the Model

Each model variant MUST receive identical context, consisting of:

1. **Task description**:

   * Explanation that the goal is to write a competitive Robocode Tank Royale bot (Python) that connects via the official Bot API and performs well in 1v1 and melee battles.

2. **Extract of Tank Royale Docs** (summarized, not full text):

   * Getting Started (rounds, turns, events, turn timeout). ([Robocode Dev][5])
   * Beyond the Basics (movement/gun/radar strategy concepts). ([Robocode][6])
   * Scoring (how Tank Royale scoring works). ([Robocode Dev][4])

3. **Python Bot API documentation** (summarized):

   * How to subclass `Bot`.
   * Available movement and firing commands (e.g., `forward`, `back`, `turn_left`, `turn_gun_right`, `fire`). ([PyPI][2])
   * Event handlers and the main `run()` loop.

4. **Starter Template**:

   * A minimal but valid skeleton project with:

     * `main.py` including a minimal `MyLLMBot(Bot)` stub.
     * Example `bot-config.json` with placeholder values.
   * Instructions to only modify specific files (e.g., `bot/src/**`) and not infrastructure files.

5. **Constraints**:

   * No external network calls inside the bot.
   * No file I/O outside the workspace.
   * Target runtime performance limits (see Section 10).
   * Pinned versions of Tank Royale server and Python API.

### 6.2 Output Format for Generated Code

The model MUST be instructed to output files in a structured format, e.g.:

````text
<file path="bot/src/main.py">
```python
# content
````

</file>

<file path="bot/bot-config.json">
```json
{ ... }
```
</file>
```

The orchestrator MUST parse this format and write each file to the corresponding path. Any deviation MUST be handled robustly, with best-effort parsing and explicit logging.

### 6.3 Generation Limits

For each variant:

* Max input tokens: fixed (e.g., 8k).
* Max output tokens: fixed (e.g., 8k).
* Temperature: fixed (e.g., 0.2).
* Top-p: fixed (e.g., 0.9).
* Max LLM calls:

  * 1 initial generation.
  * Optionally 1 repair call for build failures.

Parameters MUST be identical for all models in a benchmark run and MUST be logged.

---

## 7. Variant Lifecycle

### 7.1 Initial Generation

1. Orchestrator composes the initial prompt.
2. Model Adapter sends prompt; receives code and config.
3. Workspace Manager writes files to `bot/`.

If file parsing fails (e.g., missing `main.py` or `bot-config.json`):

* Orchestrator MAY attempt a small “fixup” call using the same model with a tightly scoped prompt, or mark the variant as malformed.

### 7.2 Build & Sanity Check

1. Build Runner runs `python -m py_compile` on `bot/src/**/*.py`.
2. Run a **single local dry-run**:

   * Start the Tank Royale server.
   * Launch the bot alone in a battle to ensure it can connect and step through a small number of turns.
   * If connection fails or repeated skipped turns occur from the start, treat as a build/runtime failure.

If build or dry-run fails:

* Record `build.log` and `dry_run.log`.
* If repair is allowed:

  * Construct a repair prompt including relevant file contents and error output.
  * Call the model once more.
  * Overwrite `bot/src` and `bot-config.json`.
  * Re-run build and dry-run once.
* If still failing:

  * Mark the variant as **BuildFailed**; score = 0 for battle metrics but still record everything for analysis.

### 7.3 Tournament Phase

On successful dry-run:

1. Register the bot for evaluation.
2. Run the full tournament configuration (Section 8).
3. Collect server and recorder logs per match.

During this phase, bot code MUST NOT be modified.

---

## 8. Match Design and Tank Royale Integration

### 8.1 Baseline Bots

The benchmark MUST define a fixed set of baseline bots, built from:

* Official sample bots for Python/Java/.NET (checked out at the same commit as the server version). ([Maven Repository][1])
* Optionally, additional hand-written bots representing different difficulties and strategies (e.g., simple rammer, random mover, turret gunner).

Baseline bots MUST:

* Be pinned to specific versions and source commits.
* Have their own `bot-config.json` and be launched via the same mechanism as model bots.
* NOT be provided as reference code inside the prompt to the model, to reduce trivial copying.

### 8.2 Match Types (Using Tank Royale Battle Modes)

The benchmark MUST run at least two match types:

1. **1v1 Duels**

   * Battle type: Tank Royale 1v1 game type. ([Robocode][6])
   * Participants: model bot vs one baseline bot.
   * For each baseline:

     * Seeds: e.g., 10 distinct seeds.
     * Rounds per seed: 10 rounds.

2. **Melee / Classic FFA**

   * Battle type: Tank Royale classic melee game type (≥ 4 bots). ([Robocode][6])
   * Participants: model bot + `N-1` baseline bots (e.g., total N = 6).
   * Seeds: e.g., 10 distinct seeds.
   * Rounds per seed: 10 rounds.

The orchestrator MUST ensure:

* Identical battle configuration across all models.
* Seeds are drawn from a deterministic sequence and logged for each match.
* No two model bots appear in the same match in v1.0 (model vs baselines only).

### 8.3 Using Tank Royale Recorder and Results

The Recorder component (or server’s built-in recording) MUST be used to save:

* Per-round scoreboard with:

  * Total score.
  * Bullet/Ram damage, bonuses.
  * Survival Score, Last Survivor Bonus.
  * 1sts/2nds/3rds counts. ([Robocode Dev][4])
* Per-round rankings and placements.
* Optionally, per-tick state for advanced analysis (optional in v1.0 due to volume).

Output format SHOULD be JSON; if Tank Royale uses a different format, implementer MUST implement a parser and canonical JSON representation.

---

## 9. Metrics and Scoring

### 9.1 Raw Per-Round Metrics

For each round, the Scoring Engine MUST extract for the model bot:

* `total_score` (Tank Royale’s total score). ([Robocode Dev][4])
* `bullet_damage`, `bullet_damage_bonus`.
* `ram_damage`, `ram_damage_bonus`.
* `survival_score`.
* `last_survivor_bonus`.
* `placement_rank` (1 = best).
* `alive_at_end` (boolean).
* `crashed_or_disqualified` (timeout, protocol violation, or process crash).

### 9.2 Per-Match Aggregation

For each battle (multi-round):

* `avg_total_score` (mean over rounds).
* `avg_rank` (mean placement rank).
* `winrate_round` (fraction of rounds where model bot ranks 1st).
* `avg_survival_score`, `avg_bullet_damage`, etc.

These are computed separately for:

* 1v1 vs each baseline.
* FFA matches.

### 9.3 Bot-Level Aggregation

Define measures:

1. **Baseline Performance Score (BPS)**

For each baseline bot `b`:

* Compute:

  * `score_1v1(b) = α * winrate_round + (1 - α) * normalized_avg_total_score`

Where:

* `winrate_round`: across all rounds in all 1v1 matches vs `b`.
* `normalized_avg_total_score`: scaled into [0,1] using a reference range (e.g., reference distribution from baselines vs each other).

Reasonable default: `α = 0.7`.

Then:

* `BPS = mean_b score_1v1(b)`

2. **FFA Performance Score (FPS)**

For each FFA round with `N` bots:

* Rank-based score:

  * `rank_score = (N - rank) / (N - 1)` (1st = 1, last = 0).

Aggregate:

* `FPS = mean(rank_score over all FFA rounds)`

Optionally combine with normalized total score in FFA; if so, that formula MUST be specified.

3. **Stability and Robustness Score (SRS)**

Compute:

* `crash_rate = (# rounds where crashed_or_disqualified) / (total rounds)`
* `performance_variance` across seeds (variance of total_score or rank_score).

Then define, for example:

```text
SRS = 0.5 * (1 - crash_rate)
    + 0.5 * (1 - normalized_performance_variance)
```

Where `normalized_performance_variance` scales observed variance range into [0,1].

### 9.4 Final Bot Score

The final score for a bot (one model variant) MUST be:

```text
BotScore = w_bps * BPS + w_fps * FPS + w_srs * SRS
```

Default weights:

* `w_bps = 0.5`
* `w_fps = 0.3`
* `w_srs = 0.2`

All components MUST be in [0,1].

### 9.5 Model-Level Score and Variants

If the benchmark allows multiple variants per model:

* v1.0 SHOULD use **Best-of-N**:

  * `ModelScore = max(BotScore over variants)`

Number of allowed variants (e.g., N=2) MUST be fixed and logged.

---

## 10. Determinism, Resource Limits, and Sandboxing

### 10.1 Determinism

Tank Royale is turn-based and designed for deterministic processing of bot intents per turn. ([Robocode][8])

To maintain determinism:

* All random decisions (spawn positions, initial headings, tie-breakers) MUST be driven from a seed passed into the server and recorded.
* Identical bot code, server version, battle config, and seed MUST produce identical outcomes.

### 10.2 Resource Limits

Bots run as independent processes; Tank Royale itself does not enforce CPU/RAM limits. ([Robocode][8])

The benchmark MUST enforce limits via containers or OS facilities:

* **Bot process limits**:

  * 1 vCPU.
  * 512 MB RAM.
  * Per-match wall-clock cap (e.g., 300 seconds).

* **Per-turn CPU budget**:

  * Observed via OS level or approximate; repeated turn timeouts (skipped turns) are tracked and impact SRS.

* **Build environment**:

  * 2 vCPU.
  * 4 GB RAM.
  * 120 s wall-clock timeout for build and dry-run.

If a process exceeds limits, it MUST be terminated and the relevant round marked as a crash.

### 10.3 Security

Generated code MUST be treated as untrusted:

* Run all bots in isolated containers without network access (except WebSocket to Tank Royale server within the same sandbox network).
* Mount only the bot workspace (no host filesystem access).
* Disable spawning of child processes where possible or at least constrain them with the same resource limits.

---

## 11. Fairness and Leakage Considerations

### 11.1 Equal Information

All models MUST:

* Receive the same version of Tank Royale documentation excerpts.
* Receive the same Python Bot API description and starter template.
* NOT receive any of the baseline bots’ source code or configuration.

### 11.2 Preventing Hidden Optimization

To reduce benchmark overfitting:

* Baseline bots and server version MUST be pinned per benchmark version and only changed via a new version (e.g., v1.1).
* Seeds SHOULD be rotated between benchmark versions, not within a version.
* Implementers SHOULD avoid publishing exact prompt text if they want to resist direct hard-coding.

---

## 12. Versioning, Configuration, and Reproducibility

### 12.1 Benchmark Versioning

Define:

* `benchmark_id`, e.g., `"llm-tank-royale-v1.0-python"`

Each version MUST fix:

* Tank Royale server, recorder, and bot API versions. ([Maven Repository][1])
* Battle configuration (battlefield size, rules).
* Baseline bots set and their versions.
* Evaluation pipeline (match counts, seeds, scoring weights).

### 12.2 Configuration File

A top-level configuration file, e.g. `benchmark-config.yaml`, MUST exist and include:

* Model generation limits (tokens, temperature, variants/repair calls).
* Battle configuration references (`battle-config.json` path).
* Seeds for all matches.
* Resource limits.
* Docker images (server, bot runtime).

This file MUST be saved with the evaluation artifacts and versioned.

### 12.3 Re-Runs

Given:

* A specific model’s response set (all prompts + outputs).
* The same `benchmark-config.yaml`.

The orchestrator MUST be able to rerun the evaluation and obtain identical scores (up to rounding).

---

## 13. Operational Considerations and Edge Cases

The implementation MUST address the following:

1. **Server startup and shutdown**

   * Wait for server WebSocket port to be ready before launching bots.
   * Cleanly stop server and recorder after each battle.

2. **Bot connection failures**

   * If a bot fails to connect within a timeout (e.g., 10 s), the battle is aborted and marked as a crash for that bot.

3. **Bot misbehavior**

   * If a bot repeatedly disconnects or sends malformed data (if bypassing Bot API), mark as disqualified.

4. **Non-terminating battles**

   * If a battle does not finish by the server’s internal rules (e.g., due to stalls), enforce a hard wall-clock timeout and abort, assigning a low score or re-running with a different seed, per a documented policy.

5. **Concurrency**

   * When running multiple evaluations in parallel, ensure CPU allocation does not exceed physical limits in a way that systematically penalizes some models (e.g., per-job CPU reservations).

6. **Logging**

   * For every failure (build, dry-run, match), logs MUST be preserved and linked to the model, variant, and match identifiers.

---

## 14. Minimal Implementation Checklist (Tank Royale–Specific)

An implementation of this benchmark MUST provide:

1. **Pinned Tank Royale stack**

   * Docker images or scripts for:

     * `robocode-tankroyale-server` (headless).
     * `robocode-tankroyale-recorder`.
   * Version numbers recorded in config. ([Maven Repository][1])

2. **Python runtime image**

   * Python 3.10+ with `robocode-tank-royale` at a pinned version. ([PyPI][2])

3. **Baseline bots**

   * Source and configs for sample or custom bots.
   * Build scripts and run commands.

4. **Orchestrator**

   * Code that:

     * Manages workspaces.
     * Calls models.
     * Writes bot files and config.
     * Spawns server, recorder, and bots.
     * Collects logs.
     * Computes scores using the formulas in Section 9.

5. **Instrumentation**

   * Tools to parse Tank Royale recorder outputs into structured JSON.
   * Metric computation and persistence.

6. **Documentation**

   * Public documentation that:

     * Describes the benchmark version.
     * Lists Tank Royale versions and rules used.
     * Explains the scoring interpretation.

---

This document, when followed, specifies a complete, Tank Royale–specific, reproducible environment for benchmarking LLM coding agents by having them generate competitive bots that battle in Robocode Tank Royale.

[1]: https://mvnrepository.com/artifact/dev.robocode.tankroyale "Maven Repository: dev.robocode.tankroyale"
[2]: https://pypi.org/project/robocode-tank-royale/?utm_source=chatgpt.com "Robocode Tank Royale - Python Bot API"
[3]: https://robocode.dev/?utm_source=chatgpt.com "Robocode Tank Royale Docs"
[4]: https://robocode-dev.github.io/tank-royale/articles/scoring.html?utm_source=chatgpt.com "Scoring | Robocode Tank Royale Docs"
[5]: https://robocode-dev.github.io/tank-royale/tutorial/getting-started.html?utm_source=chatgpt.com "Getting Started | Robocode Tank Royale Docs"
[6]: https://robocode.dev/tutorial/beyond-the-basics.html?utm_source=chatgpt.com "Beyond the Basics | Robocode Tank Royale Docs"
[7]: https://www.nuget.org/packages/Robocode.TankRoyale.BotApi/0.34.1?utm_source=chatgpt.com "Robocode.TankRoyale.BotApi 0.34.1"
[8]: https://robocode.dev/articles/tank-royale.html?utm_source=chatgpt.com "Tank Royale vs original Robocode"
