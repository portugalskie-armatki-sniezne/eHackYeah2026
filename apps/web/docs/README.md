# Dokumentacja frontendu (apps/web)

Aplikacja kliencka SPA dla platformy **pomożeMy**, zbudowana w technologii React 18, TypeScript oraz Vite, z mapą opartą o MapLibre GL JS.

## Spis treści

- [Architektura i technologie](#architektura-i-technologie)
- [Główne funkcjonalności](#główne-funkcjonalności)
- [Struktura kodu](#struktura-kodu)
- [Konfiguracja i zmienne środowiskowe](#konfiguracja-i-zmienne-środowiskowe)
- [Uruchomienie i skrypty](#uruchomienie-i-skrypty)

## Architektura i technologie

- **Framework**: React 18 z TypeScriptem i bundlerem Vite.
- **Mapa i geolokalizacja**: MapLibre GL JS ze stylami Carto Positron oraz warstwami klastrowania.
- **Komunikacja z backendem**: Moduł `src/api/client.ts` (`apiFetch`), obsługujący nagłówki `Authorization: Bearer <token>`, proxy deweloperskie w Vite oraz bezpośrednie połączenie z API na serwerze.
- **Sesja użytkownika**: Przechowywanie tokena JWT w `localStorage` z automatycznym wylogowaniem po otrzymaniu 401.
- **Routing**: Lekki routing oparty na hashu URL (`useHashRoute.ts`: `#main`, `#about`, `#projects`), niewymagający specjalnej konfiguracji serwera HTTP pod kątem fallbacku ścieżek.
- **Wielojęzyczność (i18n)**: Wbudowany moduł tłumaczeń (`src/i18n/`) obsługujący dynamiczne przełączanie języka między polskim a angielskim.

## Główne funkcjonalności

### 1. Interaktywna mapa i klastrowanie
- **Przeglądanie zgłoszeń**: Zgłoszenia główne (`master_reports`) pobierane z API są prezentowane na mapie w postaci klastrów z licznikami (`ReportClusters.tsx`) lub indywidualnych znaczników (`EventMarkers.tsx`).
- **Nawigacja i centrowanie GPS**: Pasek narzędzi mapy (`MapToolbar.tsx`) z przyciskiem centrowania widoku na bieżącej pozycji geolokalizacyjnej użytkownika (`UserPosition.tsx`, `useUserPosition.ts`).
- **Kursor dodawania zgłoszenia**: Tryb wyboru lokalizacji na mapie z dedykowanym celownikiem (`MapCursor.tsx`), umożliwiający precyzyjne wskazanie punktu problemu lub inicjatywy.
- **Optymalizacja kafelków**: Mechanizm wstępnego podgrzewania pamięci podręcznej kafelków mapy (`mapPrewarm.ts`) i wydzielony web worker dla MapLibre.

### 2. Zgłaszanie problemów i inicjatyw
- **Formularz zgłoszeniowy (`PinDialog.tsx`)**: Otwiera się po zatwierdzeniu punktu na mapie.
- **Kategorie zgłoszeń**: Umożliwia rejestrację awarii i problemów komunalnych (`issue`) lub propozycji inicjatyw obywatelskich (`improvement`).
- **Załączanie zdjęć**: Obsługa przeciągania lub wyboru do 5 zdjęć (JPEG, PNG, WebP) o rozmiarze do 10 MB, z podglądem miniatur przed wysłaniem.
- **Integracja z API**: Zgłoszenie tworzone jest przez `POST /reports`, co powoduje automatyczne dopasowanie do master reportu, identyfikację gminy i powiatu przez GUGiK ULDK oraz wyznaczenie właściwej jednostki administracyjnej.

### 3. Karta zgłoszenia i dyskusja obywatelska
- **Szczegóły sprawy (`MarkerDialog.tsx`)**: Wyświetla tytuł, opis, galerię zdjęć, datę, status realizacji z kolorowym oznaczeniem (`StatusBadge.tsx`) oraz dane jednostki odpowiedzialnej.
- **Wątek komentarzy**: Mieszkańcy mogą przeglądać i dodawać komentarze pod sprawą, prowadząc publiczną dyskusję.
- **Dedykowana karta innowacji ROPS**: Jeśli do sprawy pasuje gotowa innowacja społeczna ROPS, w oknie zgłoszenia wyświetlana jest karta z rekomendowanym rozwiązaniem oraz linkami do materiałów źródłowych (z automatycznym wykrywaniem i czyszczeniem adresów URL).

### 4. Katalog innowacji społecznych ROPS
- **Katalog dobrych praktyk (`ProjectsCatalog.tsx`)**: Dostępny pod ścieżką `#projects`, prezentuje zbiór przetestowanych innowacji społecznych Regionalnego Ośrodka Polityki Społecznej.
- **Wyszukiwanie i filtry**: Filtrowanie po kategoriach (np. seniorzy, dostępność, młodzież) oraz pole wyszukiwania przeszukujące bazę innowacji z użyciem backendowego silnika semantycznego i stemmingu.
- **Podgląd innowacji**: Karty projektów zawierają cele, grupy docelowe, autorów, podsumowania oraz linki do pełnych opracowań.

### 5. Uwierzytelnianie i profil mieszkańca
- **Logowanie i rejestracja (`AuthDialog.tsx`)**: Rejestracja nowego konta lub logowanie tradycyjne (hasło i email/telefon).
- **Logowanie przez Google SSO (`GoogleButton.tsx`)**: Integracja z Google Identity Services umożliwiająca bezpieczne logowanie jednym kliknięciem.
- **Zarządzanie kontem (`ProfileDialog.tsx`, `SignOutDialog.tsx`)**: Podgląd danych użytkownika, roli w systemie oraz bezpieczne wylogowanie z usunięciem tokena sesji.

### 6. Wielojęzyczność (i18n)
- **Obsługa języków**: Pełne tłumaczenie interfejsu na język polski i angielski (`src/i18n/messages.ts`).
- **Przełącznik w nagłówku (`LanguageToggle.tsx`)**: Płynna zmiana języka bez przeładowania aplikacji, z zapamiętywaniem wyboru w `localStorage`.

### 7. Responsywny interfejs i dostępność
- **Nawigacja mobilna i desktopowa (`Navbar.tsx`)**: Elastyczny pasek nawigacyjny z logo, linkami do katalogu innowacji i strony "O projekcie" oraz menu konta użytkownika.
- **Dostosowanie do smartfonów**: Wyśrodkowane dialogi, czytelne przyciski o odpowiedniej powierzchni dotykowej i obsługa gestów mapy na urządzeniach dotykowych.
- **Strona "O projekcie" (`About.tsx`)**: Dedykowany widok przybliżający cele platformy, rolę sztucznej inteligencji w łączeniu spraw oraz współpracę z instytucjami.

## Struktura kodu

```text
apps/web/src/
├── api/
│   ├── auth.ts                  # zapytania autoryzacyjne (login, google, rejestracja)
│   ├── client.ts                # bazowy klient HTTP z obsługą JWT
│   ├── letters.ts               # obsługa pism urzędowych
│   ├── projects.ts              # API innowacji społecznych ROPS (katalog, kategorie, search)
│   ├── reports.ts               # pobieranie masterów, wysyłanie zgłoszeń i komentarzy
│   └── session.ts               # zarządzanie tokenem sesji w localStorage
├── components/
│   ├── About.tsx                # widok informacyjny o projekcie (#about)
│   ├── AuthDialog.tsx           # okno modalne logowania i rejestracji
│   ├── BrandMark.tsx            # logotyp i identyfikacja wizualna
│   ├── EventMarkers.tsx         # znaczniki pojedynczych zgłoszeń na mapie
│   ├── GoogleButton.tsx         # przycisk logowania Google SSO
│   ├── LanguageToggle.tsx       # przełącznik języków PL / EN
│   ├── Map.tsx                  # główny komponent mapy MapLibre GL
│   ├── MapCursor.tsx            # celownik trybu dodawania punktu
│   ├── MapToolbar.tsx           # przyciski kontrolne mapy (lokalizacja, warstwy)
│   ├── MarkerDialog.tsx         # szczegóły zgłoszenia, dyskusja i karta ROPS
│   ├── Navbar.tsx               # górny pasek nawigacji
│   ├── PinDialog.tsx            # formularz dodawania nowego zgłoszenia
│   ├── ProfileDialog.tsx        # okno profilu zalogowanego użytkownika
│   ├── ProjectsCatalog.tsx      # przeglądarka i wyszukiwarka innowacji ROPS (#projects)
│   ├── ReportClusters.tsx       # klastrowanie zgłoszeń na mapie
│   ├── SignOutDialog.tsx        # potwierdzenie wylogowania
│   ├── StatusBadge.tsx          # plakietka statusu zgłoszenia
│   ├── useHashRoute.ts          # hook routingu opartego o hash
│   ├── UserPosition.tsx         # wskaźnik lokalizacji GPS użytkownika na mapie
│   └── useUserPosition.ts       # hook śledzenia pozycji geolokalizacyjnej
├── i18n/
│   ├── locale.ts                # zarządzanie wybranym językiem i stanem
│   └── messages.ts              # słowniki tłumaczeń dla języka polskiego i angielskiego
├── App.tsx                      # główny komponent integrujący widoki i dialogi
├── main.tsx                     # punkt wejściowy aplikacji React
└── index.css                    # globalne style i motyw graficzny
```

## Konfiguracja i zmienne środowiskowe

Konfiguracja aplikacji webowej opiera się na zmiennych środowiskowych Vite:

| Zmienna | Opis | Domyślna wartość w dev |
| --- | --- | --- |
| `VITE_API_URL` | Adres URL backendu REST API wdrożonego na serwerze produkcyjnym lub deweloperskim. | puste (zapytania trafiają do `/api` proxy) |
| `VITE_GOOGLE_CLIENT_ID` | Identyfikator klienta OAuth 2.0 dla logowania przez Google SSO. | opcjonalny |
| `API_PROXY_TARGET` | Cel proxy deweloperskiego w `vite.config.ts`. | `http://127.0.0.1:8000` |

## Uruchomienie i skrypty

Wszystkie komendy można uruchamiać z katalogu `apps/web` za pomocą `bun`:

```sh
cd apps/web

# Uruchomienie lokalnego serwera deweloperskiego z Vite
bun run dev

# Sprawdzanie typów TypeScript
bun run typecheck

# Budowanie wersji produkcyjnej do katalogu dist/
bun run build

# Lokalny podgląd zbudowanej wersji produkcyjnej
bun run preview
```

Z głównego katalogu repozytorium można także skorzystać z Taskfile:
- `task web` - uruchamia serwer deweloperski frontendu
- `task fe:lint` - uruchamia sprawdzanie kodu za pomocą ESLint i Prettier
- `task fe:lint:fix` - automatycznie formatuje i poprawia błędy w kodzie frontendu
