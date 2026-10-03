# API CRUD

Endpointy `auth` i `users` mają status `done`, pozostałe `planned`. Nazwy pól są takie same jak kolumny w [data-model.md](data-model.md).

## Konwencje

- Format: JSON, pola w snake_case. Identyfikatory użytkowników, masterów, reportów, zdjęć i komentarzy jako UUID w postaci tekstu; identyfikatory kategorii, statusów i instytucji jako liczby całkowite.
- Daty: ISO 8601 z strefą czasową (UTC).
- Pola `id`, `created_at`, `edited_at` są tylko do odczytu. Serwer ignoruje je w requestach albo zwraca 422.
- `PATCH` przyjmuje podzbiór pól (częściowa aktualizacja). `PUT` nie jest używany.
- Lokalizacja w JSON to obiekt `{"longitude": 19.9449, "latitude": 50.0647}`. Zakres: longitude od -180 do 180, latitude od -90 do 90 (WGS 84).
- `password_hash` nie pojawia się w żadnej odpowiedzi. Request przyjmuje `password`, a serwer zapisuje hash.
- Kolekcje: paginacja `limit` (domyślnie 50, maksymalnie 200) i `offset`. Odpowiedź: `{"items": [...], "total": 123, "limit": 50, "offset": 0}`.
- Błędy w formacie FastAPI: `{"detail": "..."}`, a dla 422 lista błędów walidacji.

### Kody błędów

| Kod | Kiedy |
| --- | --- |
| 401 | brak tokenu, token nieważny lub wygasły, użytkownik z tokenu nie istnieje |
| 403 | rola nie pozwala na operację |
| 404 | brak zasobu o podanym id |
| 409 | naruszenie unikalności albo klucza obcego przy usuwaniu |
| 422 | niepoprawne dane (typ, pusty `title` lub `description`, brak kontaktu użytkownika, zły zakres współrzędnych) |

## Przegląd endpointów

| Zasób | Ścieżka bazowa | Operacje |
| --- | --- | --- |
| auth | `/auth` | login, me |
| users | `/users` | create, list, get, update, delete |
| master_reports | `/master-reports` | create, list, get, update, delete; zapis kontrolowany przez backend |
| reports | `/reports` | create, list, get, update, delete |
| report_photos | `/reports/{report_id}/photos` | create, list, delete (bez update) |
| institution_contacts | `/institution-contacts` | list, get (tylko odczyt) |

Kategorie, statusy, komentarze masterów i polubienia mają tabele w bazie. Ich endpointy wymagają osobnego projektu; poniższy plan ich jeszcze nie definiuje.

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

## master-reports

| Metoda | Ścieżka | Opis | Sukces | Błędy |
| --- | --- | --- | --- | --- |
| POST | `/master-reports` | utworzenie przez backend po klasyfikacji | 201 | 404 (brak kategorii, statusu lub instytucji), 422 |
| GET | `/master-reports` | lista | 200 | - |
| GET | `/master-reports/{id}` | pobranie | 200 | 404 |
| PATCH | `/master-reports/{id}` | aktualizacja przez backend | 200 | 404, 422 |
| DELETE | `/master-reports/{id}` | usunięcie mastera bez powiązanych reportów wraz z dyskusją | 204 | 404, 409 (ma reporty) |

Odpowiedź:

```json
{
  "id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20",
  "report_category_id": 2,
  "status_id": 2,
  "responsible_institution_id": 17,
  "title": "Dziura w jezdni przy ul. Długiej",
  "description": "Dziura w jezdni przy ul. Długiej 5.",
  "location": { "longitude": 19.9449, "latitude": 50.0647 },
  "response": "Zgłoszenie przekazano do zarządcy drogi.",
  "edited_at": "2026-04-16T12:00:00Z",
  "created_at": "2026-04-16T10:00:00Z"
}
```

Pola wymagane przy utworzeniu: `report_category_id`, `status_id`, `title`, `description`, `location`. `responsible_institution_id` i `response` mogą być null. Backend kopiuje początkową treść z pierwszego reportu, potem aktualizuje master niezależnie. Backend obsługuje przypisanie instytucji i przejścia między statusami z [data-model.md](data-model.md). ID w przykładzie są ilustracyjne; wartości słowników należy pobrać po nazwie.

Uprawnienia do tych operacji wymagają ustalenia przed implementacją endpointów.

## reports

| Metoda | Ścieżka | Opis | Sukces | Błędy |
| --- | --- | --- | --- | --- |
| POST | `/reports` | zapis przed klasyfikacją, bez mastera | 201 | 404 (brak użytkownika lub kategorii), 422 |
| GET | `/reports` | lista z filtrami | 200 | 422 |
| GET | `/reports/{id}` | pobranie | 200 | 404 |
| PATCH | `/reports/{id}` | aktualizacja | 200 | 404, 422 |
| DELETE | `/reports/{id}` | usunięcie wraz ze zdjęciami | 204 | 404 |

Filtry `GET /reports`:

| Parametr | Znaczenie |
| --- | --- |
| user_id | zgłoszenia użytkownika |
| master_report_id | zgłoszenia powiązane z masterem |
| longitude, latitude, radius_m | zgłoszenia w promieniu (metry) od punktu, wymagane razem |

Request `POST /reports`:

```json
{
  "user_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "report_category_id": 2,
  "title": "Dziura przy ul. Długiej 5",
  "description": "Dziura w jezdni przy ul. Długiej 5.",
  "location": { "longitude": 19.9449, "latitude": 50.0647 }
}
```

Odpowiedź:

```json
{
  "id": "9a2b8c44-7d5e-4f10-a3b1-6c0d1e2f3a44",
  "user_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "master_report_id": null,
  "report_category_id": 2,
  "title": "Dziura przy ul. Długiej 5",
  "description": "Dziura w jezdni przy ul. Długiej 5.",
  "location": { "longitude": 19.9449, "latitude": 50.0647 },
  "edited_at": "2026-04-16T10:00:00Z",
  "created_at": "2026-04-16T10:00:00Z"
}
```

Pola `PATCH`: `report_category_id`, `title`, `description`, `location`. Pole `user_id` jest niezmienne. Backend przypisuje `master_report_id` dopiero po zapisaniu i klasyfikacji; frontend go nie ustawia. Utworzenie lub aktualizacja pojedynczego reportu nie aktualizuje automatycznie treści mastera.

## report photos

| Metoda | Ścieżka | Opis | Sukces | Błędy |
| --- | --- | --- | --- | --- |
| POST | `/reports/{report_id}/photos` | dodanie zdjęcia | 201 | 404, 409 (duplikat klucza), 422 |
| GET | `/reports/{report_id}/photos` | lista zdjęć zgłoszenia | 200 | 404 |
| DELETE | `/reports/{report_id}/photos/{id}` | usunięcie | 204 | 404 |

Zdjęcia są niezmienne, dlatego brak `PATCH`. Request i odpowiedź:

```json
{ "storage_key": "reports/9a2b8c44/photo-1.jpg" }
```

```json
{
  "id": "c3d4e5f6-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
  "report_id": "9a2b8c44-7d5e-4f10-a3b1-6c0d1e2f3a44",
  "storage_key": "reports/9a2b8c44/photo-1.jpg",
  "created_at": "2026-04-16T10:05:00Z"
}
```

Endpoint przyjmuje tylko klucz. Sposób wgrywania pliku jest otwartym pytaniem.

## institution-contacts

Dane referencyjne z seeda, tylko odczyt. Id to liczba całkowita, nie UUID.

| Metoda | Ścieżka | Opis | Sukces | Błędy |
| --- | --- | --- | --- | --- |
| GET | `/institution-contacts` | lista z filtrami | 200 | - |
| GET | `/institution-contacts/{id}` | pobranie | 200 | 404 |

Filtry: `teryt_code` (dokładnie), `province`, `county`, `local_government_type`, `q` (fragment `local_government_name`). Odpowiedź zawiera wszystkie kolumny z [data-model.md](data-model.md).

## Otwarte pytania

Na te pytania nie odpowiada obecny schemat. Do czasu decyzji nie implementujemy tych elementów.

| Nr | Pytanie | Wpływ |
| --- | --- | --- |
| 1 | Logowanie (JWT) i dostęp do `users` są gotowe. Kto może edytować cudze reporty i mastery (`office`, `admin`)? | `/reports`, `/master-reports` |
| 2 | Kto może aktualizować treść mastera, jego `response` i status? Tworzenie i przypisanie mastera obsługuje backend po klasyfikacji. | `/master-reports` |
| 3 | Jak master trafia do odpowiedzialnej jednostki i jak potwierdzane są postęp oraz zakończenie? Relację przechowuje `responsible_institution_id`. | obsługa wysyłki i statusów |
| 4 | Jak wgrywane są pliki zdjęć (multipart w API, presigned URL)? | `/reports/{id}/photos` |
| 5 | Czy `limit/offset` wystarcza, czy potrzebna paginacja kursorowa? | wszystkie listy |
| 6 | Jakie będą endpointy odczytu słowników, komentarzy i polubień mastera? Tabele już istnieją; inicjatywy pozostają poza obecnym schematem. | rozszerzenie planu API |
