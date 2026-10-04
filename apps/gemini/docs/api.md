# Gemini (apps/gemini)

Wewnętrzny serwis FastAPI do wizualizacji inicjatyw `improvement` przez Google Cloud (Vertex AI, obecnie Gemini Enterprise Agent Platform). [Gemini Flash](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash) (`gemini-3.8-flash`) analizuje opis i zdjęcia, a [Nano Banana 2](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/image-generation) (`gemini-3.1-flash-image`) generuje obrazy na podstawie przygotowanych promptów i tych samych zdjęć. Serwis korzysta z `google-genai` i nie wymaga bazy danych. Autoryzacja użytkownika, sprawdzenie typu zgłoszenia w bazie i ograniczanie liczby wywołań należą do backendu.

## Uruchomienie lokalne

1. Wybierz projekt w [Google Cloud](https://console.cloud.google.com/) i sprawdź, czy jest połączony z właściwym kontem rozliczeniowym. Zapisz jego Project ID.
2. Włącz [API platformy](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com).
3. W [IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) utwórz konto `gemini` i nadaj mu rolę `Vertex AI User` lub `Agent Platform User` (`roles/aiplatform.user`). Otwórz konto i wybierz **Keys > Add key > Create new key > JSON > Create**. [Instrukcja Google](https://docs.cloud.google.com/iam/docs/keys-create-delete#iam-service-account-keys-create-console).
4. Zapisz pobrany plik w głównym katalogu repo jako `project-key.json`. Jest ignorowany przez Git i Docker. Nie udostępniaj jego zawartości. W głównym `.env` ustaw:

   ```dotenv
   GOOGLE_CLOUD_PROJECT=replace_me_with_project_id
   GOOGLE_CLOUD_LOCATION=global
   GOOGLE_APPLICATION_CREDENTIALS=../../project-key.json
   ```

   Ścieżka względna zaczyna się w `apps/gemini`. Możesz też użyć ścieżki bezwzględnej. Puste `GOOGLE_APPLICATION_CREDENTIALS` korzysta ze standardowego [ADC](https://docs.cloud.google.com/docs/authentication/application-default-credentials). Serwis nie korzysta z `GEMINI_API_KEY` ani z klienta OAuth `client_secret.json`.
5. Zainstaluj zależności i uruchom serwis:

   ```sh
   cd apps/gemini
   uv sync --locked
   uv run --env-file ../../.env uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload --reload-dir app
   ```

Dokumentacja HTTP jest dostępna pod `http://127.0.0.1:8002/docs`.

`UPLOAD_DIR` wskazuje katalog zdjęć współdzielony z API, tak jak w `notify`. Domyślnie jest to `apps/api/uploads`; ścieżki względne są liczone od `apps/api`. W kontenerze zamontuj wolumen `api_uploads` tylko do odczytu i ustaw `UPLOAD_DIR=/app/uploads`. Dane logowania GCP również montuj tylko do odczytu, wskazując ścieżkę wewnątrz kontenera w `GOOGLE_APPLICATION_CREDENTIALS`.

## Przykład Python

`example.py` korzysta ze zdjęcia polany i opisu placu zabaw w `mock/`. Możesz zmienić `DESCRIPTION`, `PHOTO` i `VARIANTS`. Z katalogu `apps/gemini` uruchom:

```sh
uv run --env-file ../../.env python example.py
```

Przykład uruchamia oba etapy bez serwera HTTP i zapisuje trzy obrazy w `output/variant-1.png`, `output/variant-2.png` i `output/variant-3.png` (lub `.jpg` albo `.webp`, zależnie od odpowiedzi). `output/prompts.json` zawiera użyte prompty i nazwy plików. Katalog `output/` jest ignorowany przez Git. Ponowne uruchomienie nadpisuje pliki danego formatu. Dane wejściowe są przykładowe, ale generacja korzysta z prawdziwego API i rozliczeń projektu Google.

Konektor można też wywołać bezpośrednio z kodu Python:

```python
from app.gemini import generate_visualizations
from app.storage import read_photo

photos = [read_photo("reports/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222.jpg")]
images = generate_visualizations("Plac zabaw ze zjeżdżalnią, huśtawkami i piaskownicą.", photos, variants=3)
# each tuple contains the prompt, media type and image bytes
```

## HTTP

`GET /health` zwraca `{"status":"ok"}` i nie wywołuje Google.

`POST /generate` przyjmuje JSON:

| Pole | Znaczenie |
| --- | --- |
| `report_type` | wymagane `"improvement"`; `"issue"` jest odrzucane |
| `description` | wymagany, niepusty opis inicjatywy |
| `photos` | 1-5 obiektów z `storage_key` zdjęć zapisanych przez API; JPEG, PNG lub WebP, do 10 MB każde i 20 MB łącznie |
| `variants` | liczba propozycji od 1 do 3, domyślnie 3 |

```sh
curl --fail-with-body http://127.0.0.1:8002/generate \
  -H 'Content-Type: application/json' \
  -d '{"report_type":"improvement","description":"Plac zabaw ze zjeżdżalnią, huśtawkami i piaskownicą.","photos":[{"storage_key":"reports/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222.jpg"}],"variants":3}' \
  --output /tmp/gemini-variants.json
```

Zdjęcia muszą istnieć pod podanymi kluczami. Pierwsze wyznacza kadr wizualizacji, pozostałe dają kontekst tego samego miejsca. Wspólne reguły w `app/gemini.py` wymagają naturalnego wyglądu i zachowania otoczenia. Warianty mają różnić się układem, materiałami lub wyposażeniem.

Odpowiedź ma postać `{"variants":[{"prompt":"...","media_type":"image/png","image_base64":"..."}]}`. `image_base64` zawiera zakodowane bajty obrazu, bez prefiksu `data:`. Backend dekoduje i zapisuje je po swojej stronie. Serwis nie zapisuje wyników. Dotychczasowy kontrakt z samym `prompt` i odpowiedzią binarną został zastąpiony.

Wywołanie wykonuje jedno żądanie do Flash i osobne żądanie do Nano Banana dla każdego wariantu. Jeśli którykolwiek etap zawiedzie, endpoint zwraca błąd bez częściowych wyników. Wcześniejsze udane wywołania mogą już być rozliczone; ponowienie uruchamia cały pipeline. Endpoint służy wywołaniom wewnętrznym i nie ma własnego uwierzytelniania ani limitu na użytkownika.

| Kod | Przyczyna |
| --- | --- |
| `422` | nieprawidłowe pola, typ inny niż `improvement`, niedozwolony klucz lub format zdjęcia |
| `404` | zdjęcie nie istnieje |
| `413` | przekroczony rozmiar zdjęć |
| `503` | brak Project ID, nieprawidłowe dane logowania GCP, przekroczony limit Gemini lub brak dostępu do pliku zdjęcia |
| `502` | błąd połączenia, błąd API, nieprawidłowe prompty lub odpowiedź bez obrazu |

Limit czasu każdego żądania do Google wynosi 120 sekund. Cały pipeline może trwać dłużej; backend powinien uwzględnić wszystkie etapy w swoim limicie czasu. Odpowiedzi błędów nie ujawniają klucza ani treści błędów Google.

## Walidacja

Z katalogu `apps/gemini`:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Testy zastępują klienta Google i nie generują płatnych obrazów. `Dockerfile` korzysta z tych samych wersji Pythona i uv co `notify` i uruchamia serwis jako nieuprzywilejowany użytkownik.
