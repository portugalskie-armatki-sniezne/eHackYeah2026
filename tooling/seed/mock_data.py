"""mock users, places, topics, and scenarios in Kraków for application demos."""

from dataclasses import dataclass


# responsible parties are service entity source keys or the Kraków city office.
ZDMK = "bip:127777"
ZZM = "bip:120701"
ZTP = "bip:129155"
ZIS = "bip:103246"
SMMK = "bip:102074"
MPO = "official:mpo-krakow"
WMK = "official:wodociagi-krakow"
CITY_OFFICE = "office:1261011"


@dataclass(frozen=True)
class Topic:
    category: str
    responsible: str
    photos: tuple[str, ...]
    titles: tuple[str, ...]
    descriptions: tuple[str, ...]
    in_progress_response: str
    finished_response: str


@dataclass(frozen=True)
class Scenario:
    topic: str
    # a short place name for titles of later reports.
    place: str
    title: str
    description: str
    longitude: float
    latitude: float
    days_ago: float
    status: str
    report_count: int
    # the demo user account submits the first report.
    by_demo_user: bool = False


# the demo accounts share MOCK_PASSWORD from populate_mock_data.py.
DEMO_ACCOUNTS = (
    ("user", "Anna", "Demo", "user"),
    ("office", "Biuro", "Obsługi Zgłoszeń", "office"),
    ("admin", "Administrator", "Demo", "admin"),
)

CITIZENS = (
    ("Jan", "Kowalski"), ("Katarzyna", "Nowak"), ("Piotr", "Wiśniewski"), ("Magdalena", "Wójcik"),
    ("Tomasz", "Kowalczyk"), ("Agnieszka", "Kamińska"), ("Michał", "Lewandowski"), ("Joanna", "Zielińska"),
    ("Paweł", "Szymański"), ("Aleksandra", "Woźniak"), ("Krzysztof", "Dąbrowski"), ("Monika", "Kozłowska"),
    ("Marcin", "Jankowski"), ("Ewa", "Mazur"), ("Łukasz", "Kwiatkowski"), ("Natalia", "Krawczyk"),
    ("Grzegorz", "Piotrowski"), ("Zofia", "Grabowska"), ("Adam", "Pawłowski"), ("Barbara", "Michalska"),
    ("Kamil", "Król"), ("Weronika", "Wieczorek"), ("Rafał", "Jabłoński"), ("Julia", "Wróbel"),
    ("Stanisław", "Nowakowski"), ("Halina", "Majewska"), ("Bartosz", "Olszewski"),
)

# named places in Kraków for generated reports, longitude first.
PLACES = (
    ("ul. Karmelicka", 19.9310, 50.0665), ("ul. Dietla", 19.9450, 50.0540),
    ("ul. Starowiślna", 19.9460, 50.0570), ("al. Mickiewicza", 19.9230, 50.0640),
    ("ul. Królewska", 19.9200, 50.0730), ("ul. Kijowska", 19.9140, 50.0750),
    ("ul. Armii Krajowej", 19.8900, 50.0760), ("ul. Bronowicka", 19.9000, 50.0820),
    ("ul. Opolska", 19.9400, 50.0895), ("ul. Pachońskiego", 19.9330, 50.0950),
    ("os. Azory", 19.9090, 50.0860), ("ul. Wrocławska", 19.9200, 50.0800),
    ("ul. Prądnicka", 19.9380, 50.0850), ("ul. Lubicz", 19.9520, 50.0650),
    ("ul. Grzegórzecka", 19.9560, 50.0590), ("ul. Kotlarska", 19.9690, 50.0530),
    ("ul. Mogilska", 19.9750, 50.0700), ("al. Pokoju", 19.9850, 50.0640),
    ("ul. Dobrego Pasterza", 19.9650, 50.0820), ("os. Oświecenia", 20.0050, 50.0930),
    ("os. Kazimierzowskie", 20.0050, 50.0870), ("os. Słoneczne", 20.0280, 50.0790),
    ("os. Szklane Domy", 20.0410, 50.0730), ("ul. Bulwarowa", 20.0600, 50.0700),
    ("os. Na Skarpie", 20.0480, 50.0680), ("ul. Wielicka", 19.9850, 50.0290),
    ("ul. Kurczaba", 19.9990, 50.0150), ("ul. Witosa", 19.9590, 50.0120),
    ("ul. Zakopiańska", 19.9330, 50.0200), ("ul. Kamieńskiego", 19.9550, 50.0320),
    ("ul. Lipowa", 19.9615, 50.0475), ("ul. Kapelanka", 19.9230, 50.0420),
    ("ul. Grota-Roweckiego", 19.9120, 50.0300), ("ul. Babińskiego", 19.8990, 50.0240),
    ("ul. Królowej Jadwigi", 19.8950, 50.0580), ("al. Kasztanowa", 19.8780, 50.0610),
    ("ul. Tyniecka", 19.9050, 50.0450), ("ul. Bieżanowska", 20.0250, 50.0200),
)

TOPICS = {
    "pothole": Topic(
        "issue", ZDMK, ("pothole.jpg",),
        ("Dziura w jezdni", "Głęboka dziura w asfalcie", "Wyrwa w nawierzchni jezdni"),
        ("Duża dziura na pasie ruchu, samochody gwałtownie ją omijają. Po deszczu jest niewidoczna.",
         "Wyrwa ma kilkanaście centymetrów głębokości i się powiększa. Grozi uszkodzeniem kół.",
         "Na jezdni zrobiła się dziura, rowerzyści muszą zjeżdżać na środek pasa."),
        "Zgłoszenie przekazano do służby drogowej. Tymczasowe łatanie zaplanowano w ciągu 7 dni.",
        "Ubytek nawierzchni został naprawiony masą na gorąco. Dziękujemy za zgłoszenie.",
    ),
    "sidewalk": Topic(
        "issue", ZDMK, ("sidewalk.jpg",),
        ("Zniszczony chodnik", "Zapadnięte płyty chodnikowe", "Krzywe płyty na chodniku"),
        ("Płyty chodnikowe są popękane i wystają, łatwo się potknąć, szczególnie wieczorem.",
         "Chodnik zapadł się przy krawężniku, trudno przejechać wózkiem dziecięcym.",
         "Kilka płyt jest wybitych, w dziurach zbiera się woda."),
        "Naprawę chodnika ujęto w harmonogramie prac utrzymaniowych na bieżący miesiąc.",
        "Płyty chodnikowe zostały wymienione i wypoziomowane.",
    ),
    "street_light": Topic(
        "issue", ZDMK, ("street_light.jpg",),
        ("Nie działa latarnia", "Zgaszone oświetlenie uliczne", "Ciemna latarnia przy przejściu"),
        ("Latarnia nie świeci od kilku dni, wieczorem na chodniku jest zupełnie ciemno.",
         "Kilka lamp z rzędu nie działa, okolica jest nieoświetlona, a obok jest przejście dla pieszych.",
         "Lampa miga i gaśnie, w nocy jest bardzo ciemno przy wejściu do bloku."),
        "Zgłoszenie przekazano konserwatorowi oświetlenia, ekipa sprawdzi zasilanie.",
        "Wymieniono oprawę i źródło światła, latarnia działa.",
    ),
    "road_sign": Topic(
        "issue", ZDMK, ("road_sign.jpg",),
        ("Przewrócony znak drogowy", "Uszkodzony znak drogowy", "Znak leży na trawniku"),
        ("Znak drogowy został przewrócony, prawdopodobnie przez samochód. Kierowcy go nie widzą.",
         "Słup znaku jest wygięty, a tarcza obrócona w złą stronę."),
        "Oznakowanie zostało zabezpieczone, ponowny montaż zlecono wykonawcy.",
        "Znak został ponownie zamontowany na nowym słupku.",
    ),
    "trash_bins": Topic(
        "issue", MPO, ("trash_bins.jpg",),
        ("Przepełnione kosze na śmieci", "Śmieci wokół koszy", "Kosze nie są opróżniane"),
        ("Kosze są przepełnione od kilku dni, worki leżą na chodniku, a wiatr roznosi śmieci.",
         "Po weekendzie wokół koszy leżą stosy odpadów, pojawiają się szczury.",
         "Kosze nie są opróżniane regularnie, przydałby się częstszy odbiór."),
        "Zwiększono częstotliwość odbioru odpadów z tego miejsca na okres wakacyjny.",
        "Teren został uprzątnięty, kosze są opróżniane codziennie.",
    ),
    "illegal_dump": Topic(
        "issue", MPO, ("illegal_dump.jpg",),
        ("Dzikie wysypisko śmieci", "Nielegalnie porzucone odpady", "Gruz i opony w zaroślach"),
        ("Ktoś wyrzucił opony, meble i gruz na skraju zieleni. Sterta rośnie z tygodnia na tydzień.",
         "W krzakach leżą worki z odpadami budowlanymi i stare meble."),
        "Uprzątnięcie odpadów zlecono, sprawę przekazano też Straży Miejskiej.",
        "Odpady zostały wywiezione, w miejscu zamontowano tablicę ostrzegawczą.",
    ),
    "fallen_tree": Topic(
        "issue", ZZM, ("fallen_tree.jpg",),
        ("Złamane drzewo", "Konar leży na alejce", "Powalone drzewo po burzy"),
        ("Po burzy duży konar spadł na alejkę i blokuje przejście. Kolejne gałęzie wiszą nad ścieżką.",
         "Złamane drzewo opiera się o inne, może spaść na spacerowiczów."),
        "Teren zabezpieczono taśmą, usunięcie drzewa zaplanowano na najbliższe dni.",
        "Konar został usunięty i pocięty, alejka jest przejezdna.",
    ),
    "playground": Topic(
        "issue", ZZM, ("playground.jpg",),
        ("Zniszczony plac zabaw", "Uszkodzona huśtawka i zjeżdżalnia", "Niebezpieczny plac zabaw"),
        ("Huśtawka wisi na jednym łańcuchu, a zjeżdżalnia jest pęknięta. Dzieci mogą się skaleczyć.",
         "Urządzenia na placu zabaw są zardzewiałe i chwieją się. Piasek nie był wymieniany od lat."),
        "Uszkodzone urządzenia wyłączono z użytkowania, zamówiono części zamienne.",
        "Wymieniono huśtawkę i zjeżdżalnię, plac zabaw przeszedł przegląd bezpieczeństwa.",
    ),
    "bench": Topic(
        "issue", ZZM, ("bench.jpg",),
        ("Połamana ławka", "Zniszczona ławka w parku", "Brakujące deski w ławce"),
        ("Ławka ma połamane deski, wystają gwoździe. Nie da się na niej usiąść.",
         "Z ławki ktoś wyrwał kilka desek, zostały ostre drzazgi."),
        "Naprawę ławki zlecono w ramach bieżącego utrzymania zieleni.",
        "Ławka została naprawiona i pomalowana.",
    ),
    "bus_shelter": Topic(
        "issue", ZTP, ("bus_shelter.jpg",),
        ("Zbita szyba w wiacie przystankowej", "Rozbita wiata na przystanku", "Szkło na przystanku"),
        ("Szyba w wiacie jest rozbita, na chodniku leży szkło. Czekający pasażerowie mogą się skaleczyć.",
         "Wiata przystankowa ma potłuczoną ścianę, szkło leży przy krawężniku."),
        "Odłamki uprzątnięto, wymianę szyby zlecono firmie utrzymującej wiaty.",
        "Szyba w wiacie została wymieniona.",
    ),
    "graffiti": Topic(
        "issue", CITY_OFFICE, ("graffiti.jpg",),
        ("Graffiti na elewacji", "Pomazana kamienica", "Napisy sprayem na murze"),
        ("Świeżo odnowiona elewacja została pomazana sprayem.",
         "Na ścianie budynku pojawiły się wulgarne napisy, widoczne z ulicy."),
        "Zgłoszenie przekazano do zarządcy budynku i Straży Miejskiej.",
        "Elewacja została wyczyszczona, zabezpieczono ją powłoką antygraffiti.",
    ),
    "water_leak": Topic(
        "issue", WMK, ("water_leak.jpg",),
        ("Wyciek wody na ulicy", "Awaria wodociągu", "Woda wybija spod asfaltu"),
        ("Spod asfaltu wybija woda, zalewa jezdnię i chodnik. Ciśnienie w kranach spadło.",
         "Na ulicy od rana płynie woda, prawdopodobnie pękła rura."),
        "Ekipa pogotowia wodociągowego jest na miejscu, trwa lokalizacja awarii.",
        "Uszkodzony odcinek rury wymieniono, nawierzchnię odtworzono.",
    ),
    "abandoned_car": Topic(
        "issue", SMMK, ("abandoned_car.jpg",),
        ("Porzucony samochód", "Wrak samochodu na parkingu", "Auto stoi od miesięcy bez kół"),
        ("Zardzewiały samochód stoi na parkingu od kilku miesięcy, ma przebite opony i zajmuje miejsce.",
         "Wrak bez tablic rejestracyjnych stoi przy śmietniku, wycieka z niego płyn."),
        "Strażnicy miejscy ustalają właściciela pojazdu, wezwano go do usunięcia auta.",
        "Pojazd został odholowany na parking strzeżony.",
    ),
    "bike_racks": Topic(
        "improvement", ZDMK, (),
        ("Stojaki rowerowe", "Brakuje stojaków na rowery", "Prośba o stojaki rowerowe"),
        ("Rowery są przypinane do barierek i latarni, bo nie ma stojaków. Proponuję kilka stojaków typu U.",
         "Przydałoby się kilkanaście stojaków rowerowych, najlepiej zadaszonych."),
        "Lokalizację stojaków uzgodniono, montaż zaplanowano w najbliższym pakiecie prac.",
        "Zamontowano 10 stojaków rowerowych typu U.",
    ),
    "crossing": Topic(
        "improvement", ZDMK, (),
        ("Nowe przejście dla pieszych", "Brakuje przejścia dla pieszych", "Prośba o przejście dla pieszych"),
        ("Mieszkańcy przechodzą przez jezdnię w miejscu bez przejścia, bo najbliższe jest daleko.",
         "Proponuję wyznaczyć przejście dla pieszych z azylem i doświetleniem."),
        "Projekt organizacji ruchu z nowym przejściem jest w trakcie uzgodnień.",
        "Przejście zostało wyznaczone i doświetlone.",
    ),
    "greenery": Topic(
        "improvement", ZZM, (),
        ("Nasadzenia drzew", "Więcej zieleni", "Prośba o posadzenie drzew"),
        ("Latem plac nagrzewa się do granic możliwości. Proponuję posadzić drzewa i zrobić łąkę kwietną.",
         "Brakuje tu cienia, kilka drzew i krzewów bardzo poprawiłoby komfort mieszkańców."),
        "Propozycję ujęto w planie jesiennych nasadzeń.",
        "Posadzono 12 drzew i założono łąkę kwietną.",
    ),
    "new_benches": Topic(
        "improvement", ZZM, (),
        ("Nowe ławki", "Brakuje ławek", "Prośba o ławki i kosze"),
        ("Na całej długości alei nie ma gdzie usiąść, przydałyby się ławki dla starszych osób.",
         "Proponuję ustawić kilka ławek z oparciami i kosze na śmieci."),
        "Ustawienie ławek ujęto w planie doposażenia terenu zieleni.",
        "Ustawiono 6 nowych ławek z oparciami.",
    ),
    "outdoor_gym": Topic(
        "improvement", ZIS, (),
        ("Siłownia plenerowa", "Prośba o siłownię pod chmurką", "Urządzenia do ćwiczeń w parku"),
        ("W okolicy nie ma miejsca do ćwiczeń na świeżym powietrzu. Proponuję siłownię plenerową.",
         "Przydałyby się drążki i urządzenia do kalisteniki dla młodzieży i dorosłych."),
        "Lokalizacja została zaakceptowana, trwa wybór wykonawcy.",
        "Siłownia plenerowa została zamontowana i oddana do użytku.",
    ),
    "transit": Topic(
        "improvement", ZTP, (),
        ("Częstsze kursy autobusów", "Za rzadkie kursy komunikacji", "Prośba o zwiększenie częstotliwości"),
        ("W godzinach szczytu autobusy są przepełnione, a kursy co 20 minut to za mało.",
         "Proponuję zwiększyć częstotliwość kursów wieczorem i w weekendy."),
        "Analizujemy napełnienia pojazdów, zmiany rozkładu są przygotowywane.",
        "Od nowego rozkładu w szczycie kursy są co 10 minut.",
    ),
    "dog_bins": Topic(
        "improvement", MPO, (),
        ("Kosze na psie odchody", "Brakuje koszy na psie odchody", "Prośba o dystrybutory torebek"),
        ("Na trasie spacerowej z psami nie ma ani jednego kosza. Proponuję kosze z dystrybutorami torebek.",
         "Właściciele psów nie mają gdzie wyrzucić torebek, przydałyby się specjalne kosze."),
        "Lokalizacje koszy zostały wyznaczone, montaż zaplanowano.",
        "Zamontowano 5 koszy z dystrybutorami torebek.",
    ),
}

# hand-written scenarios at known places in Kraków.
SCENARIOS = (
    Scenario("pothole", "ul. Krowoderska", "Ogromna dziura na Krowoderskiej przy Łobzowskiej",
             "Na skrzyżowaniu Krowoderskiej z Łobzowską jest dziura na całą szerokość pasa. "
             "Wczoraj samochód przede mną urwał w niej kołpak.",
             19.9332, 50.0703, 34, "inprogress", 4, True),
    Scenario("bus_shelter", "przystanek Stary Kleparz", "Rozbita wiata na przystanku Stary Kleparz",
             "Ktoś w nocy rozbił szybę w wiacie przystanku Stary Kleparz w kierunku Dworca. "
             "Szkło leży na peronie, ludzie wsiadają do tramwaju po odłamkach.",
             19.9398, 50.0662, 61, "finished", 3),
    Scenario("trash_bins", "Planty przy Barbakanie", "Przepełnione kosze na Plantach przy Barbakanie",
             "Kosze przy alejce koło Barbakanu są przepełnione od piątku, "
             "worki leżą na trawniku i rozwiewają je gołębie.",
             19.9418, 50.0653, 9, "reported", 3, True),
    Scenario("graffiti", "ul. Józefa", "Graffiti na odnowionej kamienicy na Józefa",
             "Elewacja kamienicy przy Józefa, odnowiona w zeszłym roku, została w nocy pomazana sprayem.",
             19.9446, 50.0511, 2, "created", 2),
    Scenario("fallen_tree", "Park Jordana", "Złamany konar w Parku Jordana",
             "Po wczorajszej wichurze duży konar spadł na główną alejkę przy pomnikach. "
             "Rano biegacze przechodzą bokiem przez trawnik.",
             19.9166, 50.0626, 47, "finished", 2),
    Scenario("playground", "os. Kolorowe", "Zniszczony plac zabaw na os. Kolorowym",
             "Na placu zabaw między blokami huśtawka wisi na jednym łańcuchu, a zjeżdżalnia jest pęknięta. "
             "Dzieci i tak się na niej bawią.",
             20.0300, 50.0750, 27, "inprogress", 3),
    Scenario("illegal_dump", "Lasek Mogilski", "Dzikie wysypisko przy Lasku Mogilskim",
             "Przy wjeździe do Lasku Mogilskiego ktoś wyrzucił opony, wersalkę i kilkanaście worków gruzu.",
             20.0498, 50.0722, 15, "reported", 2),
    Scenario("water_leak", "ul. Długa", "Awaria wodociągu na ul. Długiej",
             "Na Długiej przy Kleparzu spod asfaltu wybija woda, jezdnia jest zalana, a tramwaje zwalniają.",
             19.9366, 50.0701, 75, "finished", 4),
    Scenario("street_light", "ul. Kobierzyńska", "Ciemno na Kobierzyńskiej przy przystanku",
             "Od tygodnia nie świecą trzy latarnie przy przystanku na Kobierzyńskiej. "
             "Wieczorem idzie się do bloku po ciemku.",
             19.9152, 50.0281, 19, "inprogress", 2),
    Scenario("sidewalk", "ul. Kalwaryjska", "Zapadnięty chodnik na Kalwaryjskiej",
             "Przy Rynku Podgórskim chodnik na Kalwaryjskiej zapadł się przy krawężniku, "
             "starsza pani się tam przewróciła.",
             19.9481, 50.0436, 12, "reported", 2),
    Scenario("abandoned_car", "os. Bohaterów Września", "Wrak samochodu na os. Bohaterów Września",
             "Na parkingu między blokami od pół roku stoi wrak czerwonego poloneza z przebitymi oponami.",
             20.0118, 50.0958, 38, "inprogress", 1),
    Scenario("bench", "Park Bednarskiego", "Połamana ławka w Parku Bednarskiego",
             "Ławka przy górnej alejce w Parku Bednarskiego ma wyrwane deski i wystające gwoździe.",
             19.9512, 50.0431, 1, "created", 1),
    Scenario("road_sign", "Rondo Mogilskie", "Przewrócony znak przy Rondzie Mogilskim",
             "Znak ustąp pierwszeństwa przy zjeździe z Ronda Mogilskiego leży na trawniku.",
             19.9604, 50.0656, 52, "finished", 2),
    Scenario("sidewalk", "ul. Lea", "Krzywy chodnik na ul. Lea",
             "Na Lea między Kijowską a Bronowicką płyty chodnika wystają nawet na kilka centymetrów.",
             19.9142, 50.0716, 5, "created", 3),
    Scenario("trash_bins", "Bulwar Czerwieński", "Śmieci na Bulwarze Czerwieńskim po weekendzie",
             "W każdy poniedziałek na Bulwarze Czerwieńskim leżą butelki i kartony z jedzeniem, "
             "kosze nie wystarczają.",
             19.9336, 50.0534, 24, "inprogress", 3),
    Scenario("bike_racks", "Kampus UJ", "Stojaki rowerowe przy Kampusie UJ",
             "Przy wydziałach na Łojasiewicza rowery są przypinane do barierek i latarni. "
             "Proponuję zadaszone stojaki przy wejściach do budynków.",
             19.9055, 50.0296, 41, "reported", 4, True),
    Scenario("crossing", "ul. Wielicka", "Przejście dla pieszych na Wielickiej przy przystanku",
             "Do przystanku po drugiej stronie Wielickiej trzeba iść 300 metrów do świateł, "
             "więc ludzie przebiegają przez jezdnię. Proponuję przejście z sygnalizacją.",
             19.9761, 50.0311, 8, "created", 5),
    Scenario("greenery", "Plac Centralny", "Drzewa na Placu Centralnym",
             "Latem Plac Centralny to rozgrzana betonowa patelnia. "
             "Proponuję posadzić szpaler drzew i zrobić łąkę kwietną na skwerach.",
             20.0378, 50.0720, 30, "reported", 3),
    Scenario("new_benches", "Aleja Róż", "Ławki wzdłuż Alei Róż",
             "Starsi mieszkańcy Nowej Huty nie mają gdzie odpocząć na spacerze Aleją Róż. "
             "Prośba o ławki z oparciami co 50 metrów.",
             20.0372, 50.0748, 4, "created", 2, True),
    Scenario("outdoor_gym", "Park Lotników Polskich", "Siłownia plenerowa w Parku Lotników",
             "Proponuję postawić siłownię plenerową i drążki do kalisteniki przy alejce w Parku Lotników.",
             19.9970, 50.0770, 33, "inprogress", 2),
    Scenario("transit", "Bronowice Małe", "Częstsze autobusy do Bronowic Małych",
             "W porannym szczycie autobusy z Bronowic Małych są tak pełne, że nie zatrzymują się na przystankach. "
             "Proszę o więcej kursów.",
             19.8802, 50.0822, 14, "created", 3),
    Scenario("dog_bins", "Zakrzówek", "Kosze na psie odchody przy Zakrzówku",
             "Na ścieżkach wokół Zakrzówka spaceruje mnóstwo osób z psami, a koszy prawie nie ma.",
             19.9150, 50.0381, 66, "finished", 2),
    Scenario("crossing", "ul. Mazowiecka", "Doświetlenie przejścia przy szkole na Mazowieckiej",
             "Przejście przy szkole na Mazowieckiej jest słabo oświetlone, zimą rano dzieci są niewidoczne.",
             19.9221, 50.0761, 57, "finished", 2),
)

ISSUE_COMMENTS = (
    "Potwierdzam, dzisiaj rano wyglądało to tak samo.",
    "Mieszkam obok i problem trwa już dobre dwa tygodnie.",
    "Też to zgłaszałam telefonicznie, bez odzewu.",
    "Dobrze, że ktoś to zgłosił, codziennie tędy chodzę z dziećmi.",
    "Wieczorem jest jeszcze gorzej, nic nie widać.",
    "Wczoraj ktoś prawie się tu przewrócił.",
    "Dołączam się, sytuacja się pogarsza.",
    "Czy ktoś wie, kiedy będzie naprawa?",
    "Dzięki za zgłoszenie, myślałem, że tylko mnie to przeszkadza.",
    "To nie pierwszy raz w tym miejscu, problem wraca co kilka miesięcy.",
    "Proponuję chociaż oznaczyć to miejsce do czasu naprawy.",
    "Byłem dziś, nadal nic się nie zmieniło.",
    "Super, że to w końcu ruszyło.",
    "Widziałem dzisiaj ekipę na miejscu.",
)

IMPROVEMENT_COMMENTS = (
    "Świetny pomysł, popieram!",
    "Bardzo potrzebne, dołączam się do prośby.",
    "W końcu ktoś o tym napisał.",
    "Popieram, ale warto też pomyśleć o oświetleniu.",
    "Mieszkańcy osiedla na pewno skorzystają.",
    "To mogłoby trafić do budżetu obywatelskiego.",
    "Popieram, w podobnym miejscu w innej dzielnicy to świetnie działa.",
    "Ważne, żeby było dostępne dla osób z niepełnosprawnościami.",
    "Jestem za, ale bez wycinania istniejącej zieleni.",
    "Podpisuję się obiema rękami.",
)

OFFICE_COMMENTS = {
    "inprogress": (
        "Dziękujemy za zgłoszenia. Sprawa jest w realizacji, będziemy informować o postępach.",
        "Zgłoszenie zostało przekazane do realizacji. Prosimy o cierpliwość.",
    ),
    "finished": (
        "Prace zostały zakończone. Dziękujemy mieszkańcom za zgłoszenia.",
        "Sprawa została załatwiona, prosimy o kontakt, jeśli problem powróci.",
    ),
}
