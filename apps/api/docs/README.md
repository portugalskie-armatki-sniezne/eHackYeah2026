# Dokumentacja backendu (apps/api)

Wstępny design API CRUD dla tabel z `db/migrations/`. Dokumentacja jest po polsku, nazwy techniczne (tabele, kolumny, pola JSON, ścieżki) po angielsku.

## Spis dokumentów

| Plik | Zawartość |
| --- | --- |
| [data-model.md](data-model.md) | ERD (Mermaid), tabele kolumn, relacje i reguły usuwania |
| [api.md](api.md) | konwencje, endpointy CRUD, przykłady JSON, kody błędów |

## Zasady dla agentów i ludzi

- Źródłem prawdy o schemacie są migracje w `db/migrations/`. Ten katalog tylko je opisuje. Gdy się rozjadą, wygrywają migracje.
- Po uruchomieniu API kontraktem jest `/openapi.json`. Tabele w `api.md` to plan i mają być z nim zgodne.
- Nazwy encji i pól są takie same w bazie, JSON i dokumentacji (snake_case).
- Kolumny `id`, `created_at`, `edited_at` są nadawane przez bazę. API ich nie przyjmuje.
- Backend nie zmienia migracji ani `db/seeds/`. Potrzebną zmianę schematu zapisujemy w sekcji "Otwarte pytania" w `api.md`.

## Statusy elementów

| Status | Znaczenie |
| --- | --- |
| `planned` | opisane, brak kodu |
| `mock` | działa na danych testowych |
| `done` | działa na bazie, są testy |

## Testy

Testy w `apps/api/tests/` działają na bazie z `.env` i wycofują zmiany po każdym teście. Bez dostępnej bazy są pomijane.

```sh
task db
cd apps/api
uv run --env-file ../../.env pytest
```

## Role

Nowe konto ma rolę `user`. Rolę istniejącego konta, na przykład pierwszego administratora, nadaje skrypt:

```sh
cd apps/api
uv run --env-file ../../.env python -m app.set_role anna@example.com admin
```

Dostępne role to `user`, `office` i `admin`. Później role może zmieniać `admin` przez `PATCH /users/{id}`.

## Zakres

Model danych obejmuje tabele z migracji: `users`, `report_categories`, `master_report_statuses`, `master_reports`, `reports`, `report_photos`, `master_report_comments`, `master_report_comment_likes`, `institution_contacts`. Master przechowuje wspólny stan i dyskusję, a pojedynczy report może czekać na klasyfikację bez mastera.

Plan API opisuje podstawowy CRUD. Endpointy słowników, komentarzy i polubień wymagają osobnego projektu. Inicjatywy nie mają jeszcze tabel i pozostają poza zakresem.
