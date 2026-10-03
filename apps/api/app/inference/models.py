from dataclasses import dataclass
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]


def resolve_model_path(path: str) -> Path:
    location = Path(path).expanduser()
    return location if location.is_absolute() else API_ROOT / location


@dataclass(frozen=True)
class ModelCheckpoint:
    repository: str
    revision: str
    directory: str
    files: tuple[str, ...]

    @property
    def path(self) -> Path:
        return resolve_model_path(f"models/{self.directory}")

    def downloaded(self) -> bool:
        marker = self.path / "revision.txt"
        return (
            marker.is_file()
            and marker.read_text().strip() == self.revision
            and all((self.path / name).is_file() and (self.path / name).stat().st_size > 0 for name in self.files)
        )


CHECKPOINTS = (
    ModelCheckpoint(
        repository="thaitea/laya-vision",
        revision="f2fe3c12cb6d04c59d8a190250bf3fb40fc828dc",
        directory="laya-vision",
        files=(
            "model.safetensors",
            "vlm_agent_config.json",
            "backbone/config.json",
            "processor/processor_config.json",
            "processor/tokenizer.json",
            "processor/tokenizer_config.json",
            "processor/chat_template.jinja",
        ),
    ),
    ModelCheckpoint(
        repository="Helsinki-NLP/opus-mt-pl-en",
        revision="7f2bb874fdfb6139f9842b91a9b75c4a6c93401c",
        directory="opus-mt-pl-en",
        files=(
            "config.json",
            "generation_config.json",
            "pytorch_model.bin",
            "source.spm",
            "target.spm",
            "tokenizer_config.json",
            "vocab.json",
        ),
    ),
)
