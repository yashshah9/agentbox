"""Workspace snapshot save/restore for stateful agent runs."""

from __future__ import annotations

import tarfile
import uuid
from pathlib import Path


def save_snapshot(workspace: Path, snapshot_dir: Path) -> str:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = uuid.uuid4().hex
    archive = snapshot_dir / f"{snapshot_id}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in workspace.rglob("*"):
            if path.name in {"main.py", "main.js"}:
                continue
            tar.add(path, arcname=path.relative_to(workspace))
    return snapshot_id


def restore_snapshot(snapshot_id: str, workspace: Path, snapshot_dir: Path) -> None:
    archive = snapshot_dir / f"{snapshot_id}.tar.gz"
    if not archive.exists():
        raise FileNotFoundError(f"Unknown snapshot: {snapshot_id}")
    with tarfile.open(archive, "r:gz") as tar:
        try:
            tar.extractall(workspace, filter="data")
        except TypeError:
            tar.extractall(workspace)
