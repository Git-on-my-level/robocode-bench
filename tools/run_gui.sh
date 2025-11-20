#!/usr/bin/env bash
set -euo pipefail

JAR=${1:-tools/bin/robocode-tankroyale-gui-0.34.1.jar}
if [ ! -f "$JAR" ]; then
  echo "GUI jar not found at $JAR. Download with: python -m robocode_bench.orchestrator download-stack" >&2
  exit 1
fi
exec java -jar "$JAR"
