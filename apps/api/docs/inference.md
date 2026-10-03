# Tłumaczenie i klasyfikacja

`app.inference` zawiera wspólny przepływ analizy, puste implementacje dostawców,
adapter funkcji tłumaczącej i adapter Laya. Dostawcy przyjmują typowane requesty.
Można ich używać bezpośrednio w Pythonie lub przez zależności FastAPI.

Ścieżki `LAYA_MODEL_PATH` i `TRANSLATION_MODEL_PATH` włączają lokalnych dostawców.
Bez tych wartości aplikacja korzysta z `EmptyTranslator` i `EmptyClassifier`,
które zwracają `disabled` bez ładowania modeli. Urządzenie, języki i opcje
predykcji pochodzą z konfiguracji dostawcy.

## Lokalne modele

1. Uruchom `task setup` z katalogu głównego repozytorium. Instaluje biblioteki
   modeli i pobiera poniższe checkpointy do `apps/api/models`. Pierwsze
   uruchomienie wymaga Gita i internetu. Wagi zajmują około 1,1 GB i są ignorowane
   przez Git. Kod pobierania, wersje oraz integracja znajdują się w repozytorium.
2. Nowy `.env` otrzymuje ścieżki z `.env.example`. Jeżeli masz już `.env`, ustaw
   `LAYA_MODEL_PATH=models/laya-vision` i
   `TRANSLATION_MODEL_PATH=models/opus-mt-pl-en`. Usuń stare ścieżki do innych
   checkoutów. Ścieżki względne są liczone od `apps/api`, niezależnie od katalogu
   uruchomienia. Możesz też podać własne ścieżki bezwzględne.
3. Uruchom `task api`. Modele są ładowane przy pierwszej analizie i używane
   ponownie w kolejnych wywołaniach. Pobieranie odbywa się podczas konfiguracji,
   a nie w obsłudze żądania. Puste ścieżki wyłączają odpowiednich dostawców.

| Model | Przypięta rewizja | Licencja |
| --- | --- | --- |
| [thaitea/laya-vision](https://huggingface.co/thaitea/laya-vision) | `f2fe3c12cb6d04c59d8a190250bf3fb40fc828dc` | CC BY-NC-SA 4.0 |
| [Helsinki-NLP/opus-mt-pl-en](https://huggingface.co/Helsinki-NLP/opus-mt-pl-en) | `7f2bb874fdfb6139f9842b91a9b75c4a6c93401c` | Apache 2.0 |

Ponowne `task setup` pomija kompletne checkpointy o zgodnej rewizji. Niepełne
pobranie można wznowić tym samym poleceniem. `.env` jest zachowywany.
`LAYA_DEVICE`, `LAYA_PERMUTATIONS` i `LAYA_LOAD_OPTIONS` sterują wykonaniem
predykcji. Języki tłumacza ustalają `TRANSLATION_SOURCE_LANGUAGE` oraz
`TRANSLATION_TARGET_LANGUAGE`; pobierany checkpoint obsługuje parę `pl` i `en`.

Podstawowy obraz Docker API nadal instaluje tylko zależności podstawowe.
Uruchomienie modeli w kontenerze wymaga obrazu z zestawem `inference`,
udostępnienia checkpointów w kontenerze oraz przekazania powyższych zmiennych.

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

## Klasyfikacja jednostki usługowej

Zalogowany użytkownik może wywołać `POST /inference/service-entity` z polem
formularza `payload` i opcjonalnym plikiem `image`:

```json
{
  "title": "Dziura w jezdni",
  "description": "Proszę o naprawę nawierzchni.",
  "source_language": "pl"
}
```

Odpowiedź zawiera pojedynczy `entity_type`, wyniki `scores` i tłumaczenie.
Pytanie i katalog typów są zapisane w `app/inference/entity_types.json`.
Opcjonalny `SERVICE_ENTITY_CRITERIA_PATH` wskazuje własny plik z pytaniem;
musi on zawierać dokładnie te same typy. Brak aktywnego dostawcy daje HTTP 503,
niepoprawny wynik HTTP 502, a nieobsługiwane dane wejściowe HTTP 422.
Endpoint nie tworzy zgłoszenia i nie przypisuje konkretnej instytucji.

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

Zależności lokalnych modeli należą do opcjonalnego zestawu `inference`, który
instaluje `task setup`. Dostawcy mogą zgłaszać
`InferenceUnavailableError`, gdy model jest niedostępny (HTTP 503), lub
`InvalidInferenceResultError`, gdy wynik jest niepoprawny (HTTP 502).
Odpowiedzi HTTP dla tych błędów nie zawierają szczegółów dostawcy.

Aby wykorzystać ten sam przepływ w innym handlerze, wstrzyknij `Inference` lub
utwórz `InferenceService(translator, classifier)` i wywołaj `analyze(request, image)`.
