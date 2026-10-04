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
| `SMTP_MOCK` | wymagane `true` przez cały hackathon, także na prodzie; inne wartości blokują wysyłkę |
| `SMTP_MOCK_DESTINATION` | jedyny adres testowy, zawsze wymagany |
| `UPLOAD_DIR` | katalog zdjęć API; Compose ustawia `/app/uploads`, lokalnie ścieżka względna zaczyna się w `apps/api` |

Przykład konfiguracji testowej:

```dotenv
NOTIFY_PORT=8001
SMTP_USER=replace_me@gmail.com
SMTP_PASSWORD=replace_me_with_a_gmail_app_password
SMTP_MOCK=true
SMTP_MOCK_DESTINATION=team@example.com
```

W `.env.example` mock jest włączony. Uzupełnij rzeczywisty adres testowy i dane logowania wyłącznie w ignorowanym `.env`.

To obowiązkowa zasada demonstracyjna hackathonu dla każdego środowiska. Główne API automatycznie zleca mail dla nowej sprawy, bez pobierania adresu instytucji, i stosuje limit `SMTP_USER_LIMIT` z `.env` (domyślnie 50 prób na użytkownika w 24 godziny). Kolejkę i statusy opisuje [kontrakt integracji](../../api/docs/visualizations.md).

## Wdrożenie

1. Uzupełnij `.env` w `DEPLOY_DIR` na serwerze. Plik Compose trafia tam przy każdym wdrożeniu jako `docker-compose.yml`.
2. Uruchom `[1] Deploy` dla usługi `notify` i wybranego środowiska. Push do `main` wdraża zmiany w `apps/notify/` na `dev`; `[2] Release` wdraża także `notify` na `prod`.
3. Backend w tym projekcie Compose wywołuje `http://notify:<NOTIFY_PORT>/send`. Przy wartości z przykładu jest to `http://notify:8001/send`.

Port pozostaje wewnętrzny. `task api` uruchamia backend na hoście, więc nie korzysta z adresu DNS `notify` w sieci Compose.

Compose montuje `api_uploads` w `notify` pod `/app/uploads` tylko do odczytu. API nadal zapisuje tam zdjęcia. Po zmianie szablonu Compose wdróż `api` i `notify` ponownie, aby wysyłka załączników widziała te same pliki. Backend przekazuje `photos` i `location` zgodnie z [kontraktem HTTP](api.md).

Po zmianie ustawień SMTP w `.env` odtwórz `api` i `notify` z katalogu `DEPLOY_DIR`. Obie usługi wymagają `SMTP_MOCK=true` i poprawnego `SMTP_MOCK_DESTINATION`:

```sh
docker compose up -d --force-recreate api notify
```

Błędna konfiguracja po stronie API pozostawia mail w kolejce z kodem `smtp_configuration`; worker sprawdza ją ponownie po minucie. Zlecenia zakończone jako `failed` lub `unknown` nie są automatycznie ponawiane. Sama zmiana `.env` ani restart usług nie wysyłają ich ponownie.
