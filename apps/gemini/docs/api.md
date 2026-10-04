# Gemini (apps/gemini)

Mały serwis FastAPI do generowania obrazów przez Google Cloud (Vertex AI, obecnie Gemini Enterprise Agent Platform). Korzysta z oficjalnego SDK `google-genai` i modelu [Nano Banana 2](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/image-generation) (`gemini-3.1-flash-image`). Nie wymaga bazy danych.

## Uruchomienie lokalne

1. Wybierz projekt w [Google Cloud](https://console.cloud.google.com/) i sprawdź, czy jest połączony z właściwym kontem rozliczeniowym. Zapisz jego Project ID.
2. Włącz [API platformy](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com).
3. W [IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) utwórz konto `gemini` i nadaj mu rolę `Vertex AI User` lub `Agent Platform User` (`roles/aiplatform.user`). Otwórz konto i wybierz **Keys > Add key > Create new key > JSON > Create**. [Instrukcja Google](https://docs.cloud.google.com/iam/docs/keys-create-delete#iam-service-account-keys-create-console).
4. Zapisz pobrany plik w głównym katalogu repo jako `gcp_service_account.json`. Jest ignorowany przez Git i Docker. Nie udostępniaj jego zawartości. W głównym `.env` ustaw:

   ```dotenv
   GOOGLE_CLOUD_PROJECT=replace_me_with_project_id
   GOOGLE_CLOUD_LOCATION=global
   GOOGLE_APPLICATION_CREDENTIALS=../../gcp_service_account.json
   ```

   Ścieżka względna zaczyna się w `apps/gemini`. Możesz też użyć ścieżki bezwzględnej. Puste `GOOGLE_APPLICATION_CREDENTIALS` korzysta ze standardowego [ADC](https://docs.cloud.google.com/docs/authentication/application-default-credentials). Serwis nie korzysta z `GEMINI_API_KEY` ani z klienta OAuth `client_secret.json`.
5. Zainstaluj zależności i uruchom serwis:

   ```sh
   cd apps/gemini
   uv sync --locked
   uv run --env-file ../../.env uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload --reload-dir app
   ```

Dokumentacja HTTP jest dostępna pod `http://127.0.0.1:8002/docs`.

## Przykład Python

Zmień `PROMPT` w `example.py`. Z katalogu `apps/gemini` uruchom:

```sh
uv run --env-file ../../.env python example.py
```

Przykład wywołuje konektor bez uruchamiania serwera HTTP, zapisuje obraz w `output/example.png` (lub `.jpg` albo `.webp`, zależnie od odpowiedzi) i wypisuje ścieżkę. Katalog `output/` jest ignorowany przez Git. Ponowne uruchomienie nadpisuje plik danego formatu. Wywołanie korzysta z limitu i rozliczeń projektu Google.

Konektor można też wywołać bezpośrednio z kodu Python:

```python
from app.gemini import generate_image

media_type, data = generate_image("Realistyczne zdjęcie parku miejskiego z ławkami.")
```

## HTTP

`GET /health` zwraca `{"status":"ok"}` i nie wywołuje Google.

`POST /generate` przyjmuje JSON z niepustym `prompt` i zwraca bajty pierwszego wygenerowanego obrazu z nagłówkiem `Content-Type: image/png`, `image/jpeg` lub `image/webp`.

```sh
curl --fail-with-body http://127.0.0.1:8002/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Realistyczne zdjęcie parku miejskiego z ławkami."}' \
  --output /tmp/gemini-image.png
```

Rozszerzenie zapisanego pliku powinno odpowiadać `Content-Type`. Serwis nie zapisuje obrazów ani nie przyjmuje ścieżek plików. Endpoint jest przeznaczony do wywołań wewnętrznych; uruchomienie lokalne wiąże go z `127.0.0.1`.

| Kod | Przyczyna |
| --- | --- |
| `422` | brak, pusty lub nieprawidłowy prompt albo dodatkowe pola |
| `503` | brak Project ID, brak lub nieprawidłowe dane logowania GCP albo przekroczony limit Gemini |
| `502` | błąd połączenia, błąd API lub odpowiedź bez obrazu |

Limit czasu żądania do Google wynosi 120 sekund. Odpowiedzi błędów nie ujawniają klucza ani treści błędów Google.

## Walidacja

Z katalogu `apps/gemini`:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Testy zastępują klienta Google i nie generują płatnych obrazów. `Dockerfile` korzysta z tych samych wersji Pythona i uv co `notify` i uruchamia serwis jako nieuprzywilejowany użytkownik.
