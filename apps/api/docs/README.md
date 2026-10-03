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

## Zakres

Model danych obejmuje tabele z migracji: `users`, `report_categories`, `master_report_statuses`, `master_reports`, `reports`, `report_photos`, `master_report_comments`, `master_report_comment_likes`, `institution_contacts`. Master przechowuje wspólny stan i dyskusję, a pojedynczy report może czekać na klasyfikację bez mastera.

Plan API opisuje podstawowy CRUD. Endpointy słowników, komentarzy i polubień wymagają osobnego projektu. Inicjatywy i role nie mają jeszcze tabel i pozostają poza zakresem.
