# pomożeMy - korzyści dla mieszkańców i miasta

**Trzy scenariusze dla Krakowa | Open Data App 2026**

Zespół: Portugalskie Armatki Śnieżne

Rozbita wiata, dziura w jezdni, pomysł na przyjemniejsze sąsiedztwo. Mieszkańcy dobrze znają swoją okolicę, ale nie zawsze wiedzą, komu zgłosić problem i co dzieje się z nim dalej. pomożeMy łączy ich obserwacje z miejskimi danymi: pomaga opisać sprawę, wskazać miejsce i przygotować kontakt z instytucją.

## 1. Rozbita wiata, konkretne zgłoszenie

Na przystanku Stary Kleparz leży szkło z rozbitej szyby. Pasażer nie wie, kto utrzymuje wiatę. W pomożeMy zaznacza miejsce, dodaje zdjęcie i opis. Aplikacja sugeruje adresata, a dane zgłoszenia są gotowe do wykorzystania w wiadomości. Kolejna osoba może obejrzeć tę samą sprawę i jej status.

**Dla mieszkańca:** łatwiej przygotować zgłoszenie bez szukania od początku właściwego kontaktu.

**Dla instytucji:** opis, zdjęcie i lokalizacja pomagają ustalić, co i gdzie wymaga interwencji.

**Rola danych:** granice MSIP pozwalają rozpoznać Dzielnicę I Stare Miasto i odnaleźć sprawę w jej obszarze. Sugestia adresata korzysta osobno z katalogu instytucji i treści zgłoszenia.

## 2. Ta sama dziura, jedna wspólna sprawa

Na Krowoderskiej kierowcy omijają wyrwę, a rowerzyści muszą zmieniać tor jazdy. Każdy widzi ten sam problem. pomożeMy może połączyć podobne zgłoszenia z najbliższej okolicy w jedną sprawę. Zdjęcia, komentarze i odpowiedź są dostępne razem. Gdy urząd lub administrator zmieni status, autorzy zgłoszeń otrzymają powiadomienie w aplikacji.

**Dla mieszkańca:** można sprawdzić postęp zamiast zgadywać, czy ktoś już zajął się sprawą.

**Dla instytucji:** wspólna karta porządkuje sygnały od wielu osób i dokumentację usterki.

**Rola danych:** granice MSIP łączą lokalizację zgłoszenia z dzielnicą. Filtr dzielnic pozwala przeglądać pobliskie sprawy; grupowanie wykorzystuje treści i współrzędne podane przez mieszkańców.

## 3. Miejsce spotkań zaczyna się od pomysłu

W okolicy CAS Senior w Centrum przy ul. Berka Joselewicza 28 mieszkańcy proponują ławki i zieleń: miejsce na odpoczynek po zajęciach i sąsiedzką rozmowę. Z karty placówki na mapie przechodzą do inicjatywy. Po zapisaniu pomysłu dodają zdjęcie przestrzeni. Wizualizacja pokazuje możliwą zmianę i ułatwia rozmowę o tym, czego potrzebuje okolica.

**Dla mieszkańca:** konkretny obraz pomaga wyjaśnić pomysł i zebrać uwagi sąsiadów.

**Dla miasta i organizatora CAS:** propozycja ma lokalizację oraz czytelny kontekst społeczny.

**Rola danych:** miejski zbiór CAS wskazuje rzeczywistą placówkę, jej adres, operatora i kontakt. Granice MSIP dodają kontekst dzielnicy. To hipotetyczna inicjatywa, a wizualizacja jest koncepcją; nie potwierdza dostępności terenu ani zgody na realizację.

## Pokaż to w demo

Przygotuj demo z przykładowymi sprawami opisanymi w [TESTING.md](../TESTING.md#mock-demo-data). Na komputerze otwórz mapę, ustaw język polski, wybierz „Dzielnica I Stare Miasto” i pozostaw widoczne wszystkie statusy. Do dodawania treści zaloguj się na konto demonstracyjne.

### Wiata: od miejsca do kontaktu

1. Otwórz sprawę „Rozbita wiata na przystanku Stary Kleparz” przy `50.06620, 19.93980`.
2. Pokaż zdjęcie, dzielnicę, status i odpowiedź w karcie sprawy.
3. Kliknij adres e-mail instytucji i pokaż przygotowaną wiadomość w programie pocztowym. Otwarcie jej nie wysyła.

**Efekt:** dokumentacja problemu i dane do kontaktu w jednym miejscu.

### Krowoderska: kilka zgłoszeń, wspólny przebieg

1. Otwórz „Ogromna dziura na Krowoderskiej przy Łobzowskiej” przy `50.07030, 19.93320`.
2. W zakładce „Zgłoszenia” pokaż zgłoszenia składowe i ich zdjęcia.
3. Porównaj je ze wspólnym statusem, odpowiedzią i komentarzami sprawy.

**Efekt:** kilka obserwacji mieszkańców tworzy jedną uporządkowaną sprawę.

### CAS: od miejskiego punktu do wizualizacji

1. Włącz warstwę „CAS” i otwórz „CAS Senior w Centrum” przy `50.05533, 19.94794`.
2. Wybierz „Zgłoś inicjatywę w tej okolicy”. Wpisz tytuł „Miejsce spotkań przy CAS” oraz opis: „Przykład demonstracyjny ze zdjęciem poglądowym. Proponujemy ławki z oparciami i zieleń w okolicy CAS, z miejscem dla osób poruszających się na wózku”. Zapisz; jeśli pojawi się propozycja ROPS, wybierz „Zgłoś jako nowy pomysł”.
3. Otwórz własną inicjatywę i przez „Dodaj zdjęcie” dołącz [plik bench.jpg z repozytorium](../tooling/seed/mock_photos/bench.jpg). To syntetyczna ilustracja parku, nie zdjęcie otoczenia CAS.
4. Ponownie otwórz kartę jako autor i poczekaj na generację. Przełącz „Wizualizacja”, aby zestawić zdjęcie z koncepcją. Wymaga to działającej usługi generowania i dostępnego limitu konta.

**Efekt:** miejskie dane prowadzą do konkretnej propozycji, którą można pokazać i omówić.

## Jak czytać te przykłady

Usterki, zdjęcia, odpowiedzi i statusy dwóch pierwszych historii są syntetycznymi danymi demo. Nie dokumentują rzeczywistych interwencji. Automatyczne maile trafiają na skrzynkę testową. Sugerowany adresat wymaga weryfikacji; granice dzielnic nie wyznaczają kompetencji instytucji.

## Źródła miejskie

- [MSIP: Podział administracyjny - dzielnice](https://msip.krakow.pl/dataset/1483).
- [Otwarte Dane Kraków: Centra Aktywności Seniora](https://otwartedane.um.krakow.pl/zbiory-danych/centra-aktywnosci-seniora-w-krakowie).
