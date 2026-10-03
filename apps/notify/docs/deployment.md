# Konfiguracja i wdrożenie powiadomień

Serwis jest wdrażany z opublikowanego obrazu przez `docker-compose.app.yaml`, zgodnie z [instrukcją wdrożenia](../../../README_pl.md#automatyczne-wdrożenie). Konfiguracja trafia do `.env` w `DEPLOY_DIR`.

## Gmail

1. Na [koncie Google](https://myaccount.google.com/) wybierz **Zabezpieczenia i logowanie** i włącz **weryfikację dwuetapową**.
2. Otwórz [Hasła do aplikacji](https://myaccount.google.com/apppasswords), wpisz nazwę `notify` i kliknij **Utwórz**.
3. Ustaw `SMTP_USER` na pełny adres Gmaila, a wygenerowane 16-znakowe hasło bez spacji zapisz jako `SMTP_PASSWORD` w `.env`.

Nie jest potrzebna konfiguracja Google Cloud Console. Szczegóły i ograniczenia kont opisuje [pomoc Google](https://support.google.com/accounts/answer/185833?hl=pl).

## Zmienne środowiskowe

| Zmienna | Znaczenie |
| --- | --- |
| `NOTIFY_IMAGE_TAG` | tag obrazu, domyślnie `dev`; workflow ustawia tag wdrażanego commita |
| `NOTIFY_PORT` | wewnętrzny port HTTP, domyślnie `8000`; `.env.example` ustawia `8001` |
| `SMTP_USER` | adres Gmaila używany do logowania i jako nadawca |
| `SMTP_PASSWORD` | hasło aplikacji Gmail |
| `SMTP_MOCK` | `true` przekierowuje wszystkie maile na adres testowy, `false` używa odbiorcy z żądania |
| `SMTP_MOCK_DESTINATION` | jeden adres testowy, wymagany przy `SMTP_MOCK=true` |

Przykład konfiguracji testowej:

```dotenv
NOTIFY_PORT=8001
SMTP_USER=replace_me@gmail.com
SMTP_PASSWORD=replace_me_with_a_gmail_app_password
SMTP_MOCK=true
SMTP_MOCK_DESTINATION=team@example.com
```

W `.env.example` mock jest włączony. Uzupełnij rzeczywisty adres testowy i dane logowania wyłącznie w ignorowanym `.env`.

## Wdrożenie

1. Zaktualizuj na serwerze kopię `docker-compose.app.yaml` w `DEPLOY_DIR/docker-compose.yaml` i uzupełnij `.env` obok niej.
2. Uruchom `[1] Deploy` dla usługi `notify` i wybranego środowiska. Push do `main` wdraża zmiany w `apps/notify/` na `dev`; `[2] Release` wdraża także `notify` na `prod`.
3. Backend w tym projekcie Compose wywołuje `http://notify:<NOTIFY_PORT>/send`. Przy wartości z przykładu jest to `http://notify:8001/send`.

Port pozostaje wewnętrzny. `task api` uruchamia backend na hoście, więc nie korzysta z adresu DNS `notify` w sieci Compose.

Po zmianie `.env` odtwórz kontener z katalogu `DEPLOY_DIR`:

```sh
docker compose up -d notify
```
