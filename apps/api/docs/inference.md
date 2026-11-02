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

## Wdrożenie na VPS

Workflow `[1] Deploy` buduje obraz API z zestawem `inference` i bibliotekami
PyTorch dla CPU. Pobiera przypięte checkpointy do `/app/models` w osobnej
warstwie obrazu, zachowywanej w cache przy zmianach kodu aplikacji.
Gotowy obraz trafia do GHCR, a VPS pobiera go podczas zwykłego wdrożenia.
Modele nie wymagają ręcznego pobierania, wolumenu ani dodatkowych sekretów.
Tag obrazu wskazuje jednocześnie wersję aplikacji i modeli.

Budowanie obrazu sprawdza kompletność przypiętych checkpointów i wykonuje próbną
klasyfikację polskiego tekstu bez obrazu oraz z wygenerowanym obrazem PNG.
Test działa jako nieuprzywilejowany użytkownik kontenera, bez dostępu do sieci.
Sprawdza w ten sposób tłumaczenie, katalog typów, dekodowanie obrazu i klasyfikację.
Nie sprawdza konkretnej etykiety, ponieważ jest to test działania modeli,
a nie pomiar trafności. Błąd przerywa build przed publikacją obrazu.

Compose ustawia `INFERENCE_REQUIRED=true`, `LAYA_DEVICE=cpu` oraz ścieżki
`LAYA_MODEL_PATH=/app/models/laya-vision` i
`TRANSLATION_MODEL_PATH=/app/models/opus-mt-pl-en` na dev i prod.
API ładuje modele i wykonuje próbę klasyfikacji tekstu przed przyjęciem ruchu.
Pozostają one w pamięci pojedynczego procesu Uvicorn.
Lokalne `task api` zachowuje ładowanie przy pierwszym żądaniu, chyba że
ustawisz `INFERENCE_REQUIRED=true`.

`GET /ready` potwierdza zakończenie startu, w tym próbę modeli, gdy są wymagane.
Healthcheck odczytuje ten stan bez powtarzania predykcji.
`GET /health` nadal sprawdza wyłącznie działanie aplikacji.
Workflow czeka do 600 sekund na zdrowy kontener. Nieudany start oznacza
nieudane wdrożenie; workflow nie przywraca automatycznie poprzedniego obrazu.
Push do `main` wdraża dev, a `[2] Release` korzysta z tego samego mechanizmu na prod.

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

Biblioteki modeli są dostępne w opcjonalnej grupie `inference`. Domyślna instalacja
API ich nie wymaga. Dostawcy mogą zgłaszać
`InferenceUnavailableError`, gdy model jest niedostępny (HTTP 503), lub
`InvalidInferenceResultError`, gdy wynik jest niepoprawny (HTTP 502).
`InferenceInputError` oznacza nieobsługiwane wejście lub przekroczenie limitów modelu (HTTP 422).
Odpowiedzi HTTP dla tych błędów nie zawierają szczegółów dostawcy.

Aby wykorzystać ten sam przepływ w innym handlerze, wstrzyknij `Inference` lub
utwórz `InferenceService(translator, classifier)` i wywołaj `analyze(request, image)`.

## Klasyfikacja typu jednostki

`POST /inference/service-entity` korzysta z tych samych wymiennych dostawców.
Przyjmuje formularz z polem `payload`:

```json
{
  "title": "Dziura w jezdni",
  "description": "Przed szkołą jest głęboka dziura w nawierzchni drogi.",
  "source_language": "pl"
}
```

Opcjonalne `image` ma te same reguły co w `/inference`. Oba pola tekstowe są
wymagane: tytuł ma najwyżej 300, a opis 4000 znaków. Język to `pl` (domyślnie)
lub `en`. Tekst polski jest tłumaczony, angielski trafia bezpośrednio do modelu.
Limity tokenów zależą od podłączonych modeli i mogą być niższe od limitu znaków.
Przekroczenie limitu zwraca 422, bez cichego obcinania zgłoszenia.

Odpowiedź zawiera dokładnie jeden `entity_type` z `ServiceEntityType`, `scores`
i `translation`. Nie stosujemy progu odrzucenia ani wartości `unknown`.
Także niejednoznaczny opis otrzymuje najlepszy wybór modelu. Brak skonfigurowanego
dostawcy oznacza 503. Nie zwracamy wtedy zmyślonego typu.

Wspólny enum jest w `app/service_entity_types.py`, używany również przez katalog
`/service-entities`. Angielskie kryteria są w `app/inference/entity_types.json`.
Lokalny adapter pokazuje modelowi krótkie opisy, a odpowiedź mapuje z powrotem
na kody enuma. Klient nie dostarcza własnej listy typów.
Można wskazać inny plik przez `SERVICE_ENTITY_CRITERIA_PATH`; jego klucze muszą
pokrywać dokładnie enum. Dodanie nowego typu wymaga uzupełnienia kryteriów.
Nie ma list słów kluczowych ani ręcznych reguł wybierających wynik.

Wynik można przekazać do `GET /service-entities?entity_type=...`. Wybór konkretnego
rekordu oraz sprawdzenie jego kompetencji i obszaru działania to osobny krok.
Endpoint nie zmienia reportów ani masterów.

## Rekomendacja instytucji dla nowego zgłoszenia

`POST /inference/service-entity/recommendation` wymaga zalogowania. Przyjmuje
formularz `multipart/form-data` z polem `payload` i opcjonalnym zdjęciem `image`.
Przykładowy payload:

```json
{
  "title": "Dziura w jezdni",
  "description": "Przed szkołą jest głęboka dziura w nawierzchni drogi.",
  "source_language": "pl",
  "location": {"longitude": 19.938, "latitude": 50.061}
}
```

Endpoint działa przed zapisaniem nowego zgłoszenia. Lokalizacja musi należeć
do Małopolski, tak jak przy `POST /reports`. GUGiK ULDK wyznacza gminę i powiat
zgłoszenia, a Laya wybiera jeden typ jednostki. Następnie backend rozpatruje
wyłącznie jednostki tego typu i wybiera siedzibę w kolejności:

1. Ta sama gmina (`municipality`).
2. Ten sam powiat (`county`), jeśli nie ma dopasowania w gminie.
3. To samo województwo (`province`), jeśli nie ma dopasowania w powiecie.
4. Najbliższa siedziba poza województwem (`nearest`), jeśli nie ma dopasowania
   na wcześniejszych poziomach.

W obrębie pierwszego dostępnego poziomu wygrywa najbliższa siedziba. Równe
odległości rozstrzyga mniejsze `id`. Odległość w metrach wylicza PostGIS
po powierzchni Ziemi, bez wyznaczania trasy drogowej. Dopasowanie dotyczy
siedziby, nie potwierdza kompetencji ani rzeczywistego obszaru odpowiedzialności.

Współrzędne i kod gminy siedziby są zapisane w `service_entities` w polach
`seat_location` i `seat_teryt`. Rekomendacja czyta te dane z bazy. Nie geokoduje
instytucji przy obsłudze zgłoszenia. `seat_geocoded_at` przechowuje datę ustalenia
lokalizacji, a `seat_address` adres użyty do geokodowania. Po zmianie adresu
jednostka jest pomijana do czasu ponownego uzupełnienia lokalizacji.
Historyczne `teryt_code` z katalogu nie wpływa na wybór. Nieaktywne jednostki
(`is_active=false`) pozostają w katalogu, ale nie są kandydatami do rekomendacji.

Zwykły import zapisuje przejrzane lokalizacje ze zbioru
`db/seeds/service_entity_seats.json`. Źródła, wyjątki i odświeżanie zbioru opisuje
[TESTING.md](../../../TESTING.md#reference-data-import-and-refresh).
Po zmianie adresu lub przy ręcznym uzupełnianiu siedzib możesz użyć:

```sh
cd apps/api
uv run python -m app.geocode_service_entities
```

Polecenie używa tych samych zmiennych `POSTGRES_*` co API. Aby wczytać lokalne
ustawienia z istniejącego pliku `.env`, użyj
`uv run --env-file ../../.env python -m app.geocode_service_entities`.
Zwykłe uruchomienie pomija zapisane siedziby o niezmienionym adresie;
`--refresh` wymusza ponowne geokodowanie. Zapisane dane nie wygasają.
Ponowny import niezmienionego katalogu zachowuje współrzędne.

Polecenie pobiera punkty adresowe z
[GUGiK UUG](https://services.gugik.gov.pl/uug/opis.html), z operacji `GetAddress`.
Wymagane są miejscowość i numer budynku; ulica jest opcjonalna dla miejscowości
bez ulic. Akceptujemy pojedynczy dokładny wynik o zgodnej miejscowości, ulicy i numerze oraz
ocenie dopasowania co najmniej `0.8`. Wyniki alternatywne o niższej ocenie nie blokują
dokładnego punktu. Kod pocztowy rozróżnia miejscowości o tej samej nazwie; dwa punkty
tego samego adresu pozostają niejednoznaczne. Nie zastępujemy adresu środkiem ulicy lub miejscowości.
PostGIS przelicza EPSG:2180 na WGS 84, a ULDK wyznacza region siedziby.
Do UUG trafiają wyłącznie adresy instytucji, do ULDK współrzędne.

Niepełne lub niejednoznaczne adresy są pomijane. Awaria usługi nie usuwa
wcześniej zapisanych danych; polecenie podaje identyfikator jednostki, kontynuuje
pozostałe i kończy się kodem 1, jeśli wystąpiły błędy. Można je bezpiecznie
powtórzyć. Brak dopasowania podczas odświeżania usuwa starą lokalizację.
Każde żądanie do GUGiK ma timeout 5 sekund.

Odpowiedź zawiera `entity_type`, `scores`, `translation` oraz:

- `region`: `municipality_teryt`, `municipality_name`, `county_teryt`,
  `county_name` i `province_teryt` nowego zgłoszenia.
- `recommendation`: pełny rekord `entity`, `match_level`, `distance_m`,
  `seat_location` i aktualne `seat_municipality_teryt`; `null`, gdy nie ma
  jednostki tego typu z jednoznacznie ustaloną siedzibą.
- `candidates_count`: liczba jednostek typu wybranego przez Layę.
- `skipped_candidates_count`: liczba jednostek pominiętych z powodu
  brakującej zapisanej lokalizacji albo zmiany adresu od czasu geokodowania.

Brak danych nie powoduje przejścia do innego typu jednostki. Awaria ULDK
podczas ustalania regionu nowego zgłoszenia zwraca 503. Błędy klasyfikacji i zdjęć mają
takie same kody jak `/inference/service-entity`. Endpoint nie zapisuje
zgłoszenia, przypisania ani zmian do starych rekordów.

## Dopasowanie do mastera

`POST /reports` pyta model tylko wtedy, gdy w promieniu dopasowania są otwarte
mastery tej samej kategorii, ale żaden tytuł nie przekroczył progu podobieństwa.
Tłumacz przekłada tytuł reportu i tytuły 5 najbliższych masterów. Laya dostaje
pytanie o master opisujący ten sam problem, z opcjami będącymi identyfikatorami
masterów i opcją `unmatched`.

Wybrany master musi mieć co najmniej 1,2 raza wyższą ocenę niż `unmatched`
(`MIN_SCORE_RATIO` w `app/inference/masters.py`). Bez tego progu model łączył
prawie połowę par różnych problemów. Wyłączony dostawca, błąd modelu albo brak
ocen oznaczają dopasowanie wyłącznie po tytułach. Report zostaje zapisany,
a API loguje ostrzeżenie. Pierwsze zapytanie ładuje modele, kolejne trwają
w lokalnym pomiarze na CPU zwykle poniżej sekundy.

## Ustawienia modeli

Laya działa domyślnie na CPU, z trzema permutacjami kolejności opcji.
`LAYA_LOAD_OPTIONS` przekazuje opcje ładowania; domyślne `head_max_len=768` i
`max_len=2048` zapewniają miejsce na katalog. Predykcja używa `strict=True`.
Dla tekstów `LAYA_CALIBRATION_STRENGTH=1` koryguje preferencje modelu na podstawie
predykcji dla pustego opisu i tych samych opcji: dzieli oceny przez bazową ocenę
opcji i normalizuje wynik. `0` wyłącza korektę; wartości pośrednie ją osłabiają.
Wzorzec jest liczony raz dla danego pytania i przechowywany w ograniczonym cache.
Zdjęcia zachowują oryginalne oceny modelu, ponieważ wzorzec tekstowy nie opisuje
zachowania modelu z obrazem. `scores` są ocenami względnymi, nie potwierdzonym
prawdopodobieństwem poprawnej klasyfikacji.
Lokalny tłumacz obsługuje jedną skonfigurowaną parę języków (domyślnie `pl` -> `en`),
używa deterministycznego dekodowania i odrzuca zbyt długie zdania. Zdjęcia są
rzeczywiście dekodowane i konwertowane do RGB, z limitem 20 milionów pikseli.
Zewnętrzny dostawca może zastąpić każdą z tych implementacji przez zależności FastAPI.

## Testy i pomiar trafności

Testy API i kontraktów nie wymagają modeli:

```sh
cd apps/api
uv run pytest
```

Zbiór `tests/fixtures/entity_classification.json` zawiera przykłady wszystkich
15 typów: 15 roboczych (`development`), 37 odłożonych (`holdout`, w tym dwa zdjęcia)
i trzy niejednoznaczne (`contract`). Obejmuje polski, angielski, literówki,
negacje i podobne obszary kompetencji. Dane są syntetyczne; nie pochodzą od użytkowników.
Przypadki `contract` sprawdzają wymuszony wybór, ale nie mają jednej etykiety
uznanej za poprawną i nie zwiększają wyniku trafności.

Pomiar na rzeczywistych modelach (po ustawieniu ścieżek):

```sh
cd apps/api
uv run --extra inference --env-file ../../.env python -m app.inference.evaluate \
  --split all --output /tmp/entity-evaluation.json --min-accuracy 0.8
```

Skrypt zapisuje przewidywania, oczekiwane typy, tłumaczenia i czas predykcji.
Kończy się kodem 1, jeśli trafność spadnie poniżej podanego progu.
Wynik na syntetycznych przykładach nie zastępuje oceny na rzeczywistych zgłoszeniach.

Ostatni pomiar i nierozwiązane pomyłki opisuje [raport ewaluacji](inference-evaluation.md).

Zbiór `tests/fixtures/master_matching.json` zawiera 168 par tytułu reportu
i masterów z okolicy: 112 tego samego problemu (połowa z dodatkowym masterem
o innym problemie) i 56 różnych problemów. Pary pochodzą z danych mockowych
bez nazw ulic, a trzy przeformułowane tytuły z dev. Pomiar dopasowania:

```sh
cd apps/api
uv run --extra inference --env-file ../../.env python -m app.inference.evaluate_masters \
  --output /tmp/master-evaluation.json --min-recall 0.7 --max-false-merges 0.15
```

Skrypt dopasowuje jak publikacja: najpierw po tytułach, potem modelem. Kończy się
kodem 1, gdy odsetek złączonych par tego samego problemu spadnie poniżej
`--min-recall` albo odsetek złączonych różnych problemów przekroczy
`--max-false-merges`. Ostatni pomiar na lokalnych modelach:

| Wariant | Złączone tego samego problemu | Złączone różne problemy |
| --- | --- | --- |
| Same tytuły | 25 / 112 | 0 / 56 |
| Tytuły i model, próg 1,2 | 85 / 112 | 7 / 56 |

Pytanie i próg dobrano na tym samym zbiorze, więc wynik jest optymistyczny.
Błędne łączenia może poprawić office przez `POST /reports/{id}/move`.
