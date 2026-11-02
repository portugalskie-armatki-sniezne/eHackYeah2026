# Otwarte dane Krakowa w pomożeMy

## Źródło i pochodzenie

Aplikacja korzysta bezpośrednio z pobieralnego zbioru MSIP [Podział administracyjny - dzielnice](https://msip.krakow.pl/dataset/1483). Właścicielem danych jest Prezydent Miasta Krakowa, Urząd Miasta Krakowa, Wydział Geodezji.

- Paczka źródłowa: [Dzielnice_JSON.zip](https://msip.um.krakow.pl/Dane/Dzielnice_JSON.zip), plik `Dzielnice.geojson`.
- Źródło: Gmina Miejska Kraków, Portal MSIP Obserwatorium (<https://msip.krakow.pl>).
- Warunki wykorzystania: [regulamin MSIP](https://msip.krakow.pl/getPdf?dok_id=228972). Zbiór jest oznaczony jako OpenData i udostępniony do pobrania. Aplikacja wykorzystuje lokalną kopię danych, nie udostępnia miejskiego serwisu mapowego jako własnej usługi.
- Data pobrania: 2026-11-02. Data wygenerowania pliku wskazana w paczce: 2025-12-05 10:00:39. Data pobrania nie oznacza daty aktualizacji granic.
- SHA-256 paczki: `5fca108c88267cb35816d5fa68cda9ca07fa776d2fb9532bfd5ecae076bb2b37`.

Snapshot zawiera wszystkie 18 dzielnic: ich numer, nazwę, pełną nazwę i geometrię granic. Skrypt przelicza współrzędne z EPSG:2178 do WGS 84 (EPSG:4326), w kolejności długość, szerokość geograficzna. Zachowuje wierzchołki, zaokrąglając współrzędne do siedmiu miejsc po przecinku. Nie upraszcza granic.

## Wykorzystanie w aplikacji

1. Formularz usterki lub inicjatywy rozpoznaje dzielnicę na podstawie pozycji pinezki i oficjalnych wielokątów MSIP.
2. Szczegóły zapisanej sprawy pokazują dzielnicę i odnośnik do źródła. Dotyczy to również wcześniejszych zgłoszeń, bo obliczenie korzysta z zapisanej lokalizacji.
3. Mapa pokazuje granice dzielnic. Wybór dzielnicy przybliża jej obszar i filtruje pinezki oraz grupy zgłoszeń. Liczniki oznaczają liczbę spraw głównych, a nie liczbę wszystkich zgłoszeń składowych. Wyniki łączą miejskie granice z danymi zgłaszanymi przez mieszkańców.
4. Przygotowana wiadomość email zawiera współrzędne, rozpoznaną dzielnicę i źródło granic. Opis zapisany przez mieszkańca pozostaje bez zmian.
5. Sekcja „O nas” podaje źródło oraz datę wygenerowania i pobrania pliku.

Punkty poza granicami zbioru nie otrzymują dzielnicy Krakowa. Opcja „Wszystkie lokalizacje” zachowuje widoczność spraw z pozostałej części Małopolski. Na wspólnej granicy wybierana jest dzielnica o niższym numerze. Wynik ma charakter poglądowy.

Granice dzielnicy nie określają kompetencji instytucji ani rejonów obsługi służb. Rekomendacja adresata nadal korzysta z katalogu instytucji, rodzaju problemu i lokalizacji. Przykładowe zgłoszenia wypełniające demo są danymi syntetycznymi, a nie miejskim rejestrem spraw.

## Architektura i odświeżanie

Plik `apps/web/src/data/krakow-districts.json` jest częścią builda frontendu. Rozpoznawanie, filtrowanie i rysowanie granic działają bez połączenia z MSIP, klucza API, dodatkowej konfiguracji serwera ani migracji bazy. Mapa podkładowa i API zgłoszeń nadal wymagają własnych połączeń sieciowych. Dzielnica jest wyliczana z lokalizacji, nie zapisywana jako nowe pole w bazie.

1. Z katalogu `apps/web` uruchom narzędzie przez uv w wersji z `mise.toml`:

   ```sh
   mise exec -- uv run --no-project scripts/update-krakow-districts.py
   ```

2. Skrypt pobiera oficjalną paczkę, sprawdza układ współrzędnych i kompletność 18 dzielnic, przelicza geometrię przez przypięty `pyproj` i zapisuje źródło, daty oraz sumę kontrolną. Pierwsze uruchomienie pobiera zależność narzędzia; frontend nie potrzebuje jej w czasie działania.
3. Sprawdź zmiany danych i metadanych, zaktualizuj daty i sumę kontrolną w tym dokumencie, uruchom kontrole frontendu i opublikuj jego nowy build. Dane nie odświeżają się automatycznie przy starcie aplikacji.

Do odtworzenia snapshotu z wcześniej pobranej paczki użyj `--archive /ścieżka/Dzielnice_JSON.zip --retrieved-on RRRR-MM-DD`, podając rzeczywistą datę jej pobrania.

## Scenariusz weryfikacji demo

1. Otwórz mapę i wybierz „Dzielnica I Stare Miasto”. Sprawdź zaznaczoną granicę i sprawy widoczne tylko w tym obszarze. Wybór dzielnicy bez spraw powinien pokazać pusty wynik.
2. Na komputerze zaloguj się i postaw pinezkę na Rynku Głównym, np. przy `50.06170, 19.93700`. Formularz powinien wskazać „Dzielnica I Stare Miasto”.
3. Zapisz zgłoszenie i otwórz jego szczegóły. Sprawdź dzielnicę oraz odnośnik do MSIP.
4. Po wybraniu lub uzyskaniu sugerowanego adresata otwórz link email. W programie pocztowym sprawdź opis, współrzędne, dzielnicę i źródło. Otwarcie wiadomości jej nie wysyła.
5. Wybierz „Wszystkie lokalizacje”. Sprawy spoza Krakowa powinny być ponownie dostępne, bez przypisanej krakowskiej dzielnicy.

Testy `apps/web/tests/krakowDistricts.test.ts` sprawdzają znane lokalizacje, punkty spoza miasta, krawędzie i otwory wielokątów. Testy wiadomości sprawdzają dołączanie danych MSIP i zachowanie treści dla lokalizacji spoza Krakowa.
