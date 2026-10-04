# eHackYeah2026 - pomożeMy

**pomożeMy** to **wspólna platforma** do **zgłaszania lokalnych problemów**, **proponowania inicjatyw obywatelskich** i **śledzenia ich postępów**.
Ma ułatwić kontakt z instytucjami publicznymi. Wykorzystuje AI (deterministyczne klasyfikatory i modele generatywne) do ustalenia, która instytucja odpowiada za dane zgłoszenie, na podstawie bazy publicznie dostępnych informacji o instytucjach. Do zgłoszenia można dołączyć lokalizację GPS i zdjęcia pokazujące problem.

**[ENGLISH README | README PO ANGIELSKU](README.md)**

![pomożeMy - zmiana miasta bez nadmiernej biurokracji](docs/teaser-pl.png)

## Struktura repozytorium

```text
eHackYeah2026/
├── apps/
│   ├── web/                         # frontend
│   ├── api/                         # backend
│   ├── notify/                      # wewnętrzny serwis wysyłki maili
│   └── gemini/                      # wewnętrzny konektor wizualizacji inicjatyw
├── db/
│   ├── migrations/                  # migracje SQL dla dbmate
│   └── seeds/                       # dane referencyjne i arkusz kontaktów
├── docs/
│   ├── teaser-en.png                # angielski teaser projektu
│   └── teaser-pl.png                # polski teaser projektu
├── tooling/
│   └── seed/                        # importer XLS, importer danych demo i ich obraz Dockera
├── tests/
│   ├── e2e/                         # scenariusze obejmujące całą aplikację
│   └── fixtures/                    # wspólne przykłady do testów
├── docker-compose.yaml              # baza danych, migracje i import danych
├── docker-compose.app.yaml          # kontenery API, web, notify i gemini z opublikowanych obrazów
├── Taskfile.yml                     # polecenia deweloperskie
├── mise.toml                        # ustalone wersje Bun, Task i uv
├── setup-dev-env.sh                 # instalacja mise, narzędzi i zależności
├── package.json                     # obszary robocze Bun
├── bun.lock
├── .env.example
├── README.md                        # dokumentacja po angielsku
├── README_pl.md                     # dokumentacja po polsku
├── AGENTS.md
└── TESTING.md
```

## Dostęp do projektu

Projekt jest dostępny pod adresem [hackyeah.jakubowskii.pl/#main](https://hackyeah.jakubowskii.pl/#main), przynajmniej podczas hackathonu HackYeah 2026.

## Wdrożenie

### Wymagania

1. Zainstaluj `Node.js 22.12` lub nowszy oraz `Docker` z `Compose`. Uruchom Dockera.
2. Uruchom skrypt z katalogu głównego repozytorium. Instaluje on [mise](https://mise.jdx.dev), wersje Bun, Task i uv określone w `mise.toml`, a następnie uruchamia `task setup`, aby zainstalować zależności projektu. Uruchom ponownie powłokę, jeśli skrypt o to poprosi. Na Windows zainstaluj mise ręcznie, a potem uruchom `mise install` i `task setup`.

   ```sh
   ./setup-dev-env.sh
   ```

   > `task setup` tworzy `.env` z `.env.example`, jeśli plik nie istnieje. Zachowuje istniejący plik.
   > `task setup`, `task web`, `task db` i `task api` włączają hook pre-commit z `.githooks`, który uruchamia `task fe:lint` albo `task be:lint`, gdy commit zmienia `apps/web` lub `apps/api`.

3. Sprawdź ustawienia bazy danych i uzupełnij wartości w `.env`. Przed uruchomieniem API ustaw losowy `JWT_SECRET`. Polecenie do jego wygenerowania znajdziesz w `.env.example`.

### Uruchamianie

> Wszystkie polecenia uruchamiaj z katalogu głównego repozytorium, z aktywnym mise w powłoce. W przeciwnym razie dodaj przed nimi `mise exec --`.

1. `task db`: uruchom samą bazę danych, migracje i import danych.
2. `task api`: uruchom bazę danych, migracje i import danych, a następnie API.
3. `task web`: uruchom frontend.

> Uruchamiaj `task web` i `task api` w osobnych terminalach. API jest dostępne pod adresem <http://127.0.0.1:8000>, a Vite wyświetla adres frontendu. Ctrl+C zatrzymuje aplikację w danym terminalu; PostgreSQL nadal działa pod adresem `127.0.0.1:POSTGRES_PORT`.

> Przy uruchamianiu bazy importowany jest arkusz urzędów JST, przejrzane zbiory jednostek usługowych i ich siedzib oraz biblioteka innowacji społecznych ROPS pokazywana na stronie inicjatyw. `task db` kończy działanie po zakończeniu importu.

> Na potrzeby prezentacji `docker compose run --rm mock-seeder` podmienia przykładowych użytkowników, zgłoszenia, zdjęcia i dyskusje w Krakowie. Szczegóły i konta demo opisuje sekcja [mock demo data](TESTING.md#mock-demo-data).

#### Aplikacja API

- Konfiguracja uruchamia `uv sync --extra inference`, instaluje zależności w `apps/api/.venv` i pobiera przypięte wersje Laya oraz tłumacza polsko-angielskiego do `apps/api/models` (około 1,1 GB, poza Gitem). Pierwsze uruchomienie wymaga Gita i internetu. Kolejne korzystają z kompletnych pobranych modeli. uv pobiera Pythona 3.10 lub nowszego, jeśli go brakuje.
- Dokumentacja API jest dostępna pod adresem <http://127.0.0.1:8000/docs>. `GET /health` sprawdza działanie aplikacji bez odpytywania PostgreSQL.
- Zapis zgłoszenia lub zmiana jego współrzędnych wymaga dostępu do `https://uldk.gugik.gov.pl/`, aby ustalić gminę i powiat w Małopolsce. Jeśli usługa jest niedostępna, API zwraca błąd i użytkownik może ponowić próbę.
- `POST /inference` wymaga zalogowania i przyjmuje tekst, pytania klasyfikacyjne oraz opcjonalne zdjęcie. `POST /inference/service-entity` wybiera typ jednostki usługowej na podstawie tytułu, opisu i opcjonalnego zdjęcia. Ścieżki modeli w `.env.example` włączają lokalną analizę. Do istniejącego `.env` dodaj `LAYA_MODEL_PATH=models/laya-vision` i `TRANSLATION_MODEL_PATH=models/opus-mt-pl-en`; konfiguracja zachowuje istniejące wartości. Zobacz [konfigurację modeli i dostawców](apps/api/docs/inference.md).
- Zmiany w `apps/api/app` automatycznie przeładowują API.
- Uruchom `task be:lint`, aby sprawdzić API za pomocą Ruff, lub `task be:lint:fix`, aby zastosować poprawki i formatowanie.

#### Konektor Gemini

`apps/gemini` to wewnętrzny serwis generowania wizualizacji zgłoszeń `improvement`. Gemini Flash przygotowuje prompt z opisu i zdjęć, a Nano Banana generuje jeden obraz. Główne API obsługuje uwierzytelnione żądania przed publikacją i po niej, limity użytkownika, zadania w tle oraz trwałą historię obrazów. Wysyła też jeden mail testowy dla każdej nowej sprawy, zawsze na skonfigurowany adres testowy, także na prodzie przez czas hackathonu. Szczegóły opisują [kontrakt integracji backendu](apps/api/docs/visualizations.md) i [dokumentacja konektora Gemini](apps/gemini/docs/api.md).

#### Aplikacja web

1. Edytuj `apps/web/src/App.tsx`, aby zmienić interfejs, i `apps/web/src/index.css`, aby zmienić style. `task fe:lint` uruchamia ESLint i Prettier, a `task fe:lint:fix` stosuje poprawki i formatowanie.
2. Uruchom sprawdzanie typów i budowanie z katalogu frontendu:

   ```sh
   cd apps/web
   bun run typecheck
   bun run build
   bun run preview
   ```

3. Gotowy build trafia do `apps/web/dist`.
4. Aplikacja łączy się z API pod adresem `VITE_API_URL` z głównego `.env`. Bez tej zmiennej zapytania trafiają pod `/api`, skąd serwer deweloperski Vite przekazuje je do `http://127.0.0.1:8000` albo do `API_PROXY_TARGET`. Dodanie zgłoszenia wymaga zalogowania.

Strona powiadomień czyta `GET /notifications` przez [`notifications.ts`](apps/web/src/api/notifications.ts), który prowadzi też licznik nieodczytanych w pasku nawigacji. Każde powiadomienie ma przy sobie przyciski działania: otwarcie sprawy, oznaczenie jako odczytane, usunięcie, a dla zaproponowanego zdjęcia jego przyjęcie albo odrzucenie przez [`photoProposals.ts`](apps/web/src/api/photoProposals.ts). „Otwórz zgłoszenie” wskazuje w adresie jedno zgłoszenie główne, jako `#map/<id zgłoszenia>`, a mapa otwiera arkusz tej pinezki.

Sprawa bez zdjęcia pokazuje sposób, by je zaproponować, zarówno w arkuszu na mapie, jak i na stronie zgłoszeń. Dopóki autor sprawy go nie przyjmie, zaproponowane zdjęcie zastępuje jej obrazek ze znakiem zapytania: na pinezce i w obu arkuszach.

### Automatyczne wdrożenie

1. W środowiskach GitHub `dev` i `prod` ustaw `VITE_API_URL` (adres backendu zapisany w buildzie frontendu), `VITE_GOOGLE_CLIENT_ID` (identyfikator klienta OAuth do logowania przez Google, ten sam co `GOOGLE_CLIENT_ID` w `.env` środowiska) i `DEPLOY_DIR` (katalog wdrożenia na serwerze).
2. Utwórz na serwerze katalog `DEPLOY_DIR` i umieść w nim `.env` danego środowiska. Ustaw `GOOGLE_CLOUD_PROJECT` i `GOOGLE_CLOUD_LOCATION`, skopiuj plik JSON konta usługi na serwer wdrożeniowy i ustaw `GEMINI_CREDENTIALS_FILE` na jego ścieżkę względem `docker-compose.yml` (domyślnie `./project-key.json`). Ustaw `GEMINI_UID` i `GEMINI_GID` na numeryczne wyniki poleceń `id -u` i `id -g` dla konta będącego właścicielem pliku, aby nieuprzywilejowany kontener mógł go odczytać. Chroń ten plik i nie dodawaj go do Gita. Baza działa w osobnym projekcie Compose; `DB_NETWORK` wskazuje jej sieć (domyślnie `ehackyeah2026_default`), a `POSTGRES_HOST` jej host (domyślnie `db`). Plik `.env` musi być poprawny zarówno dla Compose, jak i powłoki, a dane logowania do bazy muszą nadawać się do użycia w URL. Skonfiguruj Gmaila i wysyłkę testową dla `notify` według [instrukcji konfiguracji maili](apps/notify/docs/deployment.md).
3. W GitHub Actions uruchom `[1] Deploy`, aby wdrożyć `web`, `api`, `notify`, `gemini` albo wszystkie naraz (`all`) na `dev` albo `prod`. Push do `main` wdraża zmienione usługi na `dev`; zmiany w `db/migrations` wdrażają `api`. Workflow buduje cztery obrazy usług i publikuje je w repozytoriach `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-web`, `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-api`, `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-notify` i `ghcr.io/portugalskie-armatki-sniezne/ehackyeah2026-gemini` z tagami środowiska oraz `<environment>-<commit SHA>`.
4. Runner na serwerze kopiuje `docker-compose.app.yaml` do `DEPLOY_DIR/docker-compose.yml`, aktualizuje `*_IMAGE_TAG` wybranych usług w `DEPLOY_DIR/.env`, pobiera obrazy, stosuje migracje przed restartem `api` i uruchamia ponownie wybrane usługi. Jeśli migracja się nie powiedzie, poprzedni kontener API działa dalej. Wdrożenie nie importuje danych referencyjnych. Nie używaj runnerów na własnym serwerze w workflow uruchamianych przez pull requesty.
5. Po wdrożeniu `api` uruchom ręcznie `[4] Seed` dla `dev` lub `prod`, aby zaimportować dane z `db/seeds`. Import czeka na zakończenie wdrożeń w tym samym środowisku. Ponowne uruchomienie zachowuje identyfikatory i nie tworzy duplikatów; dane źródłowe nadpisują ręczne zmiany, a rekordy nieobecne w plikach pozostają w bazie.
6. Uruchom ręcznie `[2] Release`, aby wdrożyć wszystkie cztery usługi na `prod`, a następnie utworzyć tag Git i wydanie na GitHubie. Wersje zawierają datę UTC i licznik wydań z danego dnia, np. `v2026.10.03-1`.
7. Szablon Compose przechowuje zdjęcia zgłoszeń w `/app/uploads` na wolumenie `api_uploads`, dzięki czemu pozostają dostępne po wdrożeniu. `notify` i `gemini` montują ten sam wolumen tylko do odczytu.

Obraz API zawiera biblioteki do klasyfikacji na CPU oraz przypięte modele Laya i tłumacza PL → EN. GitHub Actions pobiera modele do warstwy obrazu zachowywanej w cache i sprawdza rzeczywistą klasyfikację polskiego tekstu z obrazem i bez niego podczas budowania, bez dostępu do sieci. Compose włącza je na dev i prod bez dodatkowej konfiguracji serwerów. API powtarza próbę tekstową przy starcie i zgłasza gotowość pod `/ready` dopiero po jej powodzeniu. Wdrożenie czeka na gotowość do 10 minut; błąd modelu oznacza błąd wdrożenia. Zobacz [wdrożenie klasyfikacji](apps/api/docs/inference.md#wdrożenie-na-vps).

> `[3] Lint` uruchamia ESLint, Prettier i Ruff dla każdego pull requesta i pusha do `main`, na runnerach GitHuba.

## Wspólne skille agentów

Skille w `.agents/skills/` są wersjonowane razem z projektem. Można korzystać z nich w Codexie z poziomu repozytorium:

| Skill                                      | Przykładowe polecenie                                   | Działanie                                                                                                                            |
| ------------------------------------------ | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| [commit](.agents/skills/commit/SKILL.md)   | `Użyj $commit, aby zatwierdzić przygotowane zmiany.`    | Sprawdza wszystkie zmiany w indeksie, uruchamia odpowiednie kontrole i tworzy commit. Wysyła zmiany tylko na wyraźne polecenie.      |
| [pr](.agents/skills/pr/SKILL.md)           | `Użyj $pr, aby otworzyć pull request dla tego brancha.` | Sprawdza i wysyła commity z brancha, a następnie tworzy lub aktualizuje PR do domyślnej gałęzi repozytorium, chyba że wskazano inną. |
| [babysit](.agents/skills/babysit/SKILL.md) | `Użyj $babysit, aby doprowadzić te zmiany do main.`     | Zatwierdza zmiany, tworzy lub wznawia draft PR, sprawdza je i scala do `main` metodą squash.                                         |

Wszystkie trzy skille wymagają Gita. `pr` i `babysit` wymagają też uwierzytelnionego dostępu do GitHuba przez integrację lub CLI `gh`. Przestrzegają `AGENTS.md` i przyjmują opcjonalne wskazówki dotyczące wiadomości lub odwołania do zgłoszeń. Nie wymagają instalowania osobistych skilli globalnych. Agenci obsługujący pliki skilli mogą też bezpośrednio przeczytać podlinkowane instrukcje `SKILL.md`.

## Model danych

- Zgłoszenia zapisują lokalizację jako PostGIS `geography(Point, 4326)`. Powstają przed klasyfikacją, więc `reports.master_report_id` może być `NULL`. Po klasyfikacji backend tworzy zgłoszenie główne lub łączy zgłoszenie z istniejącym.
- Zgłoszenia główne mają własną treść, wspólny status i odpowiedź oraz opcjonalnie przypisaną instytucję. Komentarze i polubienia dotyczą zgłoszeń głównych.
- Zdjęcia są zapisane w `report_photos`. Każdy rekord zawiera trwały `storage_key`, który wskazuje plik zarządzany przez API lub warstwę przechowywania danych.
- Do zgłoszenia głównego bez zdjęcia każda zalogowana osoba może zdjęcie zaproponować. Propozycja czeka w `master_report_photo_proposals` ze znakiem zapytania, dopóki autor zgłoszenia jej nie przyjmie, co zapisuje zdjęcie jako zdjęcie zgłoszenia, albo nie odrzuci, co usuwa plik.
- `notifications` zapisuje, co zdarzyło się w sprawach, które odbiorca zgłosił, skomentował albo do których zaproponował zdjęcie: przyjęcie sprawy do realizacji, jej zakończenie, aktualizację od urzędu, nowy komentarz oraz zaproponowane zdjęcie wraz z decyzją.
- Arkusz zawiera adresy instytucji, ale nie zawiera współrzędnych ani granic obszarów.
- Nowe zgłoszenia są przyjmowane wyłącznie z Małopolski. Zapisują kody TERYT oraz nazwy gminy i powiatu ustalone ze współrzędnych na podstawie [granic PRG z GUGiK](https://uldk.gugik.gov.pl/opis.html). W starszych zgłoszeniach pola pozostają puste do czasu aktualizacji lokalizacji. Obszar administracyjny nie przesądza o tym, która instytucja odpowiada za problem.

Opis importu danych i sprawdzania bazy znajdziesz w [TESTING.md](TESTING.md).
