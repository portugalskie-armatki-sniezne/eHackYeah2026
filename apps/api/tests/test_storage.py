from pathlib import Path

import pytest

from app import storage


def test_upload_dir_comes_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "volume"))
    assert storage.upload_dir() == tmp_path / "volume"

    # relative paths start in apps/api, an empty value falls back to the default directory.
    api_dir = Path(storage.__file__).resolve().parent.parent
    monkeypatch.setenv("UPLOAD_DIR", "photos")
    assert storage.upload_dir() == api_dir / "photos"
    monkeypatch.setenv("UPLOAD_DIR", "")
    assert storage.upload_dir() == api_dir / "uploads"


def test_check_upload_dir_creates_writable_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "volume" / "photos"))

    storage.check_upload_dir()

    assert (tmp_path / "volume" / "photos").is_dir()
    assert not any((tmp_path / "volume" / "photos").iterdir())


def test_check_upload_dir_fails_when_not_writable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # a path below a file cannot be created, also when tests run as root.
    (tmp_path / "file").write_text("")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "file" / "photos"))

    with pytest.raises(RuntimeError, match="UPLOAD_DIR .* is not writable"):
        storage.check_upload_dir()


def test_atomic_save_is_readable_by_shared_volume_connectors(upload_dir: Path):
    key = "visualizations/test/result.png"
    storage.save(key, b"original")
    path = storage.file_path(key)
    assert path.read_bytes() == b"original"
    assert path.stat().st_mode & 0o004
    assert list(path.parent.iterdir()) == [path]


def test_failed_atomic_replace_preserves_existing_file(upload_dir: Path, monkeypatch: pytest.MonkeyPatch):
    key = "visualizations/test/result.png"
    storage.save(key, b"original")
    path = storage.file_path(key)

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(OSError):
        storage.save(key, b"replacement")
    assert path.read_bytes() == b"original"
    assert list(path.parent.iterdir()) == [path]
