/**
 * Development report data for the map, shaped after the schema in `db/migrations`.
 *
 * A citizen files a row of `reports`. Filings about the same thing are classified
 * under one row of `master_reports`, which carries the shared status, the
 * responsible party and the single response every filing under it gets. The map
 * draws masters, so what a pin stands for is the aggregate - `reportCount` is how
 * many filings are behind it.
 *
 * Replace the arrays below with the API once reports are served; the
 * `AggregatedReport` shape is what the map consumes either way.
 */

/** report_categories.name */
export type ReportCategory = "improvement" | "issue";

/** master_report_statuses.name */
export type ReportStatus = "created" | "reported" | "inprogress" | "finished";

/** WGS 84, longitude first, the way GEOGRAPHY(POINT, 4326) stores it. */
export type LngLat = [number, number];

/** A row of `reports`: one filing, by one user, about one place. */
export type Report = {
  id: string;
  userId: string;
  /** null until an operator classifies the filing under a master */
  masterReportId: string | null;
  category: ReportCategory;
  title: string;
  description: string;
  location: LngLat;
  createdAt: string;
  /** report_photos.storage_key values, not expiring download urls */
  photoKeys: string[];
};

/** A row of `master_reports`: the issue several filings are folded into. */
export type MasterReport = {
  id: string;
  category: ReportCategory;
  status: ReportStatus;
  title: string;
  description: string;
  location: LngLat;
  /** the one answer shown for every filing under this master */
  response: string | null;
  /** at most one responsible party, as the schema's check constraint requires */
  responsibleOffice: string | null;
  responsibleServiceEntity: string | null;
  createdAt: string;
};

/** A master together with the filings that resolve to it. */
export type AggregatedReport = MasterReport & {
  reports: Report[];
  /** how many filings the master stands for, never below one */
  reportCount: number;
  /** newest `reports.created_at` under the master, or the master's own date */
  lastReportedAt: string;
};

const POZNAN_TERYT = "3064011";

// stands in for `users.id`; the filings below are spread across these authors
const USERS = {
  ewa: "3f1b0c8a-5d94-4f1e-9b2a-7c6e0d1a4b31",
  marek: "8a2d4e61-0c73-4b85-91df-2e5a7b9c0146",
  anna: "c47f9b20-6e18-4a3d-85b1-9d02f3c7e58a",
  tomasz: "1d6e3a95-b2c4-47f8-a0e3-5b84c1d9f260",
  kasia: "6b90f2c7-4a15-48de-9372-0e1c8b5a7d43",
  piotr: "e5c8104a-9f26-4b03-8d71-3a605c2e9b18",
} as const;

export const MASTER_REPORTS: MasterReport[] = [
  {
    id: "a1c7e4f2-3b58-4d90-8e16-2f7a9c0b5d31",
    category: "issue",
    status: "inprogress",
    title: "Potholes on Rondo Kaponiera",
    description:
      "The inside lane around the roundabout has broken up into a run of deep potholes.",
    location: [16.9148, 52.4081],
    response: "Resurfacing is scheduled for the next maintenance window.",
    responsibleOffice: null,
    responsibleServiceEntity: `${POZNAN_TERYT}-road_manager`,
    createdAt: "2026-09-14T08:12:00Z",
  },
  {
    id: "b2d8f5a3-4c69-4e01-9f27-3a8b0d1c6e42",
    category: "improvement",
    status: "reported",
    title: "Benches and shade trees on Plac Wolnosci",
    description:
      "The square has no shade and nowhere to sit between the library and the fountain.",
    location: [16.9256, 52.4073],
    response: null,
    responsibleOffice: POZNAN_TERYT,
    responsibleServiceEntity: null,
    createdAt: "2026-09-21T16:40:00Z",
  },
  {
    id: "c3e9a6b4-5d7a-4f12-8036-4b9c1e2d7f53",
    category: "issue",
    status: "created",
    title: "Street lamp out on Ostrow Tumski",
    description:
      "The lamp on the cathedral side of the bridge has been dark for about a week.",
    location: [16.948, 52.4113],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: null,
    createdAt: "2026-09-29T20:05:00Z",
  },
  {
    id: "d4fab7c5-6e8b-4023-9147-5c0d2f3a8064",
    category: "issue",
    status: "finished",
    title: "Bins overflowing on Stary Rynek",
    description:
      "Bins along the north side of the market square stay full through the weekend.",
    location: [16.9341, 52.4082],
    response: "Collection on the square was moved to a daily round.",
    responsibleOffice: null,
    responsibleServiceEntity: `${POZNAN_TERYT}-waste_management`,
    createdAt: "2026-08-30T09:25:00Z",
  },
  {
    id: "e50bc8d6-7f9c-4134-8258-6d1e3a4b9175",
    category: "improvement",
    status: "inprogress",
    title: "Bike racks at Dworzec Glowny",
    description:
      "Cyclists lock up against the railings because the racks by the west entrance are always full.",
    location: [16.915, 52.4015],
    response: "Two more stands are being installed by the west entrance.",
    responsibleOffice: null,
    responsibleServiceEntity: `${POZNAN_TERYT}-transport_authority`,
    createdAt: "2026-09-02T11:50:00Z",
  },
  {
    id: "f61cd9e7-80ad-4245-9369-7e2f4b5c0286",
    category: "issue",
    status: "reported",
    title: "Underpass floods in Gorczyn",
    description:
      "The pedestrian underpass stands under water for hours after any heavy rain.",
    location: [16.88, 52.387],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: `${POZNAN_TERYT}-water_sewage_utility`,
    createdAt: "2026-09-18T07:30:00Z",
  },
  {
    id: "0a2deaf8-91be-4356-8470-8f3a5c6d1397",
    category: "issue",
    status: "created",
    title: "Broken playground gate in Park Cytadela",
    description:
      "The gate by the playground hangs off one hinge and will not latch shut.",
    location: [16.931, 52.419],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: null,
    createdAt: "2026-10-01T15:18:00Z",
  },
  {
    id: "1b3efb09-a2cf-4467-9581-004b6d7e24a8",
    category: "improvement",
    status: "reported",
    title: "Crossing on Dabrowskiego in Jezyce",
    description:
      "Children walk 200 metres out of their way to the nearest crossing on the way to school.",
    location: [16.902, 52.411],
    response: null,
    responsibleOffice: POZNAN_TERYT,
    responsibleServiceEntity: null,
    createdAt: "2026-09-25T18:02:00Z",
  },
  {
    id: "2c40fc1a-b3d0-4578-8692-115c7e8f35b9",
    category: "improvement",
    status: "created",
    title: "Lighting on the Malta running track",
    description:
      "The lakeside stretch of the track is unlit, so it goes unused after dusk.",
    location: [16.98, 52.403],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: null,
    createdAt: "2026-10-02T19:44:00Z",
  },
  {
    id: "3d510d2b-c4e1-4689-9703-226d8f903ac0",
    category: "issue",
    status: "inprogress",
    title: "Smashed tram shelter in Chartowo",
    description:
      "The shelter glass on the city-bound stop is broken and the panes are still in the frame.",
    location: [16.97, 52.39],
    response: "The panes are boarded over until the glazing is replaced.",
    responsibleOffice: null,
    responsibleServiceEntity: `${POZNAN_TERYT}-transport_operator`,
    createdAt: "2026-09-27T06:55:00Z",
  },
  // The old town carries reports a block or two apart, which is where the map's
  // grouping earns its keep.
  {
    id: "4e621e3c-d5f2-479a-8814-337ea04b1cd1",
    category: "issue",
    status: "reported",
    title: "Cracked paving on Wroclawska",
    description:
      "A run of lifted setts outside the bars draws complaints every weekend.",
    location: [16.933, 52.4072],
    response: null,
    responsibleOffice: POZNAN_TERYT,
    responsibleServiceEntity: null,
    createdAt: "2026-09-12T19:30:00Z",
  },
  {
    id: "5f732f4d-e603-48ab-9925-448fb105ce02",
    category: "improvement",
    status: "created",
    title: "Bike lane on Paderewskiego",
    description:
      "The street is one way for cars and has nothing marked for bikes.",
    location: [16.9305, 52.4078],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: null,
    createdAt: "2026-09-24T08:45:00Z",
  },
  {
    id: "6084305e-f714-49bc-8a36-5590c216df13",
    category: "issue",
    status: "created",
    title: "Broken bench on Plac Kolegiacki",
    description:
      "Two slats are missing from the bench facing the old collegiate church.",
    location: [16.9345, 52.406],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: null,
    createdAt: "2026-09-30T11:05:00Z",
  },
  {
    id: "7195416f-0825-40cd-9b47-66a1d327e024",
    category: "issue",
    status: "inprogress",
    title: "Cars parked across the pavement on Wozna",
    description:
      "Pushchairs and wheelchairs have to go into the road to get past.",
    location: [16.936, 52.407],
    response: "The municipal guard has put the street on its patrol round.",
    responsibleOffice: null,
    responsibleServiceEntity: `${POZNAN_TERYT}-municipal_guard`,
    createdAt: "2026-09-08T13:20:00Z",
  },
  {
    id: "82a65270-1936-41de-8c58-77b2e438f135",
    category: "improvement",
    status: "reported",
    title: "Lighting on Zydowska",
    description:
      "The lane between the market square and the synagogue is poorly lit.",
    location: [16.9352, 52.4095],
    response: null,
    responsibleOffice: POZNAN_TERYT,
    responsibleServiceEntity: null,
    createdAt: "2026-09-17T21:10:00Z",
  },
  {
    id: "93b76381-2a47-42ef-9d69-88c3f549a246",
    category: "issue",
    status: "created",
    title: "Blocked gully on Szkolna",
    description: "The drain by the crossing backs up and floods the corner.",
    location: [16.9318, 52.4066],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: null,
    createdAt: "2026-10-01T07:40:00Z",
  },
  {
    id: "a4c87492-3b58-43f0-8e7a-99d4061ab357",
    category: "improvement",
    status: "reported",
    title: "Greenery on Polwiejska",
    description:
      "The whole shopping street is paved end to end with nothing planted.",
    location: [16.9295, 52.4035],
    response: null,
    responsibleOffice: POZNAN_TERYT,
    responsibleServiceEntity: null,
    createdAt: "2026-09-19T16:25:00Z",
  },
  {
    id: "b5d985a3-4c69-4401-8f8b-aae5172bc468",
    category: "improvement",
    status: "created",
    title: "Shelter at the Sw. Marcin stop",
    description:
      "The eastbound stop has a pole and a timetable and nothing to stand under.",
    location: [16.9245, 52.4045],
    response: null,
    responsibleOffice: null,
    responsibleServiceEntity: `${POZNAN_TERYT}-transport_authority`,
    createdAt: "2026-10-02T09:15:00Z",
  },
];

export const REPORTS: Report[] = [
  // four filings on the same roundabout, two days apart
  {
    id: "10a1b2c3-d4e5-4f60-8712-3a4b5c6d7e81",
    userId: USERS.ewa,
    masterReportId: "a1c7e4f2-3b58-4d90-8e16-2f7a9c0b5d31",
    category: "issue",
    title: "Hole in the road at Kaponiera",
    description: "Hit a hole on the inside lane coming off Roosevelta.",
    location: [16.9149, 52.4082],
    createdAt: "2026-09-14T08:12:00Z",
    photoKeys: ["reports/2026/09/kaponiera-ewa-1.jpg"],
  },
  {
    id: "11b2c3d4-e5f6-4071-8823-4b5c6d7e8f92",
    userId: USERS.marek,
    masterReportId: "a1c7e4f2-3b58-4d90-8e16-2f7a9c0b5d31",
    category: "issue",
    title: "Damaged surface on the roundabout",
    description:
      "Several potholes in a row, cyclists are swerving into traffic.",
    location: [16.9146, 52.408],
    createdAt: "2026-09-14T17:38:00Z",
    photoKeys: [],
  },
  {
    id: "12c3d4e5-f607-4182-8934-5c6d7e8f9013",
    userId: USERS.anna,
    masterReportId: "a1c7e4f2-3b58-4d90-8e16-2f7a9c0b5d31",
    category: "issue",
    title: "Potholes getting worse",
    description: "The same holes are deeper than last week.",
    location: [16.9151, 52.4079],
    createdAt: "2026-09-16T09:04:00Z",
    photoKeys: ["reports/2026/09/kaponiera-anna-1.jpg"],
  },
  {
    id: "13d4e5f6-0718-4293-8a45-6d7e8f901234",
    userId: USERS.tomasz,
    masterReportId: "a1c7e4f2-3b58-4d90-8e16-2f7a9c0b5d31",
    category: "issue",
    title: "Broken tarmac, Kaponiera",
    description: "Buses are braking hard over it every few minutes.",
    location: [16.9147, 52.4084],
    createdAt: "2026-09-19T12:21:00Z",
    photoKeys: [],
  },

  // three filings behind one square proposal
  {
    id: "14e5f607-1829-43a4-8b56-7e8f90123455",
    userId: USERS.kasia,
    masterReportId: "b2d8f5a3-4c69-4e01-9f27-3a8b0d1c6e42",
    category: "improvement",
    title: "Somewhere to sit on Plac Wolnosci",
    description: "A few benches near the library side would help.",
    location: [16.9255, 52.4074],
    createdAt: "2026-09-21T16:40:00Z",
    photoKeys: [],
  },
  {
    id: "15f60718-293a-44b5-8c67-8f9012345566",
    userId: USERS.piotr,
    masterReportId: "b2d8f5a3-4c69-4e01-9f27-3a8b0d1c6e42",
    category: "improvement",
    title: "Plant trees on the square",
    description:
      "There is no shade at all between the fountain and the tram stop.",
    location: [16.9258, 52.4072],
    createdAt: "2026-09-23T10:15:00Z",
    photoKeys: ["reports/2026/09/wolnosci-piotr-1.jpg"],
  },
  {
    id: "16071829-3a4b-45c6-8d78-901234556677",
    userId: USERS.ewa,
    masterReportId: "b2d8f5a3-4c69-4e01-9f27-3a8b0d1c6e42",
    category: "improvement",
    title: "Greenery on Plac Wolnosci",
    description:
      "The square bakes in summer, planters would already be something.",
    location: [16.9254, 52.4071],
    createdAt: "2026-09-26T13:47:00Z",
    photoKeys: [],
  },

  // a single filing, still the only one under its master
  {
    id: "1718293a-4b5c-46d7-8e89-012345566788",
    userId: USERS.marek,
    masterReportId: "c3e9a6b4-5d7a-4f12-8036-4b9c1e2d7f53",
    category: "issue",
    title: "Dark bridge on Ostrow Tumski",
    description: "The lamp by the cathedral has not come on for a week.",
    location: [16.9479, 52.4114],
    createdAt: "2026-09-29T20:05:00Z",
    photoKeys: ["reports/2026/09/tumski-marek-1.jpg"],
  },

  // five filings, the most-reported issue in the set
  {
    id: "18293a4b-5c6d-47e8-8f9a-123455667899",
    userId: USERS.anna,
    masterReportId: "d4fab7c5-6e8b-4023-9147-5c0d2f3a8064",
    category: "issue",
    title: "Bins full on the market square",
    description: "Rubbish piled around the bins by the town hall.",
    location: [16.934, 52.4083],
    createdAt: "2026-08-30T09:25:00Z",
    photoKeys: ["reports/2026/08/rynek-anna-1.jpg"],
  },
  {
    id: "193a4b5c-6d7e-48f9-80ab-23455667899a",
    userId: USERS.tomasz,
    masterReportId: "d4fab7c5-6e8b-4023-9147-5c0d2f3a8064",
    category: "issue",
    title: "Overflowing bins, Stary Rynek",
    description: "Same bins overflowing again on Sunday morning.",
    location: [16.9343, 52.4081],
    createdAt: "2026-08-31T08:10:00Z",
    photoKeys: [],
  },
  {
    id: "1a4b5c6d-7e8f-49a0-81bc-3455667899ab",
    userId: USERS.kasia,
    masterReportId: "d4fab7c5-6e8b-4023-9147-5c0d2f3a8064",
    category: "issue",
    title: "Rubbish on the square",
    description: "Gulls are pulling bags out of the bins onto the cobbles.",
    location: [16.9339, 52.408],
    createdAt: "2026-09-01T07:52:00Z",
    photoKeys: ["reports/2026/09/rynek-kasia-1.jpg"],
  },
  {
    id: "1b5c6d7e-8f90-4ab1-82cd-455667899abc",
    userId: USERS.piotr,
    masterReportId: "d4fab7c5-6e8b-4023-9147-5c0d2f3a8064",
    category: "issue",
    title: "Bins not emptied",
    description:
      "Still full on Monday, the restaurants are stacking bags beside them.",
    location: [16.9344, 52.4084],
    createdAt: "2026-09-02T18:33:00Z",
    photoKeys: [],
  },
  {
    id: "1c6d7e8f-90ab-4bc2-83de-55667899abcd",
    userId: USERS.ewa,
    masterReportId: "d4fab7c5-6e8b-4023-9147-5c0d2f3a8064",
    category: "issue",
    title: "Smell from the bins by the town hall",
    description: "It has been like this for two weekends running.",
    location: [16.9338, 52.4085],
    createdAt: "2026-09-03T12:09:00Z",
    photoKeys: [],
  },

  // three filings behind the station bike racks
  {
    id: "1d7e8f90-ab12-4cd3-84ef-667899abcdef",
    userId: USERS.marek,
    masterReportId: "e50bc8d6-7f9c-4134-8258-6d1e3a4b9175",
    category: "improvement",
    title: "More bike racks at the station",
    description:
      "The racks by the west entrance are full before eight in the morning.",
    location: [16.9151, 52.4016],
    createdAt: "2026-09-02T11:50:00Z",
    photoKeys: ["reports/2026/09/dworzec-marek-1.jpg"],
  },
  {
    id: "1e8f90ab-1223-4de4-85f0-7899abcdef01",
    userId: USERS.anna,
    masterReportId: "e50bc8d6-7f9c-4134-8258-6d1e3a4b9175",
    category: "improvement",
    title: "Nowhere to lock a bike",
    description: "Everyone ends up locking to the railings by the stairs.",
    location: [16.9148, 52.4014],
    createdAt: "2026-09-05T08:27:00Z",
    photoKeys: [],
  },
  {
    id: "1f90ab12-2334-4ef5-8601-899abcdef012",
    userId: USERS.kasia,
    masterReportId: "e50bc8d6-7f9c-4134-8258-6d1e3a4b9175",
    category: "improvement",
    title: "Covered bike parking, Dworzec Glowny",
    description: "A roof over the stands would make them usable in winter.",
    location: [16.9153, 52.4013],
    createdAt: "2026-09-11T17:14:00Z",
    photoKeys: [],
  },

  // two filings on the flooded underpass
  {
    id: "20ab1223-3445-4f06-8712-99abcdef0123",
    userId: USERS.tomasz,
    masterReportId: "f61cd9e7-80ad-4245-9369-7e2f4b5c0286",
    category: "issue",
    title: "Water in the Gorczyn underpass",
    description: "Ankle deep after this morning's rain, no way through.",
    location: [16.8801, 52.3871],
    createdAt: "2026-09-18T07:30:00Z",
    photoKeys: ["reports/2026/09/gorczyn-tomasz-1.jpg"],
  },
  {
    id: "21b12233-4556-4017-8823-9abcdef01234",
    userId: USERS.piotr,
    masterReportId: "f61cd9e7-80ad-4245-9369-7e2f4b5c0286",
    category: "issue",
    title: "Blocked drain in the underpass",
    description: "The grate at the bottom of the steps is packed with leaves.",
    location: [16.8799, 52.3869],
    createdAt: "2026-09-20T15:41:00Z",
    photoKeys: [],
  },

  // a single filing on the playground gate
  {
    id: "22223344-5667-4128-8934-abcdef012345",
    userId: USERS.kasia,
    masterReportId: "0a2deaf8-91be-4356-8470-8f3a5c6d1397",
    category: "issue",
    title: "Playground gate off its hinge",
    description: "Toddlers can push straight through onto the path.",
    location: [16.9311, 52.4191],
    createdAt: "2026-10-01T15:18:00Z",
    photoKeys: ["reports/2026/10/cytadela-kasia-1.jpg"],
  },

  // two filings behind the Jezyce crossing
  {
    id: "23334455-6778-4239-8a45-bcdef0123456",
    userId: USERS.ewa,
    masterReportId: "1b3efb09-a2cf-4467-9581-004b6d7e24a8",
    category: "improvement",
    title: "Crossing needed by the school",
    description:
      "Parents cross mid-block because the next crossing is far off.",
    location: [16.9021, 52.4111],
    createdAt: "2026-09-25T18:02:00Z",
    photoKeys: [],
  },
  {
    id: "24445566-7889-434a-8b56-cdef01234567",
    userId: USERS.marek,
    masterReportId: "1b3efb09-a2cf-4467-9581-004b6d7e24a8",
    category: "improvement",
    title: "Zebra crossing on Dabrowskiego",
    description: "People already cross here, it may as well be marked.",
    location: [16.9018, 52.4109],
    createdAt: "2026-09-28T09:36:00Z",
    photoKeys: [],
  },

  // a single filing on the Malta track
  {
    id: "25556677-899a-445b-8c67-def012345678",
    userId: USERS.anna,
    masterReportId: "2c40fc1a-b3d0-4578-8692-115c7e8f35b9",
    category: "improvement",
    title: "Lights along the Malta track",
    description: "The lakeside stretch is pitch dark after five in winter.",
    location: [16.9801, 52.4031],
    createdAt: "2026-10-02T19:44:00Z",
    photoKeys: [],
  },

  // two filings on the tram shelter
  {
    id: "26667788-9aab-456c-8d78-ef0123456789",
    userId: USERS.piotr,
    masterReportId: "3d510d2b-c4e1-4689-9703-226d8f903ac0",
    category: "issue",
    title: "Broken shelter glass in Chartowo",
    description: "One pane is shattered and still sitting in the frame.",
    location: [16.9701, 52.3901],
    createdAt: "2026-09-27T06:55:00Z",
    photoKeys: ["reports/2026/09/chartowo-piotr-1.jpg"],
  },
  {
    id: "27778899-aabc-467d-8e89-f01234567890",
    userId: USERS.tomasz,
    masterReportId: "3d510d2b-c4e1-4689-9703-226d8f903ac0",
    category: "issue",
    title: "Glass on the tram stop floor",
    description: "Splinters across the paving where people wait.",
    location: [16.9698, 52.3899],
    createdAt: "2026-09-30T07:12:00Z",
    photoKeys: [],
  },

  // the old town filings, several of them a block apart
  {
    id: "30aa11bb-22cc-4833-8d44-55ee66ff7700",
    userId: USERS.ewa,
    masterReportId: "4e621e3c-d5f2-479a-8814-337ea04b1cd1",
    category: "issue",
    title: "Lifted setts on Wroclawska",
    description: "Caught a heel in the gap outside the pub last night.",
    location: [16.9331, 52.4073],
    createdAt: "2026-09-12T19:30:00Z",
    photoKeys: ["reports/2026/09/wroclawska-ewa-1.jpg"],
  },
  {
    id: "31bb22cc-33dd-4944-8e55-66ff7700aa11",
    userId: USERS.piotr,
    masterReportId: "4e621e3c-d5f2-479a-8814-337ea04b1cd1",
    category: "issue",
    title: "Uneven paving by the bars",
    description: "People keep tripping on the way to the square.",
    location: [16.9329, 52.4071],
    createdAt: "2026-09-15T22:48:00Z",
    photoKeys: [],
  },
  {
    id: "32cc33dd-44ee-4a55-8f66-7700aa11bb22",
    userId: USERS.kasia,
    masterReportId: "4e621e3c-d5f2-479a-8814-337ea04b1cd1",
    category: "issue",
    title: "Broken setts, Wroclawska",
    description: "Worse after the weekend, a few are loose now.",
    location: [16.9332, 52.407],
    createdAt: "2026-09-22T10:12:00Z",
    photoKeys: [],
  },
  {
    id: "33dd44ee-55ff-4b66-8077-00aa11bb22cc",
    userId: USERS.marek,
    masterReportId: "5f732f4d-e603-48ab-9925-448fb105ce02",
    category: "improvement",
    title: "Room for a bike lane on Paderewskiego",
    description: "The street is wide enough if the parking bay goes.",
    location: [16.9306, 52.4079],
    createdAt: "2026-09-24T08:45:00Z",
    photoKeys: [],
  },
  {
    id: "34ee55ff-6600-4c77-8188-11bb22cc33dd",
    userId: USERS.anna,
    masterReportId: "5f732f4d-e603-48ab-9925-448fb105ce02",
    category: "improvement",
    title: "Cycling to the square is unpleasant",
    description: "Riding here means taking the lane with the buses.",
    location: [16.9304, 52.4077],
    createdAt: "2026-09-27T17:33:00Z",
    photoKeys: [],
  },
  {
    id: "35ff6600-7711-4d88-8299-22cc33dd44ee",
    userId: USERS.tomasz,
    masterReportId: "6084305e-f714-49bc-8a36-5590c216df13",
    category: "issue",
    title: "Bench missing slats",
    description: "Nobody can sit on it facing the church.",
    location: [16.9346, 52.4061],
    createdAt: "2026-09-30T11:05:00Z",
    photoKeys: ["reports/2026/09/kolegiacki-tomasz-1.jpg"],
  },
  {
    id: "36007711-8822-4e99-83aa-33dd44ee55ff",
    userId: USERS.kasia,
    masterReportId: "7195416f-0825-40cd-9b47-66a1d327e024",
    category: "issue",
    title: "Pavement blocked by parked cars",
    description: "Had to step into the road with the pushchair again.",
    location: [16.9361, 52.4071],
    createdAt: "2026-09-08T13:20:00Z",
    photoKeys: ["reports/2026/09/wozna-kasia-1.jpg"],
  },
  {
    id: "37118822-9933-4faa-84bb-44ee55ff6600",
    userId: USERS.ewa,
    masterReportId: "7195416f-0825-40cd-9b47-66a1d327e024",
    category: "issue",
    title: "Cars on the footway, Wozna",
    description: "Every morning, both sides of the street.",
    location: [16.9359, 52.4069],
    createdAt: "2026-09-13T08:02:00Z",
    photoKeys: [],
  },
  {
    id: "38229933-aa44-40bb-85cc-55ff66007711",
    userId: USERS.piotr,
    masterReportId: "82a65270-1936-41de-8c58-77b2e438f135",
    category: "improvement",
    title: "Zydowska is dark after sunset",
    description: "The lane feels unsafe walking back from the square.",
    location: [16.9353, 52.4096],
    createdAt: "2026-09-17T21:10:00Z",
    photoKeys: [],
  },
  {
    id: "3933aa44-bb55-41cc-86dd-660077118822",
    userId: USERS.marek,
    masterReportId: "82a65270-1936-41de-8c58-77b2e438f135",
    category: "improvement",
    title: "Lamps between the square and the synagogue",
    description: "Two or three along the lane would do it.",
    location: [16.9351, 52.4094],
    createdAt: "2026-09-21T20:27:00Z",
    photoKeys: [],
  },
  {
    id: "3a44bb55-cc66-42dd-87ee-771188229933",
    userId: USERS.anna,
    masterReportId: "93b76381-2a47-42ef-9d69-88c3f549a246",
    category: "issue",
    title: "Drain backing up on Szkolna",
    description: "Water sits across the crossing for hours after rain.",
    location: [16.9319, 52.4067],
    createdAt: "2026-10-01T07:40:00Z",
    photoKeys: [],
  },
  {
    id: "3b55cc66-dd77-43ee-88ff-88229933aa44",
    userId: USERS.tomasz,
    masterReportId: "a4c87492-3b58-43f0-8e7a-99d4061ab357",
    category: "improvement",
    title: "Trees on Polwiejska",
    description: "There is no shade on the whole shopping street.",
    location: [16.9296, 52.4036],
    createdAt: "2026-09-19T16:25:00Z",
    photoKeys: [],
  },
  {
    id: "3c66dd77-ee88-44ff-8900-9933aa44bb55",
    userId: USERS.kasia,
    masterReportId: "a4c87492-3b58-43f0-8e7a-99d4061ab357",
    category: "improvement",
    title: "Planters would help on Polwiejska",
    description: "Even tubs would break up the paving.",
    location: [16.9294, 52.4034],
    createdAt: "2026-09-23T12:54:00Z",
    photoKeys: [],
  },
  {
    id: "3d77ee88-ff99-4500-8a11-aa44bb55cc66",
    userId: USERS.ewa,
    masterReportId: "a4c87492-3b58-43f0-8e7a-99d4061ab357",
    category: "improvement",
    title: "Nowhere shaded to stop on Polwiejska",
    description: "In summer the street is unbearable in the afternoon.",
    location: [16.9297, 52.4033],
    createdAt: "2026-09-29T14:41:00Z",
    photoKeys: [],
  },
  {
    id: "3e88ff99-0011-4611-8b22-bb55cc66dd77",
    userId: USERS.piotr,
    masterReportId: "b5d985a3-4c69-4401-8f8b-aae5172bc468",
    category: "improvement",
    title: "Shelter at the eastbound Sw. Marcin stop",
    description: "Nothing to stand under when it rains.",
    location: [16.9246, 52.4046],
    createdAt: "2026-10-02T09:15:00Z",
    photoKeys: [],
  },

  // filed but not yet classified, so it has no master and the map does not draw it
  {
    id: "288899aa-bbcd-478e-8f9a-012345678901",
    userId: USERS.kasia,
    masterReportId: null,
    category: "issue",
    title: "Loose paving slab on Polwiejska",
    description: "A slab rocks underfoot outside the shopping centre entrance.",
    location: [16.9315, 52.4038],
    createdAt: "2026-10-03T08:20:00Z",
    photoKeys: [],
  },
];

/**
 * Folds filings into their masters, the way a query joining `reports` onto
 * `master_reports` would. Filings with no master are left out: they have not been
 * classified yet, so there is nothing to draw them under.
 */
export function aggregateReports(
  masters: MasterReport[],
  reports: Report[],
): AggregatedReport[] {
  const byMaster = new globalThis.Map<string, Report[]>();
  for (const report of reports) {
    if (!report.masterReportId) {
      continue;
    }
    const group = byMaster.get(report.masterReportId);
    if (group) {
      group.push(report);
    } else {
      byMaster.set(report.masterReportId, [report]);
    }
  }

  return masters.map((master) => {
    const group = [...(byMaster.get(master.id) ?? [])].sort((left, right) =>
      left.createdAt.localeCompare(right.createdAt),
    );
    return {
      ...master,
      reports: group,
      // a master always stands for at least itself, even before any filing joins it
      reportCount: Math.max(group.length, 1),
      lastReportedAt: group.at(-1)?.createdAt ?? master.createdAt,
    };
  });
}

/** What the map draws: one pin per master, ordered most-reported first. */
export const POZNAN_REPORTS: AggregatedReport[] = aggregateReports(
  MASTER_REPORTS,
  REPORTS,
).sort((left, right) => right.reportCount - left.reportCount);
