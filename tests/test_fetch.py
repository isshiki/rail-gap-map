import hashlib
import json

from ekiwalk.fetch import load_sources, record_file


def test_load_sources(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "sources.toml").write_text(
        '[a]\nurl = "https://example.org/a.zip"\nfile = "a.zip"\nsize_hint = "1 MB"\nlicense = "CC BY 4.0"\n',
        encoding="utf-8",
    )
    s = load_sources(tmp_path)
    assert s["a"]["file"] == "a.zip"


def test_record_file_writes_sha256(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    f = raw / "a.zip"
    f.write_bytes(b"hello")
    record_file(tmp_path, "a", {"url": "https://example.org/a.zip", "file": "a.zip"})
    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["a"]["sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert manifest["a"]["bytes"] == 5
    assert manifest["a"]["retrieved_utc"].endswith("Z")
