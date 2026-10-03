# API CRUD

Wszystkie endpointy opisane poniżej mają status `done`. Nazwy pól są takie same jak kolumny w [data-model.md](data-model.md).

## Konwencje

- Format: JSON, pola w snake_case. Identyfikatory użytkowników, masterów, reportów, zdjęć i komentarzy jako UUID w postaci tekstu; identyfikatory kategorii, statusów i instytucji jako liczby całkowite.
- Wyjątek: `POST /reports` i `POST /reports/{id}/photos` przyjmują `multipart/form-data`, bo zawierają pliki zdjęć.
- Daty: ISO 8601 z strefą czasową (UTC).
- Pola `id`, `created_at`, `edited_at` są tylko do odczytu. Serwer ignoruje je w requestach albo zwraca 422.
- `PATCH` przyjmuje podzbiór pól (częściowa aktualizacja). `PUT` jest używany tylko do idempotentnego polubienia komentarza.
- Lokalizacja w JSON to obiekt `{"longitude": 19.9449, "latitude": 50.0647}`. Zakres: longitude od -180 do 180, latitude od -90 do 90 (WGS 84).
- `password_hash` nie pojawia się w żadnej odpowiedzi. Request przyjmuje `password`, a serwer zapisuje hash.
- Kolekcje: paginacja `limit` (domyślnie 50, maksymalnie 200) i `offset`. Odpowiedź: `{"items": [...], "total": 123, "limit": 50, "offset": 0}`. Słowniki i zdjęcia zwracają zwykłą listę.
- Filtr po okolicy: `longitude`, `latitude` i `radius_m` (metry, do 100 000) podawane razem, inaczej 422.
- Nieznane pola w body JSON zwracają 422.
- Błędy w formacie FastAPI: `{"detail": "..."}`, a dla 422 lista błędów walidacji.

### Kody błędów

| Kod | Kiedy |
| --- | --- |
| 401 | brak tokenu, token nieważny lub wygasły, użytkownik z tokenu nie istnieje |
| 403 | rola nie pozwala na operację |
| 404 | brak zasobu o podanym id albo brak kategorii, statusu, instytucji lub mastera wskazanego w body |
| 409 | naruszenie unikalności albo klucza obcego przy usuwaniu |
| 413 | zdjęcie większe niż 10 MB |
| 422 | niepoprawne dane (typ, pusty `title` lub `description`, brak kontaktu użytkownika, zły zakres współrzędnych, zły format lub za dużo zdjęć) |

## Przegląd endpointów

| Zasób | Ścieżka bazowa | Operacje |
| --- | --- | --- |
| auth | `/auth` | login, me |
| users | `/users` | create, list, get, update, delete |
| reports | `/reports` | create z dopasowaniem do mastera, list, get, update, delete, move |
| report_photos | `/reports/{report_id}/photos`, `/photos/{id}/file` | create, list, delete, pobranie pliku (bez update) |
| master_reports | `/master-reports` | list, get, update, delete; tworzy je backend |
| master_report_comments | `/master-reports/{id}/comments`, `/comments/{id}` | create, list, delete, like, unlike |
| słowniki | `/report-categories`, `/master-report-statuses` | list (tylko odczyt) |
| local_government_offices | `/institution-contacts` | list, get (tylko odczyt) |

### Dostęp

| Kto | Co może |
| --- | --- |
| publiczny | rejestracja, logowanie, mastery, komentarze, słowniki, instytucje, pliki zdjęć |
| zalogowany | odczyt reportów i metadanych zdjęć, dodawanie reportów, komentarzy i polubień |
| autor reportu | edycja i usuwanie reportu oraz jego zdjęć |
| autor komentarza | usuwanie komentarza |
| `office` | jak zalogowany oraz edycja masterów, przepinanie reportów, usuwanie dowolnych komentarzy |
| `admin` | jak `office` oraz edycja i usuwanie dowolnych reportów, usuwanie masterów |

## auth

Logowanie zwraca token JWT (HS256, ważny 24 godziny, podpisany `JWT_SECRET` z `.env`). Chronione endpointy wymagają nagłówka `Authorization: Bearer <token>`. Token zawiera tylko id użytkownika. Rola jest czytana z bazy przy każdym zapytaniu, więc zmiana roli i usunięcie konta działają od razu. Wylogowanie polega na usunięciu tokenu po stronie klienta.

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | logowanie | publiczny | 200 | 401, 422 |
| GET | `/auth/me` | zalogowany użytkownik | zalogowany | 200 | 401 |

Request `POST /auth/login` to form-data zgodne z OAuth2 (`application/x-www-form-urlencoded`). Pole `username` zawiera email albo telefon:

```text
username=anna@example.com&password=tajne-haslo
```

Odpowiedź:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

`GET /auth/me` zwraca użytkownika w tym samym formacie co `GET /users/{id}`. W `/docs` przycisk Authorize loguje przez `/auth/login`.

## users

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| POST | `/users` | rejestracja | publiczny | 201 | 409 (email lub telefon zajęty), 422 |
| GET | `/users` | lista | `admin` | 200 | 401, 403, 422 |
| GET | `/users/{id}` | pobranie | właściciel konta, `admin` | 200 | 401, 403, 404 |
| PATCH | `/users/{id}` | aktualizacja | właściciel konta, `admin` | 200 | 401, 403, 404, 409 (email lub telefon zajęty), 422 |
| DELETE | `/users/{id}` | usunięcie | właściciel konta, `admin` | 204 | 401, 403, 404, 409 (ma zgłoszenia lub komentarze) |

Role `user` i `office` mają ten sam dostęp: tylko do własnego konta. Dla cudzego lub nieistniejącego id zwracają 403, żeby nie ujawniać, które konta istnieją.

Request `POST /users`:

```json
{
  "first_name": "Anna",
  "last_name": "Nowak",
  "email": "anna@example.com",
  "phone": "+48123456789",
  "password": "tajne-haslo"
}
```

Odpowiedź:

```json
{
  "id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "first_name": "Anna",
  "last_name": "Nowak",
  "email": "anna@example.com",
  "phone": "+48123456789",
  "role": "user",
  "edited_at": "2026-04-16T10:00:00Z",
  "created_at": "2026-04-16T10:00:00Z"
}
```

Pola `PATCH`: `first_name`, `last_name`, `email`, `phone`, `password`, `role` (tylko `admin`).

- `first_name` i `last_name` są przycinane i nie mogą być puste. `password` ma co najmniej 8 znaków i jest hashowane Argon2.
- Nowy użytkownik dostaje rolę `user`, a `role` w `POST` zwraca 422. Rolę w `PATCH` zmienia tylko `admin`, a dla innych ról zwraca 403.
- Pierwszego administratora tworzy skrypt z [README.md](README.md#role).
- Nieznane pola w `POST` i `PATCH` zwracają 422.
- `email` i `phone` są opcjonalne, ale co najmniej jedno musi pozostać ustawione, także po częściowym `PATCH`. Inaczej API zwraca 422. `PATCH` z `null` jest dozwolony tylko dla tych dwóch pól.
- `phone` jest zapisywany bez spacji i myślników, na przykład `+48 123-456-789` jako `+48123456789`. Po tym musi mieć 7-15 cyfr z opcjonalnym `+` na początku. Email i telefon są unikalne.
- `edited_at` ustawia trigger w bazie przy każdej zmianie.


## reports

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| POST | `/reports` | dodanie z dopasowaniem do mastera | zalogowany | 201 | 401, 404 (brak kategorii), 413, 422 |
| GET | `/reports` | lista z filtrami | zalogowany | 200 | 401, 422 |
| GET | `/reports/{id}` | pobranie | zalogowany | 200 | 401, 404 |
| PATCH | `/reports/{id}` | aktualizacja | autor, `admin` | 200 | 401, 403, 404, 422 |
| DELETE | `/reports/{id}` | usunięcie wraz ze zdjęciami | autor, `admin` | 204 | 401, 403, 404 |
| POST | `/reports/{id}/move` | przepięcie do innego mastera | `office`, `admin` | 200 | 401, 403, 404, 422 |

Filtry `GET /reports`: `user_id`, `master_report_id` oraz `longitude`, `latitude`, `radius_m`. Lista jest posortowana od najnowszych.

Request `POST /reports` to `multipart/form-data`. `user_id` pochodzi z tokenu. Pole `photos` można powtórzyć do 5 razy albo pominąć:

```text
report_category_id=2
title=Dziura przy ul. Długiej 5
description=Dziura w jezdni przy ul. Długiej 5.
longitude=19.9449
latitude=50.0647
photos=@dziura.jpg
```

Odpowiedź:

```json
{
  "id": "9a2b8c44-7d5e-4f10-a3b1-6c0d1e2f3a44",
  "user_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "master_report_id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20",
  "report_category_id": 2,
  "title": "Dziura przy ul. Długiej 5",
  "description": "Dziura w jezdni przy ul. Długiej 5.",
  "location": { "longitude": 19.9449, "latitude": 50.0647 },
  "photos": [
    {
      "id": "c3d4e5f6-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
      "report_id": "9a2b8c44-7d5e-4f10-a3b1-6c0d1e2f3a44",
      "storage_key": "reports/9a2b8c44-7d5e-4f10-a3b1-6c0d1e2f3a44/c3d4e5f6-1a2b-4c3d-8e9f-0a1b2c3d4e5f.jpg",
      "url": "/photos/c3d4e5f6-1a2b-4c3d-8e9f-0a1b2c3d4e5f/file",
      "created_at": "2026-04-16T10:00:00Z"
    }
  ],
  "edited_at": "2026-04-16T10:00:00Z",
  "created_at": "2026-04-16T10:00:00Z"
}
```

### Dopasowanie do mastera

`POST /reports` w jednej transakcji zapisuje report i od razu przypina go do mastera. To tymczasowy mock w `app/matching.py`, który później zastąpi klasyfikator LLM:

1. Kandydaci to mastery z tą samą `report_category_id`, ze statusem innym niż `finished`, w promieniu 50 m od punktu mastera.
2. Dla każdego kandydata liczone jest podobieństwo tytułu nowego reportu do tytułu mastera i tytułów jego reportów, a wynikiem jest najlepsze z nich. Tytuły są porównywane bez wielkości liter, polskich znaków i interpunkcji (`difflib`, wynik od 0 do 1).
3. Kandydaci z wynikiem poniżej 0.5 odpadają. Wygrywa najwyższy wynik, a przy remisie bliższy master.
4. Bez pasującego kandydata backend tworzy nowy master ze statusem `created`, kopiując `report_category_id`, `title`, `description` i `location` reportu.

Przykład: przy masterze „Dziura w jezdni” report „Dziura w jezdni na Długiej” 20 m dalej trafia pod ten master, a report „Zepsuta latarnia” 5 m dalej tworzy nowy. Dopasowania wykonują się po kolei (advisory lock), więc dwa równoczesne zgłoszenia tego samego problemu nie tworzą dwóch masterów.

Pola `PATCH`: `report_category_id`, `title`, `description`, `location` (JSON). Pole `user_id` jest niezmienne, a `master_report_id` zmienia tylko `move`. Edycja nie uruchamia ponownego dopasowania i nie zmienia treści mastera.

Request `POST /reports/{id}/move`:

```json
{ "master_report_id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20" }
```

`null` wydziela report jako nowy master utworzony z jego treści. Pole jest wymagane. Gdy usunięty lub przepięty report był ostatnim reportem mastera, backend usuwa master razem z komentarzami i polubieniami.

## report photos

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| POST | `/reports/{report_id}/photos` | dodanie zdjęć | autor, `admin` | 201 | 401, 403, 404, 413, 422 |
| GET | `/reports/{report_id}/photos` | lista zdjęć reportu | zalogowany | 200 | 401, 404 |
| DELETE | `/reports/{report_id}/photos/{id}` | usunięcie | autor, `admin` | 204 | 401, 403, 404 |
| GET | `/photos/{id}/file` | plik zdjęcia | publiczny | 200 | 404 |

`POST` przyjmuje `multipart/form-data` z jednym lub kilkoma polami `photos` i zwraca listę dodanych zdjęć w formacie z przykładu reportu. Zdjęcia są niezmienne, dlatego brak `PATCH`.

- Report ma najwyżej 5 zdjęć. Dozwolone są JPEG, PNG i WebP do 10 MB, a typ jest rozpoznawany po nagłówku pliku.
- Pliki są zapisywane w katalogu `UPLOAD_DIR` (domyślnie `apps/api/uploads`, ignorowany przez Git) pod kluczem `reports/{report_id}/{photo_id}.{ext}`.
- `url` jest ścieżką względem adresu API. Plik jest publiczny, żeby aplikacja mogła go pokazać bez nagłówka z tokenem.

## master-reports

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| GET | `/master-reports` | lista z filtrami | publiczny | 200 | 422 |
| GET | `/master-reports/{id}` | pobranie ze zdjęciami | publiczny | 200 | 404 |
| PATCH | `/master-reports/{id}` | aktualizacja | `office`, `admin` | 200 | 401, 403, 404 (brak mastera, kategorii, statusu lub instytucji), 422 |
| DELETE | `/master-reports/{id}` | usunięcie mastera bez reportów wraz z dyskusją | `admin` | 204 | 401, 403, 404, 409 (ma reporty) |

Mastery tworzy wyłącznie backend przy dodawaniu lub przepinaniu reportu, dlatego nie ma `POST`. Filtry `GET /master-reports`: `status_id`, `report_category_id`, `responsible_institution_id` oraz `longitude`, `latitude`, `radius_m`. Lista jest posortowana od najnowszych.

Odpowiedź `GET /master-reports/{id}`:

```json
{
  "id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20",
  "report_category_id": 2,
  "status_id": 2,
  "responsible_office_id": null,
  "responsible_service_entity_id": 17,
  "title": "Dziura w jezdni przy ul. Długiej",
  "description": "Dziura w jezdni przy ul. Długiej 5.",
  "location": { "longitude": 19.9449, "latitude": 50.0647 },
  "response": "Zgłoszenie przekazano do zarządcy drogi.",
  "report_count": 3,
  "photos": [],
  "edited_at": "2026-04-16T12:00:00Z",
  "created_at": "2026-04-16T10:00:00Z"
}
```

`photos` zawiera zdjęcia wszystkich reportów mastera i występuje tylko w szczegółach. Elementy listy mają te same pola bez `photos`. Reporty mastera zwraca `GET /reports?master_report_id=...`.

Pola `PATCH`: `report_category_id`, `status_id`, `responsible_institution_id`, `title`, `description`, `location`, `response`. `null` jest dozwolony tylko dla `responsible_institution_id` i `response`. Status można zmienić na dowolny, także wstecz. Zmiana treści mastera nie zmienia jego reportów. ID w przykładzie są ilustracyjne; wartości słowników należy pobrać z endpointów słowników.

## comments

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| GET | `/master-reports/{id}/comments` | lista komentarzy mastera | publiczny | 200 | 401 (nieważny token), 404 |
| POST | `/master-reports/{id}/comments` | dodanie | zalogowany | 201 | 401, 404, 422 |
| DELETE | `/comments/{id}` | usunięcie | autor, `office`, `admin` | 204 | 401, 403, 404 |
| PUT | `/comments/{id}/like` | polubienie | zalogowany | 200 | 401, 404 |
| DELETE | `/comments/{id}/like` | cofnięcie polubienia | zalogowany | 200 | 401, 404 |

Request `POST` to `{"content": "Potwierdzam, dziura jest coraz większa."}`. Odpowiedź:

```json
{
  "id": "e1f2a3b4-5c6d-4e7f-8a9b-0c1d2e3f4a5b",
  "master_report_id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20",
  "user_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "content": "Potwierdzam, dziura jest coraz większa.",
  "like_count": 4,
  "liked_by_me": true,
  "created_at": "2026-04-16T11:00:00Z"
}
```

- Lista jest posortowana od najstarszych. Token jest opcjonalny; bez niego `liked_by_me` ma wartość `false`.
- Komentarzy nie można edytować, bo tabela nie ma `edited_at`.
- `PUT` i `DELETE` na `/like` są idempotentne i zwracają komentarz z aktualnym `like_count`.

## słowniki

| Metoda | Ścieżka | Opis | Sukces |
| --- | --- | --- | --- |
| GET | `/report-categories` | kategorie reportów | 200 |
| GET | `/master-report-statuses` | statusy masterów | 200 |

Oba endpointy są publiczne i zwracają listę `[{"id": 1, "name": "improvement"}, ...]` posortowaną po `id`.

## institution-contacts

Katalog czyta tabelę `local_government_offices`; nazwa ścieżki API pozostaje bez zmian. `service_entities` jest na tym etapie katalogiem DB i nie ma endpointów.

Dane referencyjne z seeda, tylko odczyt i publiczne. Id to liczba całkowita, nie UUID.

| Metoda | Ścieżka | Opis | Sukces | Błędy |
| --- | --- | --- | --- | --- |
| GET | `/institution-contacts` | lista z filtrami | 200 | 422 |
| GET | `/institution-contacts/{id}` | pobranie | 200 | 404 |

Filtry: `teryt_code`, `province`, `county`, `local_government_type` (dokładnie), `q` (fragment `local_government_name` bez rozróżniania wielkości liter). Odpowiedź zawiera wszystkie kolumny z [data-model.md](data-model.md).

## Otwarte pytania

| Nr | Pytanie | Wpływ |
| --- | --- | --- |
| 1 | Jak master trafia do odpowiedzialnej jednostki i jak potwierdzane są postęp oraz zakończenie? Relację przechowuje `responsible_office_id` albo `responsible_service_entity_id`, obecnie ustawiane ręcznie przez `office` lub `admin`. | obsługa wysyłki i statusów |
| 2 | Kiedy mock dopasowania zastąpi klasyfikator LLM, który porówna też opisy i zdjęcia? | `POST /reports` |
| 3 | Czy `limit/offset` wystarcza, czy potrzebna paginacja kursorowa? | wszystkie listy |
| 4 | Czy komentarze mają pokazywać imię autora? Teraz zwracają tylko `user_id`. | `/master-reports/{id}/comments` |
