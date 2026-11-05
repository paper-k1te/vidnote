"""whisper 依赖包：下载、解压与安全校验，不联网。"""

import zipfile
from pathlib import Path

import pytest

from vidnote import whisper_deps


def _make_deps_zip(path: Path, *, include_required: bool = True) -> Path:
    with zipfile.ZipFile(path, "w") as bundle:
        if include_required:
            for name in whisper_deps._REQUIRED:
                bundle.writestr(f"{name}/__init__.py", "")
        bundle.writestr("bundle.txt", "ok")
    return path


def test_install_from_local_zip(monkeypatch, tmp_path: Path) -> None:
    archive = _make_deps_zip(tmp_path / "deps.zip")
    monkeypatch.setenv("VIDNOTE_CACHE", str(tmp_path))
    monkeypatch.setenv("VIDNOTE_WHISPER_DEPS_URL", str(archive))

    result = whisper_deps.install()

    assert result["ok"] is True
    assert whisper_deps.installed()
    root = whisper_deps.deps_dir()
    assert all((root / name).is_dir() for name in whisper_deps._REQUIRED)
    assert (root / "bundle.txt").exists()


def test_install_can_replace_existing_dir(monkeypatch, tmp_path: Path) -> None:
    archive = _make_deps_zip(tmp_path / "deps.zip")
    monkeypatch.setenv("VIDNOTE_CACHE", str(tmp_path))
    monkeypatch.setenv("VIDNOTE_WHISPER_DEPS_URL", str(archive))

    whisper_deps.install()
    result = whisper_deps.install()

    assert result["ok"] is True
    assert whisper_deps.installed()


def test_install_rejects_incomplete_zip(monkeypatch, tmp_path: Path) -> None:
    archive = _make_deps_zip(tmp_path / "deps.zip", include_required=False)
    monkeypatch.setenv("VIDNOTE_CACHE", str(tmp_path))
    monkeypatch.setenv("VIDNOTE_WHISPER_DEPS_URL", str(archive))

    with pytest.raises(whisper_deps.DepsError):
        whisper_deps.install()


def test_extract_rejects_unsafe_paths(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../evil.txt", "x")

    with zipfile.ZipFile(archive) as bundle, pytest.raises(whisper_deps.DepsError):
        whisper_deps._safe_extract(bundle, tmp_path / "out")


def test_download_url_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("VIDNOTE_WHISPER_DEPS_URL", "https://example.com/deps.zip")
    assert whisper_deps.download_url() == "https://example.com/deps.zip"
