import sys
from unittest.mock import Mock

import pytest

from app.inference import models, runtime
from app.inference.download import download


@pytest.fixture
def checkpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(models, "API_ROOT", tmp_path)
    return models.ModelCheckpoint("example/model", "pinned-revision", "example", ("weights", "config.json"))


@pytest.fixture
def hub(monkeypatch):
    module = Mock()
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    return module


def test_download_uses_pinned_revision_and_reuses_complete_checkpoint(checkpoint, hub):
    def snapshot_download(**kwargs):
        assert kwargs["repo_id"] == checkpoint.repository
        assert kwargs["revision"] == checkpoint.revision
        assert kwargs["local_dir"] == checkpoint.path
        assert set(checkpoint.files) <= set(kwargs["allow_patterns"])
        checkpoint.path.mkdir(parents=True)
        for name in checkpoint.files:
            (checkpoint.path / name).write_text("contents")

    hub.snapshot_download.side_effect = snapshot_download
    download(checkpoint)
    assert checkpoint.downloaded()
    download(checkpoint)
    hub.snapshot_download.assert_called_once()


@pytest.mark.parametrize("failure", ["interrupted", "missing", "empty"])
def test_failed_download_never_leaves_a_completion_marker(checkpoint, hub, failure):
    checkpoint.path.mkdir(parents=True)
    marker = checkpoint.path / "revision.txt"
    marker.write_text("old-revision")
    if failure == "interrupted":
        hub.snapshot_download.side_effect = RuntimeError("interrupted")
    elif failure == "empty":
        for name in checkpoint.files:
            (checkpoint.path / name).touch()
    with pytest.raises(RuntimeError):
        download(checkpoint)
    assert not marker.exists()
    assert not checkpoint.downloaded()


@pytest.mark.parametrize("damage", ["revision", "missing", "empty"])
def test_incomplete_or_stale_checkpoint_is_not_reused(checkpoint, damage):
    checkpoint.path.mkdir(parents=True)
    for name in checkpoint.files:
        (checkpoint.path / name).write_text("contents")
    (checkpoint.path / "revision.txt").write_text(checkpoint.revision)
    assert checkpoint.downloaded()
    if damage == "revision":
        (checkpoint.path / "revision.txt").write_text("another-revision")
    elif damage == "missing":
        (checkpoint.path / "weights").unlink()
    else:
        (checkpoint.path / "weights").write_text("")
    assert not checkpoint.downloaded()


def test_relative_paths_are_resolved_from_api_workspace_independently_of_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    classifier = Mock()
    translator = Mock()
    monkeypatch.setattr(runtime, "local_classifier", classifier)
    monkeypatch.setattr(runtime, "local_translator", translator)
    monkeypatch.setenv("LAYA_MODEL_PATH", "models/laya-vision")
    monkeypatch.setenv("TRANSLATION_MODEL_PATH", "models/opus-mt-pl-en")
    classifier_provider = runtime.configured_classifier()
    translator_provider = runtime.configured_translator()
    classifier.assert_not_called()
    translator.assert_not_called()
    classifier_provider.classify(Mock())
    translator_provider.translate(Mock())
    assert classifier.call_args.args[0] == str(models.API_ROOT / "models/laya-vision")
    assert translator.call_args.args[0] == str(models.API_ROOT / "models/opus-mt-pl-en")
    assert models.resolve_model_path(str(tmp_path)) == tmp_path
