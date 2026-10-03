# Pomiar klasyfikacji jednostek - 2026-10-04

Pomiar wykonano na rzeczywistych lokalnych modelach, bez mockowania predykcji.
Dane są syntetyczne i opisują typowe zgłoszenia aplikacji.

| Zbiór | Poprawne / oznaczone | Trafność |
| --- | --- | --- |
| Roboczy (`development`) | 11 / 15 | 73,3% |
| Walidacyjny (`holdout`) | 31 / 37 | 83,8% |
| Łącznie | 42 / 52 | 80,8% |

Trzy dodatkowe przypadki bez jednoznacznej etykiety sprawdzają wyłącznie
wymuszony wybór: niepełny opis, problem spoza katalogu i kilka problemów naraz.
Wszystkie 55 przypadków zwróciło jedną poprawną wartość enuma. W dwóch
przypadkach ze zdjęciem model poprawnie wybrał typ raz. To za mała próba,
żeby ocenić trafność klasyfikacji zdjęć.

Wariant z krótkimi opisami, bez korekty preferencji, osiągnął 23/37 na zbiorze
walidacyjnym. Korekta preferencji została dobrana na zbiorze roboczym, a jej
pomijanie dla zdjęć wprowadzono po analizie wyników walidacyjnych. Zbiór o nazwie
`holdout` nie jest już nietkniętym testem końcowym. Potrzebny jest osobny pomiar
na nowych, rzeczywistych zgłoszeniach przed oceną gotowości do automatycznych przydziałów.

## Konfiguracja

- Laya: `thaitea/laya-vision`, rewizja `f2fe3c12cb6d04c59d8a190250bf3fb40fc828dc`.
- Tłumacz: `Helsinki-NLP/opus-mt-pl-en`, rewizja `7f2bb874fdfb6139f9842b91a9b75c4a6c93401c`.
- Biblioteka Laya: commit `9e1e2419d855ad3e1a2af4d4bd1ef6be5418842c`.
- Transformers 5.18.0, PyTorch 2.14.1, CPU, 3 permutacje, `strict=True`.
- `head_max_len=768`, `max_len=2048`, korekta tekstowa o sile 1, bez korekty zdjęć.
- Kryteria: `app/inference/entity_types.json`; źródło typów: wspólny enum API.

Instrukcja odtworzenia pomiaru jest w [inference.md](inference.md#testy-i-pomiar-trafności).
Skrypt zapisuje każdą predykcję, tłumaczenie i czas, a także wersje bibliotek oraz
sumy SHA-256 kryteriów i danych. Próg `--min-accuracy 0.8` został przekroczony;
nie jest gwarancją trafności na danych produkcyjnych.

## Nierozwiązane pomyłki

Identyfikatory odnoszą się do [danych testowych](../../../tests/fixtures/entity_classification.json).

| Przypadek | Oczekiwany typ | Wybrany typ |
| --- | --- | --- |
| `transport_authority-1` | `transport_authority` | `transport_operator` |
| `transport_authority-2` | `transport_authority` | `transport_operator` |
| `transport_operator-3` | `transport_operator` | `heating_utility` |
| `water_sewage_authority-1` | `water_sewage_authority` | `water_sewage_utility` |
| `municipal_guard-1` | `municipal_guard` | `road_manager` |
| `housing_manager-2` | `housing_manager` | `municipal_services` |
| `sports_infrastructure_manager-1` | `sports_infrastructure_manager` | `water_infrastructure_manager` |
| `park-waste` | `waste_management` | `green_space_manager` |
| `guard-dumping` | `municipal_guard` | `waste_management` |
| `photo-waste` | `waste_management` | `road_manager` |

Pomyłki obejmują rozróżnienie organizatora transportu i przewoźnika, miejsce
usterki względem rodzaju usługi oraz interwencję straży względem usuwania odpadów.
Tłumacz dodatkowo gubi część znaczenia: „bramki na boisku” oddaje jako „gates”,
a „międzygminny związek” nie zachowuje poprawnie we wszystkich zdaniach.
Dostawców można wymienić bez zmiany kontraktu API; obecny wynik nie oznacza
bezbłędnego wyboru najwłaściwszej instytucji.
