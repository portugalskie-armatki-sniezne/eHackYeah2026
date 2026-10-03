# API powiadomień

## Konwencje

- Format: JSON, pola w snake_case. Nieznane pola zwracają 422.
- Adres w sieci aplikacji: `http://notify:<NOTIFY_PORT>`. Port określa konfiguracja wdrożenia.
- Serwis nie wymaga tokenu użytkownika. Compose nie publikuje jego portu na hoście.
- Wiadomości mają wyłącznie format plaintext. Dobór szablonów nie jest zaimplementowany.

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
  "text": "Zgłoszenie zostało przyjęte."
}
```

| Pole | Wymagania |
| --- | --- |
| `to` | jeden poprawny adres email, wymagany także w trybie mock |
| `subject` | od 1 do 255 znaków, bez znaków nowej linii |
| `text` | niepusta treść plaintext |

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
| 422 | niepoprawny adres, temat lub treść, brak wymaganych pól albo dodatkowe pola |
| 503 | brak danych SMTP, flaga mock inna niż `true` lub `false`, brak lub błędny adres testowy przy włączonym mocku |
| 502 | błąd połączenia, TLS, logowania lub wysyłki SMTP |

Błędy 502 i 503 mają format `{"detail": "..."}`. Odpowiedź 422 zawiera listę błędów walidacji.
