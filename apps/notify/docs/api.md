# API powiadomień

## Konwencje

- Format: JSON, pola w snake_case. Nieznane pola zwracają 422.
- Adres w sieci aplikacji: `http://notify:<NOTIFY_PORT>`. Port określa konfiguracja wdrożenia.
- Serwis nie wymaga tokenu użytkownika. Compose nie publikuje jego portu na hoście.
- Typ zgłoszenia wybiera szablon Markdown z katalogu `templates/`. Mail zawiera wersję HTML z formatowaniem i wersję tekstową.

## Przegląd endpointów

| Metoda | Ścieżka | Opis | Sukces |
| --- | --- | --- | --- |
| GET | `/health` | sprawdzenie działania aplikacji | 200 |
| POST | `/send` | wysłanie jednej wiadomości | 200 |

### GET /health

```json
{"status": "ok"}
```

Nie sprawdza danych logowania ani połączenia z Gmail SMTP.

### POST /send

Request:

```json
{
  "to": "recipient@example.com",
  "subject": "Aktualizacja zgłoszenia",
  "description": "Na ścieżce przy parku brakuje oświetlenia.",
  "report_type": "issue",
  "first_name": "Jan",
  "last_name": "Kowalski",
  "anonymous": false,
  "location": {"longitude": 19.9449, "latitude": 50.0647},
  "photos": [
    {"storage_key": "reports/9a2b8c44-7d5e-4f10-a3b1-6c0d1e2f3a44/c3d4e5f6-1a2b-4c3d-8e9f-0a1b2c3d4e5f.png"}
  ]
}
```

| Pole | Wymagania |
| --- | --- |
| `to` | jeden poprawny adres email, wymagany także w trybie mock |
| `subject` | od 1 do 255 znaków, bez znaków nowej linii |
| `description` | niepusty opis wstawiany do szablonu jako plaintext |
| `report_type` | `issue` albo `improvement`, zgodnie z kategoriami w bazie |
| `first_name` | imię, wymagane przy `anonymous=false` |
| `last_name` | nazwisko, wymagane przy `anonymous=false` |
| `anonymous` | boolean, domyślnie `false`; `true` ukrywa dane zgłaszającego |
| `location` | opcjonalny obiekt z `longitude` (-180 do 180) i `latitude` (-90 do 90), WGS 84 |
| `photos` | opcjonalna lista do 5 obiektów ze `storage_key` istniejącego zdjęcia; domyślnie `[]` |

`issue` wybiera [issue.md](../templates/issue.md), a `improvement` [improvement.md](../templates/improvement.md). Szablony zawierają miejsca `{description}`, `{reporter}` i `{pin}`. Markdown szablonu jest renderowany przed wstawieniem danych. Opis i dane zgłaszającego są wstawiane dosłownie, z zachowaniem nowych linii; nie są interpretowane jako HTML, Markdown ani kolejny szablon.

Wiadomość imienna zawiera `Zgłoszone przez: Jan Kowalski`. Imię i nazwisko są przycinane z otaczających spacji i muszą być niepuste, bez znaków nowej linii.

Dla zgłoszenia anonimowego ustaw `anonymous=true`. Imię i nazwisko można pominąć lub przekazać jako `null`. Jeśli podasz poprawne dane, zostaną pominięte w mailu; wiadomość zawiera wyłącznie `Zgłoszone przez: anonimowo`. Serwis nie usuwa danych osobowych wpisanych w `description` lub `subject`.

Przykład anonimowy:

```json
{
  "to": "recipient@example.com",
  "subject": "Propozycja oświetlenia ścieżki",
  "description": "Proponujemy zamontowanie lamp na ścieżce przy parku.",
  "report_type": "improvement",
  "anonymous": true
}
```

Nadawcą jest adres z `SMTP_USER`. Wysyłka odbywa się w trakcie obsługi żądania, bez kolejki.

Odpowiedź po przyjęciu wiadomości przez serwer SMTP:

```json
{"status": "sent"}
```

To potwierdzenie przyjęcia przez SMTP, nie dostarczenia do skrzynki odbiorcy.

## Lokalizacja

Backend może przekazać `location` bezpośrednio z reportu. Obie współrzędne są wymagane, jeśli obiekt został podany. Serwis generuje [link Google Maps](https://developers.google.com/maps/documentation/urls/get-started#search) z parametrami `api=1` i `query=latitude,longitude`. W mailu lokalizacja znajduje się po opisie; w wersji HTML link jest klikalny.

Przy braku `location` lub wartości `null` szablon pokazuje `Przybliżona lokalizacja zgłoszenia: nieokreślono`.

## Zdjęcia

Backend przekazuje `storage_key` z `report_photos` lub listę `photos` z odpowiedzi API. Dodatkowe pola zdjęcia (`id`, `report_id`, `created_at`, `url`) są pomijane. Przykładowe klucze powyżej są ilustracyjne.

Klucz ma format `reports/{report_id}/{photo_id}.{ext}` stosowany przez API, z rozszerzeniem `jpg`, `png` albo `webp`. Notify odczytuje plik z katalogu `UPLOAD_DIR` i dodaje go jako załącznik. Nie korzysta z bazy ani nie pobiera plików przez HTTP. Compose montuje ten sam wolumen `api_uploads` co API, tylko do odczytu.

Dozwolone są JPEG, PNG i WebP do 10 MB na zdjęcie, tak jak w API. Łączny limit załączników jednego maila wynosi 20 MB. Brak zdjęcia, niepoprawny plik albo przekroczenie limitu blokuje całą wysyłkę przed połączeniem z SMTP.

Pominięcie `photos` lub pusta lista oznacza mail bez załączników. Dowolne ścieżki systemowe, URL i klucze wychodzące poza katalog zdjęć są odrzucane.

## Tryb mock

`SMTP_MOCK=true` podmienia odbiorcę z `to` na `SMTP_MOCK_DESTINATION`, zarówno w nagłówku wiadomości, jak i w wysyłce SMTP. Mail nadal jest wysyłany przez Gmail, a temat i treść pozostają bez zmian.

Przy `SMTP_MOCK=false` używany jest odbiorca z żądania. Brak zmiennej oznacza `false`. Pusty lub błędny adres testowy przy włączonym mocku blokuje wysyłkę.

## Kody błędów

| Kod | Kiedy |
| --- | --- |
| 404 | zdjęcie wskazane przez `storage_key` nie istnieje |
| 413 | zdjęcie przekracza 10 MB albo załączniki przekraczają łącznie 20 MB |
| 422 | niepoprawne dane wiadomości, lokalizacja, klucz lub format zdjęcia, ponad 5 zdjęć, brak wymaganych pól albo dodatkowe pola żądania |
| 503 | brak danych SMTP, niepoprawna konfiguracja mock albo brak możliwości odczytu zdjęcia |
| 502 | błąd połączenia, TLS, logowania lub wysyłki SMTP |

Błędy mają format `{"detail": "..."}`. Dla walidacji żądania `detail` zawiera listę błędów.
