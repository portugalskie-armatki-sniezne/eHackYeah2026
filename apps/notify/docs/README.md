# Dokumentacja powiadomień (apps/notify)

Osobny mikroserwis FastAPI do wysyłania maili przez Gmail SMTP. Renderuje szablony Markdown do HTML i dołącza wersję tekstową. Backend wywołuje go po HTTP w sieci Docker Compose. Serwis nie korzysta z bazy danych.

## Spis dokumentów

| Plik | Zawartość |
| --- | --- |
| [api.md](api.md) | endpointy, format wiadomości, tryb mock i kody błędów |
| [deployment.md](deployment.md) | konfiguracja Gmaila, zmienne środowiskowe i wdrożenie |

## Zasady dla agentów i ludzi

- Źródłem prawdy o zachowaniu jest `app/main.py`, a kontraktem HTTP `/openapi.json`.
- Dokumentacja opisuje zaimplementowane endpointy. Zmiany API i konfiguracji wymagają aktualizacji odpowiedniego dokumentu.

## Struktura kodu

| Plik | Zawartość |
| --- | --- |
| `app/main.py` | aplikacja FastAPI, walidacja, wybór szablonu i wysyłka SMTP |
| `templates/*.md` | szablony dla `issue` i `improvement` z opisem, zgłaszającym i lokalizacją |
| `app/storage.py` | odczyt i walidacja zdjęć z katalogu API |
| `tests/test_send.py` | testy renderowania, wysyłki, lokalizacji, zdjęć, anonimowości i błędów |
| `Dockerfile` | obraz uruchamiający serwis jako nieuprzywilejowany użytkownik |
| `pyproject.toml`, `uv.lock` | zależności i konfiguracja narzędzi |

## Testy

Testy zastępują połączenie SMTP i nie wysyłają prawdziwych maili. Nie wymagają danych Gmaila.

```sh
cd apps/notify
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
