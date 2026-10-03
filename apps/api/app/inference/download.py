from app.inference.models import CHECKPOINTS, ModelCheckpoint


def download(checkpoint: ModelCheckpoint) -> None:
    if checkpoint.downloaded():
        print(f"Model ready: {checkpoint.repository} at {checkpoint.path}")
        return
    from huggingface_hub import snapshot_download

    marker = checkpoint.path / "revision.txt"
    marker.unlink(missing_ok=True)
    snapshot_download(
        repo_id=checkpoint.repository,
        revision=checkpoint.revision,
        local_dir=checkpoint.path,
        allow_patterns=[*checkpoint.files, "README.md", "LICENSE*"],
    )
    if not all(
        (checkpoint.path / name).is_file() and (checkpoint.path / name).stat().st_size > 0 for name in checkpoint.files
    ):
        raise RuntimeError(f"Incomplete model download: {checkpoint.repository}")
    marker.write_text(checkpoint.revision + "\n")
    print(f"Model ready: {checkpoint.repository} at {checkpoint.path}")


def main() -> None:
    for checkpoint in CHECKPOINTS:
        download(checkpoint)


if __name__ == "__main__":
    main()
