"""Download confirmed source files into data/raw/ and record SHA-256."""

from __future__ import annotations

import hashlib
import json
import tomllib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def load_sources(root: Path) -> dict:
    with (root / "configs" / "sources.toml").open("rb") as f:
        return tomllib.load(f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record_file(root: Path, key: str, src: dict) -> dict:
    raw = root / "data" / "raw"
    path = raw / src["file"]
    manifest_path = raw / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    entry = {
        "url": src["url"],
        "file": src["file"],
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    manifest[key] = entry
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def download(root: Path, key: str, src: dict) -> dict:
    raw = root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    path = raw / src["file"]
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".part")
        req = urllib.request.Request(src["url"], headers={"User-Agent": "rail-gap-map (personal research)"})
        with urllib.request.urlopen(req) as r, tmp.open("wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.replace(path)
    return record_file(root, key, src)


def raw_path(root: Path, key: str) -> Path:
    src = load_sources(root)[key]
    path = root / "data" / "raw" / src["file"]
    if not path.exists():
        raise FileNotFoundError(f"{key} がありません: {path}  先に `uv run ekiwalk fetch {key}` を実行してください")
    return path
