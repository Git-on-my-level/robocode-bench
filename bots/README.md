# Curated Bots

Store immutable bot artifacts here as `bots/<model_id>/<variant_id>/`.

Populate via `python -m robocode_bench.orchestrator save-artifact --workspace workspaces/<model>/<variant> --model-id <model> --variant-id <variant> [--dest-root bots]`.

Artifacts should only include the bot sources/config, initial prompt/response, and metadata; transient logs/results stay under `workspaces/` and are ignored.
