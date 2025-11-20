from __future__ import annotations

import datetime
import os
import pathlib
import socket
import subprocess
import time
import urllib.request
import hashlib
from dataclasses import dataclass
from typing import Iterable, Optional

DEFAULT_PORT = 7654
MAVEN_BASE = "https://repo1.maven.org/maven2/dev/robocode/tankroyale"


@dataclass
class TankRoyaleProcess:
    name: str
    process: subprocess.Popen
    log_path: pathlib.Path

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


def artifact_url(artifact: str, version: str) -> str:
    jar = f"{artifact}-{version}.jar"
    return f"{MAVEN_BASE}/{artifact}/{version}/{jar}"


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_artifact(artifact: str, version: str, dest_dir: pathlib.Path, expected_sha256: str | None = None) -> pathlib.Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{artifact}-{version}.jar"
    sidecar = dest_dir / f"{artifact}-{version}.sha256"
    expected = expected_sha256 or (sidecar.read_text().strip().split()[0] if sidecar.exists() else None)
    if target.exists():
        if expected and _sha256(target) != expected:
            raise ValueError(f"Checksum mismatch for existing {target}")
        return target
    url = artifact_url(artifact, version)
    with urllib.request.urlopen(url) as resp, target.open("wb") as fh:  # type: ignore[arg-type]
        fh.write(resp.read())
    if expected:
        actual = _sha256(target)
        if actual != expected:
            target.unlink(missing_ok=True)
            raise ValueError(f"Checksum mismatch for {target} (expected {expected}, got {actual})")
    return target


def download_stack(server: str, recorder: str, gui: str, dest_dir: pathlib.Path, checksums: dict[str, str] | None = None) -> dict[str, pathlib.Path]:
    checksums = checksums or {}
    artifacts = {
        "server": download_artifact("robocode-tankroyale-server", server, dest_dir, checksums.get("server")),
        "recorder": download_artifact("robocode-tankroyale-recorder", recorder, dest_dir, checksums.get("recorder")),
        "gui": download_artifact("robocode-tankroyale-gui", gui, dest_dir, checksums.get("gui")),
    }
    return artifacts


def wait_for_port(host: str = "127.0.0.1", port: int = DEFAULT_PORT, timeout: float = 10.0) -> bool:
    end = datetime.datetime.now().timestamp() + timeout
    while datetime.datetime.now().timestamp() < end:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def start_server(
    jar_path: pathlib.Path,
    log_path: pathlib.Path,
    game_types: Iterable[str],
    port: int = DEFAULT_PORT,
    tps: int = 60,
    enable_initial_position: bool = False,
    java_bin: Optional[pathlib.Path] = None,
) -> TankRoyaleProcess:
    java_cmd = str(java_bin or os.environ.get("JAVA_BIN") or "java")
    cmd = [
        java_cmd,
        "-jar",
        str(jar_path),
        f"--games={','.join(game_types)}",
        f"--port={port}",
        f"--tps={tps}",
    ]
    if enable_initial_position:
        cmd.append("--enable-initial-position")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
    return TankRoyaleProcess(name="server", process=proc, log_path=log_path)


def start_recorder(
    jar_path: pathlib.Path,
    log_path: pathlib.Path,
    server_url: str = f"ws://localhost:{DEFAULT_PORT}",
    output_dir: Optional[pathlib.Path] = None,
    secret: Optional[str] = None,
    java_bin: Optional[pathlib.Path] = None,
) -> TankRoyaleProcess:
    java_cmd = str(java_bin or os.environ.get("JAVA_BIN") or "java")
    cmd = [
        java_cmd,
        "-jar",
        str(jar_path),
        f"--url={server_url}",
    ]
    if secret:
        cmd.append(f"--secret={secret}")
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        cmd.append(f"--dir={output_dir}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
    return TankRoyaleProcess(name="recorder", process=proc, log_path=log_path)
