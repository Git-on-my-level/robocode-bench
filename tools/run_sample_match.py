#!/usr/bin/env python
"""Run a single 1v1 match between the two sample bots using the headless server."""
from __future__ import annotations

import asyncio
import os
import pathlib
import signal
import subprocess
from typing import List

from robocode_bench import tankroyale

ROOT = pathlib.Path(__file__).resolve().parents[1]
JAVA_BIN_PATH = pathlib.Path("/opt/homebrew/opt/openjdk@17/bin/java")
JAVA_BIN = JAVA_BIN_PATH if JAVA_BIN_PATH.exists() else None
TOOLS_BIN = ROOT / "tools" / "bin"
SERVER_JAR = TOOLS_BIN / "robocode-tankroyale-server-0.34.1.jar"
RECORDER_JAR = TOOLS_BIN / "robocode-tankroyale-recorder-0.34.1.jar"
PORT = 7654


async def controller_run(expected_bots: List[str]) -> list[dict]:
    import websockets
    import json

    url = f"ws://localhost:{PORT}"
    async with websockets.connect(url) as ws:
        msg = json.loads(await ws.recv())
        assert msg.get("type") == "ServerHandshake", f"Unexpected message: {msg}"
        server_session = msg["sessionId"]
        game_setup = msg.get("gameSetup")
        ctrl = {
            "type": "ControllerHandshake",
            "sessionId": server_session,
            "name": "bench-controller",
            "version": "0.1",
            "author": "bench",
        }
        await ws.send(json.dumps(ctrl))

        bots: dict[str, dict] = {}
        while len(bots) < len(expected_bots):
            payload = json.loads(await ws.recv())
            if payload.get("type") == "BotListUpdate":
                for bot in payload.get("bots", []):
                    bots[bot["name"]] = bot
        addresses = [{"host": bots[name]["host"], "port": bots[name]["port"]} for name in expected_bots]
        if not game_setup:
            game_setup = {
                "gameType": "classic",
                "arenaWidth": 800,
                "isArenaWidthLocked": True,
                "arenaHeight": 600,
                "isArenaHeightLocked": True,
                "minNumberOfParticipants": 2,
                "isMinNumberOfParticipantsLocked": False,
                "maxNumberOfParticipants": len(expected_bots),
                "isMaxNumberOfParticipantsLocked": False,
                "numberOfRounds": 1,
                "isNumberOfRoundsLocked": False,
                "gunCoolingRate": 0.1,
                "isGunCoolingRateLocked": False,
                "maxInactivityTurns": 450,
                "isMaxInactivityTurnsLocked": False,
                "turnTimeout": 40,
                "isTurnTimeoutLocked": False,
                "readyTimeout": 10000,
                "isReadyTimeoutLocked": False,
                "defaultTurnsPerSecond": 240,
            }
        else:
            game_setup = dict(game_setup)
            game_setup["numberOfRounds"] = 1
            game_setup["maxNumberOfParticipants"] = game_setup.get("maxNumberOfParticipants", len(expected_bots))
        start_game = {
            "type": "StartGame",
            "botAddresses": addresses,
            "gameSetup": game_setup,
        }
        await ws.send(json.dumps(start_game))

        game_results: list[dict] | None = None
        while True:
            try:
                payload = json.loads(await ws.recv())
            except websockets.ConnectionClosed:
                break
            if payload.get("type") == "GameEndedEventForObserver":
                game_results = payload.get("results", [])
                break
        return game_results or []


def launch_bot(path: pathlib.Path) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("SERVER_URL", f"ws://localhost:{PORT}")
    env.setdefault("PYTHONPATH", str(ROOT / "src"))
    return subprocess.Popen(["python", "main.py"], cwd=path, env=env)


def main() -> None:
    TOOLS_BIN.mkdir(parents=True, exist_ok=True)
    artifacts = tankroyale.download_stack("0.34.1", "0.34.1", "0.34.1", TOOLS_BIN)
    server = tankroyale.start_server(
        artifacts["server"],
        ROOT / "logs" / "sample-server.log",
        game_types=["classic", "1v1"],
        port=PORT,
        java_bin=JAVA_BIN,
        tps=240,
    )
    bots: list[subprocess.Popen] = []
    try:
        if not tankroyale.wait_for_port(port=PORT, timeout=5):
            raise RuntimeError("Server did not open WebSocket port in time")

        bots = [launch_bot(ROOT / "sample_bots" / "rammer"), launch_bot(ROOT / "sample_bots" / "spinner")]

        results: list[dict] = []
        try:
            results = asyncio.run(asyncio.wait_for(controller_run(["rammer", "spinner"]), timeout=60))
        finally:
            for p in bots:
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.send_signal(signal.SIGTERM)
        print("Results:")
        for r in results:
            print(
                f"- {r.get('name')}: total={r.get('totalScore')}, "
                f"survival={r.get('survival')}, bullet={r.get('bulletDamage')}"
            )
    finally:
        server.stop()


if __name__ == "__main__":
    main()
