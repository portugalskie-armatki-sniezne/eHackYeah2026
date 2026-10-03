from collections.abc import Callable

from app.inference.contracts import TranslationRequest


class EmptyTranslator:
    def translate(self, request: TranslationRequest) -> None:
        return None


class CallableTranslator:
    def __init__(self, translate: Callable[[TranslationRequest], str]) -> None:
        self._translate = translate

    def translate(self, request: TranslationRequest) -> str:
        return self._translate(request)
