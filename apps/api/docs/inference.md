# Tłumaczenie i klasyfikacja

`app.inference` zawiera wspólny przepływ analizy, puste implementacje dostawców,
adapter funkcji tłumaczącej i adapter Laya. Dostawcy przyjmują typowane requesty.
Można ich używać bezpośrednio w Pythonie lub przez zależności FastAPI.

Aplikacja korzysta domyślnie z `EmptyTranslator` i `EmptyClassifier`. Zwracają one
`disabled` bez ładowania i pobierania modeli. Identyfikatory modeli, ścieżki,
urządzenia, języki, pytania i katalogi instytucji pochodzą od wywołującego lub
z konfiguracji dostawcy.

## Request API

Zalogowany użytkownik może wywołać `POST /inference` z polami formularza:

- `payload`: tekst JSON zawierający `text`, `source_language`, `target_language`
  i `questions`.
- `image`: opcjonalny plik JPEG, PNG lub WebP. Endpoint korzysta z limitu rozmiaru
  zdjęć reportów i wykrywa typ pliku na podstawie jego nagłówka.

Przykładowy payload:

```json
{
  "text": "Opis do analizy.",
  "source_language": "pl",
  "target_language": "en",
  "questions": {
    "destination": {
      "instructions": "Choose the best destination for this description.",
      "criteria": {
        "candidate-id": "English description of the candidate's responsibilities",
        "unmatched": "None of the candidates is suitable"
      }
    }
  }
}
```

Nazwy pytań, instrukcje i identyfikatory kandydatów są dowolne. Powyższe opcje
są przykładowe. Usługa sprawdza, czy klasyfikator odpowiedział na przekazane
pytania i wybrał tylko przekazane opcje. Wyniki `scores` pochodzą od dostawcy
i nie określają zweryfikowanego prawdopodobieństwa poprawności.

Tłumaczenie odbywa się przed klasyfikacją. Zgodne języki źródłowy i docelowy
pozwalają pominąć tłumaczenie. Wyłączony tłumacz zatrzymuje klasyfikację tekstu
wymagającego tłumaczenia. Zdjęcie trafia tylko do klasyfikatora; API go nie
zapisuje ani nie zwraca. Tekst jest wymagany, a zdjęcie opcjonalne. Endpoint
zwraca analizę bez tworzenia reportów i przypisywania instytucji.

## Podłączanie dostawców

Zaimplementuj `Translator.translate(TranslationRequest)` i
`Classifier.classify(ClassificationRequest)` albo użyj gotowych adapterów.
`CallableTranslator` opakowuje funkcję zwracającą przetłumaczony tekst.
`LayaClassifier` przyjmuje załadowany model z metodą `predict`, opcjonalną funkcję
przygotowania obrazu i opcjonalne argumenty predykcji.

Podepnij dostawców w kodzie konfigurującym aplikację:

```python
from app.inference.laya import LayaClassifier
from app.inference.service import get_classifier, get_translator
from app.inference.translation import CallableTranslator
from app.main import app


def connect_inference(agent, translate, prepare_image, predict_options):
    translator = CallableTranslator(translate)
    classifier = LayaClassifier(agent, prepare_image=prepare_image, predict_options=predict_options)
    app.dependency_overrides[get_translator] = lambda: translator
    app.dependency_overrides[get_classifier] = lambda: classifier
```

Funkcja `translate` otrzymuje request z tekstem i identyfikatorami obu języków.
Funkcja `prepare_image` otrzymuje `ImageInput` z polami `data` i `media_type`
i zwraca obiekt wymagany przez załadowany model Laya. Powinna zdekodować
i zweryfikować zdjęcie przy użyciu wybranej biblioteki. Jest wymagana przy
klasyfikacji ze zdjęciem. Wywołania z samym tekstem jej nie potrzebują.
Adapter wykonuje predykcje swojego modelu kolejno. Dostawcy są synchroniczni;
FastAPI uruchamia endpoint w puli wątków.

Biblioteki wybranego dostawcy i ładowanie modelu konfiguruje się osobno.
Podstawa nie dodaje zależności modeli. Dostawcy mogą zgłaszać
`InferenceUnavailableError`, gdy model jest niedostępny (HTTP 503), lub
`InvalidInferenceResultError`, gdy wynik jest niepoprawny (HTTP 502).
Odpowiedzi HTTP dla tych błędów nie zawierają szczegółów dostawcy.

Aby wykorzystać ten sam przepływ w innym handlerze, wstrzyknij `Inference` lub
utwórz `InferenceService(translator, classifier)` i wywołaj `analyze(request, image)`.
