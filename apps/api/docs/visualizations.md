# Wizualizacje i wysyłka testowa

Główne API obsługuje użytkowników, limity, kolejkę oraz zapis obrazów. `gemini` generuje obrazy, a `notify` wysyła mail na adres testowy. Frontend korzysta wyłącznie z głównego API. Powiadomienia i przyciski frontendu nie są częścią tej integracji.

## Konfiguracja

Wartości pochodzą z głównego `.env`. Domyślne ustawienia dokumentuje `.env.example`; lokalny plik nie jest nadpisywany. Po zmianie konfiguracji uruchom API ponownie.

| Zmienna | Domyślnie | Znaczenie |
| --- | --- | --- |
| `GEMINI_USER_LIMIT` | `10` | próby generacji na użytkownika w ruchomym oknie |
| `SMTP_USER_LIMIT` | `50` | próby wywołania konektora SMTP na użytkownika w tym samym oknie |
| `RATE_LIMIT_WINDOW_SECONDS` | `86400` | długość okna limitów w sekundach |
| `VISUALIZATION_DRAFT_TTL_DAYS` | `7` | ważność nieopublikowanego formularza od jego utworzenia |
| `GEMINI_URL` | `http://127.0.0.1:8002` | lokalny adres konektora obrazów |
| `NOTIFY_URL` | `http://127.0.0.1:8001` | lokalny adres konektora SMTP |
| `SMTP_MOCK` | wymagane `true` | obowiązkowa zasada demonstracyjna hackathonu, także na prodzie |
| `SMTP_MOCK_DESTINATION` | wymagany adres testowy | jedyny odbiorca maili |

Wartości limitów i czasu przechowywania muszą być dodatnimi liczbami całkowitymi. Compose przekazuje ustawienia z `.env` i ustawia wewnętrzne adresy konektorów. Przy pracy lokalnej uruchom oba serwisy według ich dokumentacji; `task api` uruchamia worker wraz z API.

## Generacja

Wymagany jest bearer token oraz nagłówek `Idempotency-Key` z niepustym kluczem do 200 znaków. Zachowaj ten sam klucz podczas ponawiania żądania sieciowego. Nowa próba generacji, również po błędzie poprzedniej, używa nowego klucza.

Obecny webowy `apiFetch` obsługuje FormData i odpowiedzi blob. Przy integracji trzeba dodać możliwość przekazania `Idempotency-Key` oraz zachowania `Retry-After` i obiektu `detail` w błędzie. API udostępnia `Retry-After` przez CORS.

| Metoda | Ścieżka | Działanie |
| --- | --- | --- |
| POST | `/visualizations` | opis i zdjęcia przed publikacją, multipart |
| POST | `/reports/{report_id}/visualizations` | generacja z zapisanego opisu i oryginalnych zdjęć, bez body |
| GET | `/visualizations/{job_id}` | status zlecenia, dostęp dla jego autora i administratora |
| GET | `/visualizations/{job_id}/file` | zapisany obraz |
| GET | `/reports/{report_id}/visualizations` | publiczna historia udanych obrazów zgłoszenia |
| GET | `/master-reports/{master_id}/visualizations` | publiczna historia obrazów wszystkich zgłoszeń sprawy |

`POST /visualizations` przyjmuje `description`, 1-5 plików `photos` oraz opcjonalne `draft_id` z wcześniejszej odpowiedzi. Kolejne próby z tym `draft_id` dopisują historię tego samego formularza. Każde zlecenie zachowuje własny opis i kopie zdjęć źródłowych. JPEG, PNG i WebP mają limit 10 MB na zdjęcie i 20 MB łącznie. Przy zapisanym zgłoszeniu wymagana jest kategoria `improvement` oraz autor lub administrator.

Odpowiedź `202` zawiera `id`, `draft_id`, `report_id`, `status_url`, `status`, `generated: true`, `url`, `prompt`, `media_type`, `error_code`, `created_at` i `completed_at`. Status to `queued`, `running`, `succeeded` lub `failed`. `url` jest dostępny po zapisaniu obrazu. Odpytuj `status_url`, aby odebrać wynik; backend nie wysyła nowych powiadomień w ramach tego zadania.

Ten sam klucz i dane zwracają istniejące zlecenie bez zużycia kolejnej próby. Zmienione dane z tym samym kluczem zwracają `409`. Drugie aktywne zlecenie użytkownika również zwraca `409`, z identyfikatorem istniejącego zadania. Limit prób jest wspólny dla formularzy i zgłoszeń; przekroczenie zwraca `429` z `Retry-After`. Nieudane przyjęte zlecenia liczą się do limitu, a odrzucone żądania nie. Usunięcie zgłoszenia nie zeruje licznika.

Listy historii zwracają `items`, `total`, `limit` i `offset`. Domyślny limit to 50, maksymalny 200. Pierwszy wynik jest najnowszą udaną wizualizacją. Poprzednie udane obrazy pozostają dostępne; nieudana generacja nie zmienia bieżącego wyniku. Obrazy są oddzielone od oryginalnych `report_photos` i nie zmniejszają ich limitu.

## Publikacja i przechowanie

`POST /reports` przyjmuje dodatkowe pole multipart `visualization_draft_id`. Musi ono wskazywać własny, niewygasły i jeszcze nieopublikowany formularz, a zgłoszenie musi mieć kategorię `improvement`. Publikacja wiąże wszystkie jego obrazy i zlecenia ze zgłoszeniem, także generację w toku. Jeśli nie prześlesz `photos`, API kopiuje oryginalne zdjęcia z ostatniego zlecenia formularza do zdjęć zgłoszenia.

Robocze pliki wymagają tokenu ich autora lub administratora. W przeglądarce pobierz roboczy `url` przez `fetch` z nagłówkiem `Authorization`, a potem wyświetl blob przez `URL.createObjectURL`; samo `<img src>` nie dołącza tokenu. Po publikacji pliki obrazów są publiczne, tak jak zdjęcia zgłoszeń. Formularze wygasają po skonfigurowanym czasie; worker usuwa ich pliki i zachowuje metadane prób do limitowania. Opublikowane źródła i historia pozostają do usunięcia zgłoszenia. Odczyt wygasłego wyniku zwraca `410`.

## Automatyczny mail

Publikacja tworząca nowy `master_report` zapisuje jedno zlecenie maila w tej samej transakcji. Dołączenie do istniejącej sprawy, przenoszenie zgłoszeń oraz regeneracja obrazu nie tworzą maila. Nie ma wysyłek wstecz dla spraw utworzonych przed wdrożeniem.

Jeśli publikowany formularz ma trwającą generację, mail czeka na tę próbę. Po jej sukcesie dołącza obraz, po błędzie wysyła oryginalne zdjęcia. Maksymalnie dołącza pięć oryginałów i jedną wizualizację; obowiązuje limit załączników konektora 20 MB łącznie. Późniejsze generacje nie ponawiają wysyłki.

Adres instytucji nie jest pobierany. API i `notify` wymagają `SMTP_MOCK=true` i poprawnego `SMTP_MOCK_DESTINATION`; brak konfiguracji blokuje wysyłkę. Jest to rzeczywisty mail przez Gmail do skrzynki testowej, także w środowisku prod.

`GET /master-reports/{master_id}/delivery` udostępnia autorowi zlecenia i administratorowi status `queued`, `running`, `sent`, `failed` lub `unknown`, pole `mock: true`, kod błędu oraz czasy wykonania. Brak zlecenia zwraca `404`. Limit SMTP pozostawia mail w kolejce z `next_attempt_at` i kodem `smtp_limit`; błędna konfiguracja daje `smtp_configuration` i jest ponownie sprawdzana po minucie.

`sent` oznacza przyjęcie maila przez SMTP, nie potwierdzenie dostarczenia do skrzynki. Po takim sukcesie backend zmienia wyłącznie `created -> reported`. Nie cofa `inprogress` ani `finished`. Błąd nie usuwa zgłoszenia i nie zmienia jego statusu.

## Worker i restart

Worker działa w cyklu życia API, z osobnymi pętlami dla generacji i SMTP. PostgreSQL przechowuje kolejkę, atomowe rezerwacje limitów i dzierżawy. Globalnie wykonywane jest najwyżej jedno zlecenie każdego rodzaju. Wywołania sieciowe odbywają się poza transakcjami; timeout wynosi 300 sekund dla Gemini i 60 sekund dla `notify`. Dzierżawa trwa 60 sekund i jest odnawiana co 10 sekund.

Po restarcie zadania oczekujące są kontynuowane. Wygasła dzierżawa generacji daje `failed`, a wysyłki `unknown`. Niepewne ani zakończone błędem wywołania SMTP nie są automatycznie powtarzane. Sam SMTP nie gwarantuje dokładnie jednej dostawy przy utracie potwierdzenia. Nowe generacje po błędzie wymagają świadomego żądania z nowym kluczem.

Migracja musi zostać zastosowana przed restartem API. Workflow wdrożeniowy zachowuje tę kolejność. Testy zastępują Google i SMTP i nie wykonują płatnych generacji ani rzeczywistych wysyłek.
