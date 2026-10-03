# API powiadomień

## Konwencje

- Format: JSON, pola w snake_case. Nieznane pola zwracają 422.
- Adres w sieci aplikacji: `http://notify:<NOTIFY_PORT>`. Port określa konfiguracja wdrożenia.
- Serwis nie wymaga tokenu użytkownika. Compose nie publikuje jego portu na hoście.
- Wiadomości mają wyłącznie format plaintext. Typ zgłoszenia wybiera szablon z katalogu `templates/`.

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
  "anonymous": false
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

`issue` wybiera [issue.txt](../templates/issue.txt), a `improvement` [improvement.txt](../templates/improvement.txt). Szablony zawierają miejsca `{description}` i `{reporter}`. Opis jest wstawiany dosłownie, z zachowaniem nowych linii; nie jest interpretowany jako HTML ani kolejny szablon.

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

## Tryb mock

`SMTP_MOCK=true` podmienia odbiorcę z `to` na `SMTP_MOCK_DESTINATION`, zarówno w nagłówku wiadomości, jak i w wysyłce SMTP. Mail nadal jest wysyłany przez Gmail, a temat i treść pozostają bez zmian.

Przy `SMTP_MOCK=false` używany jest odbiorca z żądania. Brak zmiennej oznacza `false`. Pusty lub błędny adres testowy przy włączonym mocku blokuje wysyłkę.

## Kody błędów

| Kod | Kiedy |
| --- | --- |
| 422 | niepoprawny adres, temat, opis, typ zgłoszenia lub dane zgłaszającego, brak wymaganych pól albo dodatkowe pola |
| 503 | brak danych SMTP, flaga mock inna niż `true` lub `false`, brak lub błędny adres testowy przy włączonym mocku |
| 502 | błąd połączenia, TLS, logowania lub wysyłki SMTP |

Błędy 502 i 503 mają format `{"detail": "..."}`. Odpowiedź 422 zawiera listę błędów walidacji.
