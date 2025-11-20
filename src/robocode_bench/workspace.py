from __future__ import annotations

import json
import os
import shutil
import pathlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkspacePaths:
    root: pathlib.Path
    prompts: pathlib.Path
    bot: pathlib.Path
    bot_src: pathlib.Path
    logs: pathlib.Path
    results: pathlib.Path
    server: pathlib.Path
    shared_docs: pathlib.Path | None = None


class WorkspaceManager:
    """Create and manage benchmark workspaces following SPEC.md layout."""

    def __init__(self, base_dir: pathlib.Path):
        self.base_dir = base_dir

    def create(
        self,
        model_id: str,
        variant_id: str,
        template_dir: pathlib.Path,
        shared_docs: list[pathlib.Path] | None = None,
    ) -> WorkspacePaths:
        root = self.base_dir / model_id / variant_id
        prompts = root / "prompts"
        bot = root / "bot"
        bot_src = bot / "src"
        logs = root / "logs" / "matches"
        results = root / "results"
        server = root / "server"
        shared_root = self.base_dir / "_shared_docs" if shared_docs else None

        for path in [prompts, bot_src, logs, results, server]:
            path.mkdir(parents=True, exist_ok=True)

        self._copy_template(template_dir, bot)
        if shared_docs and shared_root:
            self._copy_shared_docs(shared_docs, shared_root)
        return WorkspacePaths(
            root=root,
            prompts=prompts,
            bot=bot,
            bot_src=bot_src,
            logs=logs,
            results=results,
            server=server,
            shared_docs=shared_root,
        )

    def _copy_template(self, template_dir: pathlib.Path, dest: pathlib.Path) -> None:
        for item in template_dir.iterdir():
            dest_item = dest / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_item)

    def _copy_shared_docs(self, items: list[pathlib.Path], dest_dir: pathlib.Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            src = item.resolve()
            target = dest_dir / src.name
            if src.is_dir():
                shutil.copytree(src, target, dirs_exist_ok=True)
            else:
                shutil.copy2(src, target)

    @staticmethod
    def write_prompt(paths: WorkspacePaths, name: str, content: str) -> pathlib.Path:
        target = paths.prompts / f"{name}.txt"
        target.write_text(content, encoding="utf-8")
        return target

    @staticmethod
    def record_build_log(paths: WorkspacePaths, name: str, content: str) -> pathlib.Path:
        target = paths.root / "logs" / f"{name}.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    @staticmethod
    def write_results(paths: WorkspacePaths, name: str, payload: dict) -> pathlib.Path:
        target = paths.results / f"{name}.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return target

    @staticmethod
    def write_match_log(paths: WorkspacePaths, name: str, content: str) -> pathlib.Path:
        target = paths.logs / f"{name}.log"
        target.write_text(content, encoding="utf-8")
        return target
