# Web Workspace (apps/web)

Frontend platformy **pomożeMy** napisany w React 18, TypeScript i Vite.

Pełny opis modułów, architektury i zrealizowanych funkcjonalności znajduje się w [dokumentacji frontendu](docs/README.md).

## Szybki start

```sh
# instalacja zależności (z poziomu katalogu głównego repozytorium)
task setup

# uruchomienie serwera deweloperskiego
task web
```

Aplikacja jest domyślnie dostępna pod adresem wskazanym przez Vite (zwykle `http://localhost:5173`).
Zapytania do API są przekierowywane na `http://127.0.0.1:8000`.

## Polecenia

```sh
cd apps/web
bun run dev          # uruchomienie serwera deweloperskiego
bun run typecheck    # sprawdzanie typów TypeScript
bun run build        # budowanie produkcyjne do apps/web/dist
bun run preview      # podgląd zbudowanej aplikacji
```
