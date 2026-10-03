# Dokumentacja backendu (apps/api)

API w FastAPI do zgłaszania problemów, łączenia podobnych zgłoszeń w mastery i dyskusji pod nimi. Działa na tabelach z `db/migrations/`. Dokumentacja jest po polsku, nazwy techniczne (tabele, kolumny, pola JSON, ścieżki) po angielsku.

## Spis dokumentów

| Plik | Zawartość |
| --- | --- |
| [data-model.md](data-model.md) | ERD (Mermaid), tabele kolumn, relacje i reguły usuwania |
| [api.md](api.md) | konwencje, dostęp, endpointy, dopasowanie do mastera, przykłady JSON, kody błędów |
| [inference.md](inference.md) | tłumaczenie, klasyfikacja typów jednostek, opcjonalne zdjęcia i pomiar trafności |

## Zasady dla agentów i ludzi

- Źródłem prawdy o schemacie są migracje w `db/migrations/`. Ten katalog tylko je opisuje. Gdy się rozjadą, wygrywają migracje.
- Po uruchomieniu API kontraktem jest `/openapi.json`. `api.md` opisuje zaimplementowane endpointy i przy każdej zmianie API ma być z nim zgodne.
- Nazwy encji i pól są takie same w bazie, JSON i dokumentacji (snake_case).
- Kolumny `id`, `created_at`, `edited_at` są nadawane przez bazę. API ich nie przyjmuje.
- Backend nie zmienia migracji ani `db/seeds/`. Potrzebną zmianę schematu zapisujemy w sekcji "Otwarte pytania" w `api.md`.

## Statusy elementów

| Status | Znaczenie |
| --- | --- |
| `planned` | opisane, brak kodu |
| `mock` | działa na danych testowych |
| `done` | działa na bazie, są testy |

Endpointy CRUD z [api.md](api.md) mają status `done`. `/inference` udostępnia analizę z wymiennymi dostawcami. `/inference/service-entity` wybiera jeden typ jednostki po skonfigurowaniu modeli. Dopasowanie reportów do masterów też działa na bazie i ma testy, ale jest tymczasową heurystyką, którą zastąpi klasyfikator LLM.

## Uruchomienie

Z katalogu głównego repozytorium:

```sh
task api
```

Polecenie uruchamia bazę, migracje i import seeda, a potem API pod <http://127.0.0.1:8000>. Interaktywna dokumentacja jest pod `/docs`. API wymaga `JWT_SECRET` w `.env`, a ustawienia bazy czyta z tych samych zmiennych co Docker Compose. Logowanie przez Google działa po ustawieniu opcjonalnego `GOOGLE_CLIENT_ID`.

## Struktura kodu

| Plik w `app/` | Zawartość |
| --- | --- |
| `main.py` | aplikacja FastAPI, routery i otwarcie puli połączeń |
| `db.py` | pula połączeń z PostgreSQL |
| `security.py` | hashowanie haseł, tokeny JWT i weryfikacja tokenów Google |
| `auth.py` | `/auth` i zależności dostępu: `CurrentUser`, `OptionalUser`, `StaffUser` (`office`, `admin`), `AdminUser` |
| `models.py` | model użytkownika i role |
| `common.py` | wspólne typy i SQL: lokalizacja, paginacja, filtr po okolicy, częściowy `UPDATE` |
| `users.py` | `/users` |
| `reports.py` | `/reports`, zdjęcia reportów i przepinanie do innego mastera |
| `matching.py` | dopasowanie nowego reportu do mastera |
| `storage.py` | walidacja i zapis plików zdjęć |
| `photos.py` | model zdjęcia i publiczne `/photos/{id}/file` |
| `master_reports.py` | `/master-reports` |
| `comments.py` | komentarze i polubienia masterów |
| `reference.py` | `/report-categories` i `/master-report-statuses` |
| `institution_contacts.py` | `/institution-contacts` |
| `inference/` | `/inference`, wymienny tłumacz, klasyfikator i adapter Laya |
| `set_role.py` | skrypt nadający rolę użytkownikowi |

## Testy

Testy w `apps/api/tests/` automatycznie wczytują główny `.env` przed importem aplikacji. Zmienne ustawione w środowisku mają pierwszeństwo. Testy działają na wskazanej bazie i wycofują zmiany po każdym teście. Zdjęcia zapisują w katalogu tymczasowym. Bez dostępnej bazy są pomijane.

```sh
task db
cd apps/api
uv run pytest
```

## Role

Nowe konto ma rolę `user`. Rolę istniejącego konta, na przykład pierwszego administratora, nadaje skrypt:

```sh
cd apps/api
uv run --env-file ../../.env python -m app.set_role anna@example.com admin
```

Dostępne role to `user`, `office` i `admin`. Później role może zmieniać `admin` przez `PATCH /users/{id}`. `office` zarządza masterami: zmienia status, odpowiedź i odpowiedzialny podmiot oraz przepina reporty. `admin` może dodatkowo edytować i usuwać dowolne reporty i mastery. Pełna tabela jest w [api.md](api.md#dostęp).

## Reporty i mastery

Report to pojedyncze zgłoszenie użytkownika. Master to wspólna sprawa dla podobnych reportów: ma status, odpowiedź, odpowiedzialny podmiot (urząd albo jednostkę usługową), komentarze i polubienia.

`POST /reports` od razu przypina nowy report do mastera. Kandydaci to mastery z tą samą kategorią, ze statusem innym niż `finished`, do 50 m od punktu mastera. Spośród nich wygrywa ten o najbardziej podobnym tytule. Jeśli żaden nie przekroczy progu podobieństwa, report tworzy nowy master. Gdy master straci ostatni report, API usuwa go razem z dyskusją. Szczegóły są w [api.md](api.md#dopasowanie-do-mastera), a promień i próg w `app/matching.py`.

## Zdjęcia

Pliki zdjęć trafiają do katalogu z opcjonalnej zmiennej `UPLOAD_DIR`. Domyślnie jest to `apps/api/uploads`, ignorowany przez Git. Ścieżka względna zaczyna się w `apps/api`. Report ma najwyżej 5 zdjęć JPEG, PNG lub WebP do 10 MB.

Przy starcie API tworzy ten katalog i sprawdza, czy da się w nim zapisywać. Jeśli nie, kończy start błędem `UPLOAD_DIR ... is not writable`, zamiast zwracać 500 przy pierwszym zdjęciu.

W kontenerze `docker-compose.app.yaml` ustawia `UPLOAD_DIR=/app/uploads` na nazwanym wolumenie `api_uploads`, więc zdjęcia przetrwają kolejne wdrożenia. Obraz tworzy ten katalog dla nieuprzywilejowanego użytkownika (65534), a nazwany wolumen przy pierwszym montowaniu przejmuje jego właściciela. Wolumen albo bind mount pod inną ścieżką musi być zapisywalny dla tego użytkownika.

## Zakres

Model danych obejmuje tabele z migracji: `users`, `report_categories`, `master_report_statuses`, `master_reports`, `reports`, `report_photos`, `master_report_comments`, `master_report_comment_likes`, `local_government_offices`, `service_entities`.

API obejmuje CRUD tych tabel, słowniki, komentarze i polubienia. Urzędy (`/institution-contacts`) i słowniki są tylko do odczytu, a `service_entities` nie ma jeszcze endpointów. Inicjatywy nie mają jeszcze tabel i pozostają poza zakresem.
