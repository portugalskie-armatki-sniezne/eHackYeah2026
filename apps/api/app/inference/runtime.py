import json
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

from app.inference.calibration import ContextCalibratedAgent
from app.inference.contracts import (
    ClassificationRequest,
    ClassificationResult,
    ImageInput,
    InferenceInputError,
    InferenceUnavailableError,
    InvalidInferenceResultError,
    TranslationRequest,
)
from app.inference.laya import LayaClassifier
from app.inference.models import resolve_model_path

_loading_lock = Lock()


class LocalTranslator:
    def __init__(self, model_path: str, source_language: str, target_language: str) -> None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self._source = source_language
        self._target = target_language
        self._tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True).eval()
        self._lock = Lock()

    def translate(self, request: TranslationRequest) -> str:
        try:
            return self._translate(request)
        except RuntimeError as error:
            raise InferenceUnavailableError("Translation failed") from error

    def _translate(self, request: TranslationRequest) -> str:
        import torch

        if (request.source_language, request.target_language) != (self._source, self._target):
            raise InferenceInputError("Unsupported translation language pair")
        sentences = [part for part in re.split(r"(?<=[.!?])\s+|\n+", request.text) if part.strip()]
        with self._lock, torch.inference_mode():
            inputs = self._tokenizer(sentences, return_tensors="pt", padding=True, truncation=False)
            limit = self._model.config.max_position_embeddings
            if inputs.input_ids.shape[1] > limit:
                raise InferenceInputError("Text exceeds the translation model token limit")
            output = self._model.generate(**inputs, max_length=limit, do_sample=False, num_beams=4)
            if output.shape[1] >= limit:
                raise InferenceInputError("Translation exceeds the output token limit")
            return " ".join(self._tokenizer.batch_decode(output, skip_special_tokens=True))


def prepare_image(image: ImageInput):
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(BytesIO(image.data)) as photo:
            if photo.width * photo.height > 20_000_000:
                raise InferenceInputError("Image exceeds the pixel limit")
            return photo.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise InferenceInputError("Cannot decode image") from error


class LocalLayaClassifier(LayaClassifier):
    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        try:
            return super().classify(request)
        except (InvalidInferenceResultError, InferenceInputError):
            raise
        except ValueError as error:
            raise InferenceInputError("Input exceeds model limits or is unsupported") from error
        except RuntimeError as error:
            raise InferenceUnavailableError("Model inference failed") from error


@lru_cache(maxsize=1)
def local_translator(model_path: str, source_language: str, target_language: str) -> LocalTranslator:
    try:
        return LocalTranslator(model_path, source_language, target_language)
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        raise InferenceUnavailableError("Cannot load translation model") from error


@lru_cache(maxsize=1)
def local_classifier(
    model_path: str, device: str, load_options: str, permutations: int, calibration_strength: float
) -> LocalLayaClassifier:
    try:
        import laya

        checkpoint = Path(model_path)
        for filename in ("vlm_agent_config.json", "model.safetensors", "backbone/config.json", "processor"):
            if not (checkpoint / filename).exists():
                raise ValueError("Laya requires a complete local checkpoint")
        options = json.loads(load_options)
        agent = laya.load_vlm(model_path, device=device, **options)
        return LocalLayaClassifier(
            ContextCalibratedAgent(agent, calibration_strength),
            prepare_image=prepare_image,
            predict_options={"strict": True, "n_permutations": permutations},
            use_descriptions_as_labels=True,
        )
    except (ImportError, OSError, ValueError, TypeError, RuntimeError) as error:
        raise InferenceUnavailableError("Cannot load Laya model") from error


@dataclass(frozen=True)
class ConfiguredTranslator:
    model_path: str
    source_language: str
    target_language: str

    def translate(self, request: TranslationRequest) -> str:
        with _loading_lock:
            provider = local_translator(self.model_path, self.source_language, self.target_language)
        return provider.translate(request)


@dataclass(frozen=True)
class ConfiguredClassifier:
    model_path: str
    device: str
    load_options: str
    permutations: int
    calibration_strength: float

    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        with _loading_lock:
            provider = local_classifier(
                self.model_path, self.device, self.load_options, self.permutations, self.calibration_strength
            )
        return provider.classify(request)


def configured_translator():
    from app.inference.translation import EmptyTranslator

    path = os.getenv("TRANSLATION_MODEL_PATH")
    if not path:
        return EmptyTranslator()
    return ConfiguredTranslator(
        str(resolve_model_path(path)),
        os.getenv("TRANSLATION_SOURCE_LANGUAGE", "pl"),
        os.getenv("TRANSLATION_TARGET_LANGUAGE", "en"),
    )


def configured_classifier():
    from app.inference.service import EmptyClassifier

    path = os.getenv("LAYA_MODEL_PATH")
    if not path:
        return EmptyClassifier()
    try:
        permutations = int(os.getenv("LAYA_PERMUTATIONS", "3"))
        if permutations < 1:
            raise ValueError("Permutation count must be positive")
        strength = float(os.getenv("LAYA_CALIBRATION_STRENGTH", "1"))
        if not math.isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError("Calibration strength must be between 0 and 1")
    except ValueError as error:
        raise InferenceUnavailableError("Invalid Laya configuration") from error
    return ConfiguredClassifier(
        str(resolve_model_path(path)),
        os.getenv("LAYA_DEVICE", "cpu"),
        os.getenv("LAYA_LOAD_OPTIONS", '{"head_max_len": 768, "max_len": 2048}'),
        permutations,
        strength,
    )
