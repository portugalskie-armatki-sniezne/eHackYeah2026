import json
import os
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

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
def local_classifier(model_path: str, device: str, load_options: str, permutations: int) -> LocalLayaClassifier:
    try:
        import laya

        if not Path(model_path).is_dir():
            raise ValueError("Laya requires a local checkpoint directory")
        options = json.loads(load_options)
        agent = laya.load_vlm(model_path, device=device, **options)
        return LocalLayaClassifier(
            agent, prepare_image=prepare_image, predict_options={"strict": True, "n_permutations": permutations}
        )
    except (ImportError, OSError, ValueError, TypeError, RuntimeError) as error:
        raise InferenceUnavailableError("Cannot load Laya model") from error


def configured_translator():
    from app.inference.translation import EmptyTranslator

    path = os.getenv("TRANSLATION_MODEL_PATH")
    if not path:
        return EmptyTranslator()
    with _loading_lock:
        return local_translator(
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
    except ValueError as error:
        raise InferenceUnavailableError("Invalid Laya configuration") from error
    with _loading_lock:
        return local_classifier(
            str(resolve_model_path(path)),
            os.getenv("LAYA_DEVICE", "cpu"),
            os.getenv("LAYA_LOAD_OPTIONS", '{"head_max_len": 768, "max_len": 2048}'),
            permutations,
        )
