#!/usr/bin/env bash
set -euo pipefail

CONFIG=${1:-benchmark-config.yaml}
export PYTHONPATH=${PYTHONPATH:-src}
python -m robocode_bench.orchestrator download-stack --config "$CONFIG"
