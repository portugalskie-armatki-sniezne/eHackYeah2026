# API CRUD

Endpointy CRUD opisane poniżej mają status `done`. Nazwy pól są takie same jak kolumny w [data-model.md](data-model.md). `/inference` udostępnia analizę z konfigurowalnym tłumaczem i klasyfikatorem Laya.

## Konwencje

- Format: JSON, pola w snake_case. Identyfikatory użytkowników, masterów, reportów, zdjęć i komentarzy jako UUID w postaci tekstu; identyfikatory kategorii, statusów, urzędów i jednostek usługowych jako liczby całkowite.
- Wyjątek: `POST /reports`, `POST /reports/{id}/photos`, `POST /master-reports/{id}/photos`, `POST /master-reports/{id}/photo-proposals` i endpointy `POST /inference`, `POST /inference/service-entity` oraz `POST /inference/service-entity/recommendation` przyjmują `multipart/form-data`, bo mogą zawierać pliki zdjęć.
- Daty: ISO 8601 z strefą czasową (UTC).
- CORS: API przyjmuje na razie zapytania z każdej domeny (`*`). Uwierzytelnianie opiera się na nagłówku `Authorization`, bez ciasteczek.
- Pola `id`, `created_at`, `edited_at` są tylko do odczytu. Serwer ignoruje je w requestach albo zwraca 422.
- `PATCH` przyjmuje podzbiór pól (częściowa aktualizacja). `PUT` jest używany tylko do idempotentnego polubienia komentarza.
- Lokalizacja w JSON to obiekt `{"longitude": 19.9449, "latitude": 50.0647}`. Zakres: longitude od -180 do 180, latitude od -90 do 90 (WGS 84).
- `password_hash` nie pojawia się w żadnej odpowiedzi. Request przyjmuje `password`, a serwer zapisuje hash.
- Kolekcje: paginacja `limit` (domyślnie 50, maksymalnie 200) i `offset`. Odpowiedź: `{"items": [...], "total": 123, "limit": 50, "offset": 0}`. Słowniki i zdjęcia zwracają zwykłą listę.
- Filtr po okolicy: `longitude`, `latitude` i `radius_m` (metry, do 100 000) podawane razem, inaczej 422.
- Nieznane pola w body JSON zwracają 422.
- Błędy w formacie FastAPI: `{"detail": "..."}`, a dla 422 lista błędów walidacji.
- Generacja formularza przez `POST /visualizations` również używa multipart; [kontrakt](visualizations.md) opisuje idempotencję, historię i wysyłkę testową.

### Kody błędów

| Kod | Kiedy |
| --- | --- |
| 400 | nieprawidłowy token Google przy łączeniu konta |
| 401 | brak tokenu, token nieważny lub wygasły, użytkownik z tokenu nie istnieje |
| 403 | rola nie pozwala na operację |
| 404 | brak zasobu o podanym id albo brak kategorii, statusu, urzędu, jednostki usługowej lub mastera wskazanego w body |
| 409 | naruszenie unikalności albo klucza obcego przy usuwaniu, master ma już zdjęcie, inna propozycja czeka na decyzję, albo decyzja o propozycji już zapadła |
| 410 | wygasły formularz wizualizacji lub usunięty wynik |
| 413 | zdjęcie większe niż 10 MB |
| 422 | niepoprawne dane (typ, pusty `title` lub `description`, brak kontaktu użytkownika, zły zakres współrzędnych, zły format lub za dużo zdjęć) |
| 429 | limit generacji użytkownika, z nagłówkiem `Retry-After` |
| 502 | dostawca analizy zwrócił niepoprawny wynik |
| 503 | dostawca analizy lub GUGiK jest niedostępny, logowanie przez Google nie jest skonfigurowane albo nie udało się pobrać kluczy Google |

## Przegląd endpointów

| Zasób | Ścieżka bazowa | Operacje |
| --- | --- | --- |
| auth | `/auth` | login, google, google link, me |
| users | `/users` | create, list, get, update, delete |
| reports | `/reports` | create z dopasowaniem do mastera, list, get, update, delete, move |
| report_photos | `/reports/{report_id}/photos`, `/photos/{id}/file` | create, list, delete, pobranie pliku (bez update) |
| master_reports | `/master-reports` | list, get, update, delete; tworzy je backend |
| master_report_photo_proposals | `/master-reports/{id}/photo-proposals`, `/photo-proposals/{id}` | create, list, approve, reject, pobranie pliku |
| master_report_comments | `/master-reports/{id}/comments`, `/comments/{id}` | create, list, delete, like, unlike |
| notifications | `/notifications` | list, unread-count, read, read-all, delete |
| słowniki | `/report-categories`, `/master-report-statuses` | list (tylko odczyt) |
| local_government_offices | `/institution-contacts` | list, get (tylko odczyt) |
| service_entities | `/service-entities` | list, get (tylko odczyt) |
| projects | `/projects`, `/projects/categories`, `/projects/search` | list, categories, get po slug, wyszukiwanie wektorowe i pełnotekstowe (tylko odczyt); biblioteka innowacji ROPS z `db/seeds/seed_rops.sql.tar.gz` |
| inference | `/inference`, `/inference/service-entity`, `/inference/service-entity/recommendation` | tłumaczenie, klasyfikacja, wybór typu i rekomendacja instytucji według lokalizacji siedziby; [kontrakt](inference.md#rekomendacja-instytucji-dla-nowego-zgłoszenia) |
| visualizations | `/visualizations`, `/reports/{id}/visualizations`, `/master-reports/{id}/visualizations` | generacja, status, pliki i historia; [kontrakt](visualizations.md) |
| deliveries | `/master-reports/{id}/delivery` | status automatycznego maila testowego dla nowej sprawy; autor lub `admin` |

### Dostęp

| Kto | Co może |
| --- | --- |
| publiczny | rejestracja, logowanie, odczyt reportów i metadanych zdjęć, mastery, komentarze, słowniki, urzędy, jednostki usługowe, innowacje ROPS, pliki zdjęć |
| zalogowany | dodawanie reportów, komentarzy i polubień, proponowanie zdjęcia do mastera bez zdjęcia, odczyt i obsługa własnych powiadomień, analiza przez `/inference`, połączenie własnego konta z Google |
| autor reportu | edycja i usuwanie reportu oraz jego zdjęć |
| autor mastera | przyjęcie lub odrzucenie zdjęcia zaproponowanego do jego mastera |
| autor komentarza | usuwanie komentarza |
| `office` | jak zalogowany oraz edycja masterów, przepinanie reportów, usuwanie dowolnych komentarzy, wyróżnianie komentarzy |
| `admin` | jak `office` oraz edycja i usuwanie dowolnych reportów, usuwanie masterów |

## auth

Logowanie zwraca token JWT (HS256, ważny 24 godziny, podpisany `JWT_SECRET` z `.env`). Chronione endpointy wymagają nagłówka `Authorization: Bearer <token>`. Token zawiera tylko id użytkownika. Rola jest czytana z bazy przy każdym zapytaniu, więc zmiana roli i usunięcie konta działają od razu. Wylogowanie polega na usunięciu tokenu po stronie klienta.

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | logowanie | publiczny | 200 | 401, 422 |
| POST | `/auth/google` | logowanie przez Google | publiczny | 200 | 401, 403, 409, 422, 503 |
| POST | `/auth/google/link` | połączenie konta z kontem Google | zalogowany | 200 | 400, 401, 409, 422, 503 |
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

### Logowanie przez Google

Oba endpointy przyjmują token ID, który Google wydał klientowi (Google Identity Services):

```json
{
  "credential": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."
}
```

API sprawdza podpis tokenu kluczami Google, wystawcę, termin ważności i odbiorcę, którym musi być `GOOGLE_CLIENT_ID` z `.env`. Bez tej zmiennej oba endpointy zwracają 503. Ten sam kod oznacza, że nie udało się pobrać kluczy Google.

`POST /auth/google` zwraca taki sam token jak `POST /auth/login`:

- Konto jest wyszukiwane po identyfikatorze konta Google (`sub`), a nie po emailu, więc zmiana adresu w Google nie odcina użytkownika od konta.
- Pierwsze logowanie zakłada konto z rolą `user`, emailem z Google i bez hasła. Imię i nazwisko pochodzą z Google. Gdy Google nie poda imienia, API bierze pełną nazwę albo część emaila przed `@`, a brakujące nazwisko zapisuje jako pusty tekst.
- Jeśli email z Google należy już do istniejącego konta, API zwraca 409 i niczego nie łączy. Wielkość liter w emailu nie ma znaczenia. Właściciel takiego konta loguje się hasłem i sam łączy je z Google w ustawieniach profilu.
- Nieprawidłowy token Google zwraca 401, a konto Google bez potwierdzonego emaila 403.

`POST /auth/google/link` łączy konto zalogowanego użytkownika z kontem Google z tokenu i zwraca użytkownika:

- Email w Google może być inny niż email konta.
- Ponowne połączenie zastępuje poprzednie konto Google.
- Konto Google połączone już z innym użytkownikiem zwraca 409.
- Nieprawidłowy token Google zwraca 400, a nie 401, bo sesja użytkownika pozostaje ważna.

Konto bez hasła nie zaloguje się przez `POST /auth/login`, dopóki właściciel nie ustawi hasła przez `PATCH /users/{id}`. Pole `google_linked` użytkownika mówi, czy konto jest połączone z Google.

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
  "google_linked": false,
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
| POST | `/reports` | dodanie z dopasowaniem do mastera i ustaleniem gminy i powiatu | zalogowany | 201 | 401, 403, 404, 409, 410, 413, 422, 503 |
| GET | `/reports` | lista z filtrami | publiczny | 200 | 422 |
| GET | `/reports/{id}` | pobranie | publiczny | 200 | 404 |
| PATCH | `/reports/{id}` | aktualizacja | autor, `admin` | 200 | 401, 403, 404, 422, 503 |
| DELETE | `/reports/{id}` | usunięcie wraz ze zdjęciami | autor, `admin` | 204 | 401, 403, 404 |
| POST | `/reports/{id}/move` | przepięcie do innego mastera | `office`, `admin` | 200 | 401, 403, 404, 422 |

Filtry `GET /reports`: `user_id`, `master_report_id` oraz `longitude`, `latitude`, `radius_m`. Lista jest posortowana od najnowszych.

Request `POST /reports` to `multipart/form-data`. `user_id` pochodzi z tokenu. Pole `photos` można powtórzyć do 5 razy albo pominąć.

Opcjonalne `visualization_draft_id` publikuje własny formularz wizualizacji, którego `report_type` musi odpowiadać kategorii zgłoszenia, wraz z historią i zleceniami w toku. Bez `photos` API kopiuje jego ostatnie źródła. Nowy master otrzymuje jedno zlecenie maila na wymuszony adres testowy; dołączenie do istniejącego mastera nie wysyła maila. Szczegóły opisuje [kontrakt integracji](visualizations.md).

Przykład:

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
  "municipality_teryt": "1261011",
  "municipality_name": "Kraków (miasto)",
  "county_teryt": "1261",
  "county_name": "powiat Kraków",
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

### Przypisanie do gminy i powiatu

Zgłoszenia są przyjmowane wyłącznie z województwa małopolskiego (prefiks TERYT `12`).
Przed zapisem backend ustala gminę i powiat ze współrzędnych przez
[ULDK GUGiK](https://uldk.gugik.gov.pl/opis.html), operację `GetCommuneByXY`
na granicach PRG. Wysyła tylko długość i szerokość geograficzną w WGS 84.
Zapisuje `municipality_teryt` (7 cyfr), `municipality_name`, `county_teryt`
(pierwsze 4 cyfry kodu gminy) i `county_name`. Nazwy pochodzą z odpowiedzi usługi.
Dla Krakowa jako miasta na prawach powiatu są to kody `1261011` i `1261`.
Współrzędne zgłoszenia pozostają bez zmian. Kod gminy można zestawić z `teryt_code`
w katalogu urzędów. Przypisanie terytorialne jest niezależne od
`responsible_office_id` i `responsible_service_entity_id` mastera.

Pola są zwracane przy tworzeniu, odczycie i edycji zgłoszeń. Klient nie ustawia ich
samodzielnie. `PATCH` z lokalizacją wyznacza je ponownie; edycja samego opisu oraz
przepięcie do mastera zachowują przypisanie. Starsze rekordy mają cztery pola `null`
do czasu aktualizacji lokalizacji; migracja nie odpytuje usługi zewnętrznej.

Backend przechowuje do 4096 udanych wyników dla dokładnych współrzędnych w pamięci
procesu API. Wynik jest aktualny przez 24 godziny. Przy przejściowej awarii usługi
starszy wynik może posłużyć jako wynik zastępczy. Restart procesu usuwa cache.
Jednoczesne zapytania dla tego samego punktu współdzielą wynik. Pozostałe trafiają
do kolejki, która mieści do 16 różnych punktów, wliczając aktualnie obsługiwany.
Proces odpytuje ULDK pojedynczo. Przejściowe błędy sieci oraz HTTP 408, 429 i 5xx
ponawia do trzech prób z przerwami 0,5 s i 1 s. Każda próba ma limit 5 s.
Klient czeka na wynik maksymalnie 30 s; zaległe zapytania wygasają w kolejce.

Punkt poza Małopolską lub brak gminy dla punktu oznacza 422. Niejednoznaczna lub
niepoprawna odpowiedź oznacza 503 i unieważnia starszy wynik. Niedostępność po
ponowieniach, pełna kolejka lub przekroczenie czasu oczekiwania oznaczają 503,
jeśli nie ma wyniku w cache. Błąd nie zapisuje nowego zgłoszenia, mastera ani zdjęć;
przy edycji zachowuje poprzednie dane.

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
| GET | `/reports/{report_id}/photos` | lista zdjęć reportu | publiczny | 200 | 404 |
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
| POST | `/master-reports/{id}/photos` | dodanie zdjęcia przez nowy report | zalogowany | 201 | 401, 404, 409 (brak reportu do skopiowania), 413, 422 |
| PATCH | `/master-reports/{id}` | aktualizacja | `office`, `admin` | 200 | 401, 403, 404 (brak mastera, kategorii, statusu, urzędu lub jednostki usługowej), 422 |
| DELETE | `/master-reports/{id}` | usunięcie mastera bez reportów wraz z dyskusją | `admin` | 204 | 401, 403, 404, 409 (ma reporty) |

Mastery tworzy wyłącznie backend przy dodawaniu lub przepinaniu reportu, dlatego nie ma `POST`. Filtry `GET /master-reports`: `status_id`, `report_category_id`, `responsible_office_id`, `responsible_service_entity_id` oraz `longitude`, `latitude`, `radius_m`. Lista jest posortowana od najnowszych.

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
  "author_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "photo_url": "/photos/c3d4e5f6-1a2b-4c3d-8e9f-0a1b2c3d4e5f/file",
  "pending_photo_id": null,
  "pending_photo_url": null,
  "photos": [],
  "edited_at": "2026-04-16T12:00:00Z",
  "created_at": "2026-04-16T10:00:00Z"
}
```

`photos` zawiera zdjęcia wszystkich reportów mastera i występuje tylko w szczegółach. Elementy listy mają te same pola bez `photos`. `photo_url` to najstarsze zdjęcie spośród reportów mastera (albo `null`), żeby mapa mogła pokazać je na pinezce bez pobierania szczegółów każdego mastera. Reporty mastera zwraca `GET /reports?master_report_id=...`.

`POST /master-reports/{id}/photos` przyjmuje jedno pole plikowe `photo` (JPEG, PNG lub WebP, do 10 MB). Tworzy report pod kontem dodającej osoby, powiązany z tym samym masterem. Kopiuje kategorię, tytuł, opis, współrzędne i dane gminy oraz powiatu z najstarszego reportu mastera. Nowy report ma własne ID i daty, a jego jedynym zdjęciem jest przesłany plik. Odpowiedź ma format reportu z `POST /reports`. Zdjęcie jest od razu publiczne, bez akceptacji autora. Dodanie nie zmienia statusu ani odbiorcy sprawy i nie tworzy nowej wysyłki do instytucji.

`author_id` to użytkownik najstarszego reportu mastera. `pending_photo_id` i `pending_photo_url` wskazują starszą propozycję zdjęcia czekającą na jego decyzję albo są `null`, gdy nie ma takiej propozycji; zobacz [photo proposals](#photo-proposals). Lista i mapa używają teraz bezpośredniego dodawania zdjęcia. Istniejące propozycje można nadal zaakceptować lub odrzucić; zdjęcia reportów mają pierwszeństwo w widoku sprawy.

Pola `PATCH`: `report_category_id`, `status_id`, `responsible_office_id`, `responsible_service_entity_id`, `title`, `description`, `location`, `response`. `null` jest dozwolony tylko dla obu pól odpowiedzialnego podmiotu i `response`. Master wskazuje najwyżej jeden podmiot: urząd albo jednostkę usługową. Zmiana odbiorcy na podmiot innego rodzaju wymaga przesłania obu pól, na przykład `{"responsible_office_id": null, "responsible_service_entity_id": 17}`, inaczej API zwraca 422. Status można zmienić na dowolny, także wstecz. Zmiana treści mastera nie zmienia jego reportów. ID w przykładzie są ilustracyjne; wartości słowników należy pobrać z endpointów słowników.

## comments

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| GET | `/master-reports/{id}/comments` | lista komentarzy mastera | publiczny | 200 | 401 (nieważny token), 404 |
| POST | `/master-reports/{id}/comments` | dodanie | zalogowany | 201 | 401, 403 (`highlighted` bez roli `office` lub `admin`), 404, 422 |
| DELETE | `/comments/{id}` | usunięcie | autor, `office`, `admin` | 204 | 401, 403, 404 |
| PUT | `/comments/{id}/like` | polubienie | zalogowany | 200 | 401, 404 |
| DELETE | `/comments/{id}/like` | cofnięcie polubienia | zalogowany | 200 | 401, 404 |

Request `POST` to `{"content": "Potwierdzam, dziura jest coraz większa."}`. Opcjonalne `highlighted: true` wyróżnia komentarz jako oficjalny i jest dostępne tylko dla `office` i `admin`; dla roli `user` zwraca 403. Odpowiedź:

```json
{
  "id": "e1f2a3b4-5c6d-4e7f-8a9b-0c1d2e3f4a5b",
  "master_report_id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20",
  "user_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "author_first_name": "Anna",
  "content": "Potwierdzam, dziura jest coraz większa.",
  "like_count": 4,
  "liked_by_me": true,
  "highlighted": false,
  "created_at": "2026-04-16T11:00:00Z"
}
```

- `author_first_name` to imię autora; nazwisko i dane kontaktowe nie są publiczne.
- Lista jest posortowana od najstarszych. Token jest opcjonalny; bez niego `liked_by_me` ma wartość `false`.
- Komentarzy nie można edytować, bo tabela nie ma `edited_at`.
- `PUT` i `DELETE` na `/like` są idempotentne i zwracają komentarz z aktualnym `like_count`.

## photo proposals

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| POST | `/master-reports/{id}/photo-proposals` | propozycja zdjęcia do mastera bez zdjęcia | zalogowany | 201 | 401, 404, 409 (master ma zdjęcie albo czeka inna propozycja), 413, 422 |
| GET | `/master-reports/{id}/photo-proposals` | propozycje mastera | publiczny | 200 | 422 |
| GET | `/photo-proposals/{id}/file` | plik zaproponowanego zdjęcia | publiczny | 200 | 404 |
| POST | `/photo-proposals/{id}/approve` | przyjęcie zdjęcia | autor mastera, `admin` | 200 | 401, 403, 404, 409 |
| POST | `/photo-proposals/{id}/reject` | odrzucenie zdjęcia | autor mastera, `admin` | 200 | 401, 403, 404, 409 |

`POST` przyjmuje `multipart/form-data` z jednym polem `photo`. Obowiązują te same reguły co dla zdjęć reportu: JPEG, PNG albo WebP do 10 MB, typ rozpoznawany po nagłówku pliku. Odpowiedź:

```json
{
  "id": "9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
  "master_report_id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20",
  "user_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "storage_key": "proposals/9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d.jpg",
  "state": "pending",
  "decided_at": null,
  "url": "/photo-proposals/9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d/file",
  "created_at": "2026-04-16T11:30:00Z"
}
```

- Propozycję można złożyć tylko do mastera, którego żaden report nie ma zdjęcia. Jednocześnie czeka najwyżej jedna propozycja na master, co pilnuje częściowy indeks unikalny.
- Decyduje autor mastera, czyli użytkownik najstarszego reportu mastera, zwracany jako `author_id` w master-reports. `admin` może zdecydować za niego.
- Dopóki `state` to `pending`, master zwraca propozycję jako `pending_photo_id` i `pending_photo_url`, a aplikacja pokazuje ją ze znakiem zapytania.
- `approve` zapisuje zdjęcie jako zdjęcie najstarszego reportu mastera, więc od tej chwili wychodzi w `photo_url` i `photos`, a plik przechodzi z `proposals/{id}.{ext}` na `reports/{report_id}/{photo_id}.{ext}`.
- `reject` usuwa plik, a master znów przyjmuje propozycje. Wiersz zostaje ze stanem `rejected`.
- Obie decyzje tworzą powiadomienie dla osoby, która zdjęcie zaproponowała. Nowa propozycja tworzy powiadomienie dla autora mastera, chyba że zaproponował je on sam: wtedy zdjęcie jest przyjmowane od razu i nie powstaje żadne powiadomienie.
- `GET` filtruje po `state` (domyślnie `pending`); pusty filtr zwraca wszystkie propozycje mastera, od najstarszych.

## notifications

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| GET | `/notifications` | własne powiadomienia, od najnowszych | zalogowany | 200 | 401, 422 |
| GET | `/notifications/unread-count` | liczba nieodczytanych | zalogowany | 200 | 401 |
| PUT | `/notifications/{id}/read` | oznaczenie jako odczytane | odbiorca | 200 | 401, 404 |
| POST | `/notifications/read-all` | oznaczenie wszystkich jako odczytane | zalogowany | 200 | 401 |
| DELETE | `/notifications/{id}` | usunięcie | odbiorca | 204 | 401, 404 |

Powiadomienia tworzy wyłącznie backend, dlatego nie ma `POST` na kolekcji. Każdy widzi tylko swoje: dla cudzego id `PUT` i `DELETE` zwracają 404. Filtr `GET`: `unread=true` zwraca same nieodczytane. Odpowiedź:

```json
{
  "id": "4c5d6e7f-8a9b-4c0d-8e1f-2a3b4c5d6e7f",
  "user_id": "0b0c6f0e-6a1e-4a43-9c7e-2f5d6a1b9c11",
  "kind": "photo_proposal",
  "master_report_id": "5d1f7a52-3c3e-4a7e-8b0a-1f6d2d9e7a20",
  "photo_proposal_id": "9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
  "subject": "Dziura w jezdni przy ul. Długiej",
  "detail": null,
  "photo_proposal_state": "pending",
  "photo_proposal_url": "/photo-proposals/9b8a7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d/file",
  "read_at": null,
  "created_at": "2026-04-16T11:30:00Z"
}
```

| `kind` | Kiedy powstaje | Kto dostaje |
| --- | --- | --- |
| `status_inprogress` | `PATCH /master-reports/{id}` zmienia status na `inprogress` | autorzy wszystkich reportów mastera |
| `status_finished` | ten sam `PATCH` zmienia status na `finished` | autorzy wszystkich reportów mastera |
| `update` | ten sam `PATCH` zmienia cokolwiek innego, na przykład `response` | autorzy wszystkich reportów mastera |
| `comment` | `POST /master-reports/{id}/comments` | autorzy wszystkich reportów mastera poza autorem komentarza |
| `photo_proposal` | `POST /master-reports/{id}/photo-proposals` | autor mastera |
| `photo_approved` | `POST /photo-proposals/{id}/approve` | osoba, która zaproponowała zdjęcie |
| `photo_rejected` | `POST /photo-proposals/{id}/reject` | osoba, która zaproponowała zdjęcie |

- `subject` to tytuł mastera z chwili zdarzenia, więc lista czyta się także po zmianie tytułu. `detail` zawiera treść komentarza albo nową odpowiedź urzędu, inaczej `null`.
- `photo_proposal_state` i `photo_proposal_url` dotyczą zaproponowanego zdjęcia i są `null` dla pozostałych rodzajów. Dzięki `state` aplikacja wie, czy przyciski przyjęcia i odrzucenia jeszcze mają sens.
- Ustawienie tego samego statusu nie jest zmianą i nie tworzy powiadomienia.
- `PUT /{id}/read` jest idempotentne: ponowne wywołanie nie zmienia `read_at`.
- Usunięcie mastera, propozycji albo użytkownika usuwa związane z nimi powiadomienia.

## słowniki

| Metoda | Ścieżka | Opis | Sukces |
| --- | --- | --- | --- |
| GET | `/report-categories` | kategorie reportów | 200 |
| GET | `/master-report-statuses` | statusy masterów | 200 |

Oba endpointy są publiczne i zwracają listę `[{"id": 1, "name": "improvement"}, ...]` posortowaną po `id`.

## institution-contacts

Katalog czyta tabelę `local_government_offices`; nazwa ścieżki API pozostaje bez zmian.

Dane referencyjne z seeda, tylko odczyt i publiczne. Id to liczba całkowita, nie UUID.

| Metoda | Ścieżka | Opis | Sukces | Błędy |
| --- | --- | --- | --- | --- |
| GET | `/institution-contacts` | lista z filtrami | 200 | 422 |
| GET | `/institution-contacts/{id}` | pobranie | 200 | 404 |

Filtry: `teryt_code`, `province`, `county`, `local_government_type` (dokładnie), `q` (fragment `local_government_name` bez rozróżniania wielkości liter). Odpowiedź zawiera wszystkie kolumny z [data-model.md](data-model.md).

## service-entities

Publiczny katalog jednostek usługowych z tabeli `service_entities`, tylko do odczytu.
Id to liczba całkowita. Odpowiedź zawiera wszystkie kolumny opisane w [data-model.md](data-model.md#service_entities),
w tym źródła, kanał zgłoszeniowy i datę weryfikacji `verified_on` w formacie `YYYY-MM-DD`.

| Metoda | Ścieżka | Opis | Sukces | Błędy |
| --- | --- | --- | --- | --- |
| GET | `/service-entities` | lista z filtrami i paginacją | 200 | 422 |
| GET | `/service-entities/{id}` | pobranie jednostki | 200 | 404, 422 |

Filtry `entity_type`, `teryt_code` i `locality` wymagają dokładnego dopasowania i można je łączyć.
`entity_type` przyjmuje jeden z 15 typów katalogu; Swagger pokazuje listę wyboru i objaśnienia kodów.
Nieznany typ zwraca 422. `q` wyszukuje fragment `name` lub `short_name` bez rozróżniania wielkości liter;
znaki `%`, `_` i `\` są traktowane dosłownie. Parametry `limit` i `offset` działają zgodnie z konwencją list,
a wyniki są sortowane po `id`.

Przykład: `/service-entities?entity_type=road_manager&locality=Krak%C3%B3w&limit=20`.
TERYT wskazuje powiązaną gminę, a nie zasięg usług lub jurysdykcję. Typ jednostki nie określa kompletu jej kompetencji.

## projects

Katalog innowacji społecznych Regionalnego Ośrodka Polityki Społecznej (ROPS) oraz wyszukiwarka inicjatyw, tylko do odczytu i publiczne.
Zawiera gotowe rozwiązania problemów społecznych i miejskich, które mogą służyć jako inspiracja lub gotowe innowacje dla zgłaszanych inicjatyw obywatelskich.

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| GET | `/projects` | lista projektów z paginacją i filtrami | publiczny | 200 | 422 |
| GET | `/projects/categories` | unikalne kategorie z liczbą projektów | publiczny | 200 | - |
| GET | `/projects/{slug}` | szczegóły pojedynczego projektu | publiczny | 200 | 404 |
| POST | `/projects/search` | hybrydowe wyszukiwanie projektów | publiczny | 200 | 422 |

Parametry `GET /projects`:
- `category` (tekst, opcjonalny): filtrowanie po nazwie kategorii lub `category_slug`.
- `q` (tekst, opcjonalny): fraza wyszukiwana w tytule lub podsumowaniu (`ILIKE`).
- `limit` (liczba całkowita, domyślnie 50, od 1 do 200) i `offset` (liczba całkowita, domyślnie 0).

`GET /projects/categories` zwraca listę obiektów `[{"category": "Dostępność", "category_slug": "dostepnosc", "count": 12}, ...]`, posortowaną malejąco według liczby projektów.

`POST /projects/search` przyjmuje body JSON:

```json
{
  "query": "jak ułatwić seniorom poruszanie się po mieście",
  "query_vector": null,
  "category": null,
  "limit": 5
}
```

Tryby wyszukiwania:
1. **Wyszukiwanie wektorowe**: Jeśli pole `query_vector` zawiera 1024-wymiarowy wektor embeddingu, endpoint wykonuje wyszukiwanie po odległości cosinusowej (`<=>`) na kolumnie `summary_vector`, z opcjonalnym filtrem kategorii. Zwraca wynik podobieństwa `score` od 0 do 1.
2. **Wyszukiwanie słów kluczowych ze stemmingiem**: Gdy `query_vector` nie jest podany, zapytanie tekstowe oczyszczane jest z polskich słów pospolitych (stop words) oraz znaków diakrytycznych. Z kluczowych słów wyznaczane są 5-znakowe rdzenie gramatyczne, a zapytanie przeszukuje bazę `projects` i fragmenty `project_chunks`. Dynamiczny system wag punktuje dopasowania w tytule (+0.40), kategorii (+0.30) oraz streszczeniu (+0.15) z bonusem za jednoczesne trafienie wielu słów kluczowych (do maksymalnego wyniku 0.96).

## inference

| Metoda | Ścieżka | Opis | Dostęp | Sukces | Błędy |
| --- | --- | --- | --- | --- | --- |
| POST | `/inference` | tłumaczenie i klasyfikacja według przekazanych pytań | zalogowany | 200 | 401, 413, 422, 502, 503 |
| POST | `/inference/service-entity` | wybór typu jednostki usługowej na podstawie tytułu, opisu i zdjęcia | zalogowany | 200 | 401, 413, 422, 502, 503 |

Request przyjmuje pole formularza `payload` z JSON-em zawierającym `text`, `source_language`,
`target_language` i `questions` oraz opcjonalny plik `image`. Tekst jest wymagany.
Pytania, instrukcje i opcje odpowiedzi określa wywołujący. Zdjęcie podlega limitowi
rozmiaru i regułom formatów zdjęć reportów, ale nie jest zapisywane.

Odpowiedź przy wyłączonych dostawcach i różnych językach:

```json
{
  "translation": { "status": "disabled", "text": null },
  "classification": { "status": "disabled", "answers": {} }
}
```

Przy zgodnych językach tłumaczenie ma status `unchanged` i zawiera wejściowy tekst.
Podłączony tłumacz zwraca `translated`, a działający klasyfikator `classified` i odpowiedzi
z polami `choice` i `scores`. Analiza nie tworzy reportów ani nie przypisuje instytucji.
`POST /inference/service-entity` przyjmuje `payload` z `title` (do 300 znaków),
`description` (do 4000 znaków) i `source_language` (`pl` domyślnie albo `en`),
a także opcjonalny plik `image`. Zwraca `entity_type`, `scores` oraz `translation`.
Lista opcji pochodzi z enuma API, nie od klienta. Także przy niepełnym lub
wielowątkowym opisie model wybiera jedną opcję. Niedostępny model zwraca 503,
a przekroczony limit tokenów modelu lub uszkodzone zdjęcie zwraca 422.
Wynik określa typ, nie identyfikator konkretnej instytucji ani jej jurysdykcję.

Kontrakt, przykład requestu, konfigurację modeli i pomiar trafności opisuje [inference.md](inference.md).

## Otwarte pytania

| Nr | Pytanie | Wpływ |
| --- | --- | --- |
| 1 | Jak master trafia do odpowiedzialnej jednostki i jak potwierdzane są postęp oraz zakończenie? Relację przechowuje `responsible_office_id` albo `responsible_service_entity_id`, obecnie ustawiane ręcznie przez `office` lub `admin`. | obsługa wysyłki i statusów |
| 2 | Kiedy mock dopasowania zastąpi klasyfikator LLM, który porówna też opisy i zdjęcia? | `POST /reports` |
| 3 | Czy `limit/offset` wystarcza, czy potrzebna paginacja kursorowa? | wszystkie listy |
