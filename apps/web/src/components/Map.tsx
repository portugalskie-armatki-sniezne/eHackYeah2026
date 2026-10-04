import {
  useCallback,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";
import {
  Map as MapLibreMap,
  setWorkerUrl,
  type FillExtrusionLayerSpecification,
} from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import MapToolbar, { type BasemapId } from "./MapToolbar";
import MapCursor from "./MapCursor";
import UserPosition from "./UserPosition";
import useUserPosition from "./useUserPosition";
import EventMarkers, {
  DEFAULT_PIN_CATEGORY,
  type EventPin,
} from "./EventMarkers";
import PinDialog, { type PinDraft } from "./PinDialog";
import MarkerDialog from "./MarkerDialog";
import ReportClusters from "./ReportClusters";
import { isClusterAt } from "./reportClusterHit";
import { createTiltPrewarmer } from "./mapPrewarm";
import {
  readLastKnownPosition,
  saveLastKnownPosition,
} from "./lastKnownPosition";
import {
  reportsApi,
  type MasterReport,
  type MasterReportDetail,
  type Report,
  type ReportCategoryName,
  type ReportLocation,
} from "../api/reports";
import { useSession } from "../api/session";
import "./Map.css";

// maplibre resolves its worker next to its own file at runtime, which the bundler cannot see
setWorkerUrl(maplibreWorkerUrl);

// Where the map opens when the device has never been located in this browser.
const MALOPOLSKA: [number, number] = [20.25, 49.85];
// wide enough to open on Małopolska, not one city
const ZOOM = 7;
// Close enough to read the street you are standing on.
const LOCATE_ZOOM = 16.5;
const TILTED_VIEW = { pitch: 55, bearing: -20 };
const FLAT_VIEW = { pitch: 0, bearing: 0 };
// Looking straight down is a flat drawn plan, so heights stay hidden until the
// camera has leaned well off top-down, then cross-fade up to the block model.
const EXTRUSION_FADE_START_PITCH = 22;
const EXTRUSION_FULL_PITCH = 50;
const EXTRUSION_OPACITY = 0.95;

// The phone layout, as the chrome's stylesheets draw it. There the "+" tile is
// the way to file a report, so a tap on the map only pans.
const PHONE_LAYOUT = "(max-width: 40rem)";

const BASEMAP_STYLES: Record<BasemapId, string> = {
  streets: "https://tiles.openfreemap.org/styles/bright",
};

// report_categories.id to the name the pin's pictogram is picked by
type CategoryNames = ReadonlyMap<number, ReportCategoryName>;

const CATEGORY_NAMES: readonly ReportCategoryName[] = ["improvement", "issue"];

function isReportCategory(name: string): name is ReportCategoryName {
  return (CATEGORY_NAMES as readonly string[]).includes(name);
}

// The sheet has no title field, so a report is titled by the start of its
// description: the first line, cut where a sentence or the limit ends.
const TITLE_LIMIT = 80;

function titleFrom(description: string): string {
  const firstLine = description.split(/\r?\n/, 1)[0].trim();
  const sentence = firstLine.match(/^.*?[.!?](?=\s|$)/)?.[0] ?? firstLine;
  if (sentence.length <= TITLE_LIMIT) return sentence;
  const cut = sentence.slice(0, TITLE_LIMIT);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), 40)).trimEnd()}…`;
}

// The map draws master reports, so each pin is an aggregate: its pictogram comes
// from the category and its count from the filings folded into it.
function masterPin(
  master: MasterReport | MasterReportDetail,
  categories: CategoryNames,
  imageUrl: string | null = null,
): EventPin {
  const photo = "photos" in master ? master.photos[0] : undefined;
  return {
    id: master.id,
    lngLat: [master.location.longitude, master.location.latitude],
    // a pin's label is a one-liner, so the master's title stands in for it
    description: master.title,
    image: null,
    imageUrl: imageUrl ?? (photo ? reportsApi.photoUrl(photo) : null),
    category: categories.get(master.report_category_id) ?? DEFAULT_PIN_CATEGORY,
    reportCount: master.report_count,
  };
}

// a pin already on the map is replaced, so a master that took in another
// filing shows the new count rather than a second pin
function upsertPin(pins: EventPin[], pin: EventPin): EventPin[] {
  const index = pins.findIndex((existing) => existing.id === pin.id);
  if (index === -1) {
    return [...pins, pin];
  }
  const next = [...pins];
  next[index] = { ...pin, imageUrl: pin.imageUrl ?? pins[index].imageUrl };
  return next;
}

type PaintProperty = Parameters<MapLibreMap["setPaintProperty"]>[1];
type PaintValue = Parameters<MapLibreMap["setPaintProperty"]>[2];

// Scaffolding palette for the "bright" basemap: ink construction lines over paper,
// with amber reserved for the primary roads so it echoes the chrome's offset blocks.
// Entries are [layer id, paint property, value].
const PAPER = "#efe8d6";
const PAPER_BRIGHT = "#f8f3e6";
const INK = "#141414";
const INK_SOFT = "#4a4a46";
const INK_LINE = "#a89f8e";
const INK_LINE_FAINT = "#cbc2b0";
const HATCH_FILL = "#f3ede0";
const HATCH_LINE = "rgba(20, 20, 20, 0.22)";
const AMBER = "#efb33f";
const AMBER_SOFT = "#f7dba6";
const AMBER_GHOST = "#fbeed2";
const AMBER_LINE = "#c99a46";
const WATER = "#5096C4";
const WATER_INK = "#36617f";
const SAGE = "#e0dfc6";

type PaintOverride = [string, PaintProperty, PaintValue];

const ROAD_PALETTE: PaintOverride[] = [];
// Motorways and trunks are the amber blocks; everything below them is paper on ink.
for (const prefix of ["highway", "bridge", "tunnel"]) {
  ROAD_PALETTE.push(
    [`${prefix}-motorway`, "line-color", AMBER],
    [`${prefix}-motorway-link`, "line-color", AMBER_SOFT],
    [`${prefix}-motorway-casing`, "line-color", AMBER_LINE],
    [`${prefix}-motorway-link-casing`, "line-color", AMBER_LINE],
    [`${prefix}-link`, "line-color", AMBER_GHOST],
    [`${prefix}-link-casing`, "line-color", INK_LINE],
    [`${prefix}-secondary-tertiary`, "line-color", PAPER_BRIGHT],
    [`${prefix}-secondary-tertiary-casing`, "line-color", INK_LINE],
    [`${prefix}-minor`, "line-color", PAPER_BRIGHT],
    [`${prefix}-minor-casing`, "line-color", INK_LINE_FAINT],
    [`${prefix}-path`, "line-color", INK_LINE],
    [`${prefix}-railway`, "line-color", INK_LINE],
    [`${prefix}-railway-hatching`, "line-color", INK_LINE],
  );
}
ROAD_PALETTE.push(
  ["highway-trunk", "line-color", AMBER_SOFT],
  ["highway-trunk-casing", "line-color", AMBER_LINE],
  ["highway-primary", "line-color", AMBER_GHOST],
  ["highway-primary-casing", "line-color", AMBER_LINE],
  ["bridge-trunk-primary", "line-color", AMBER_SOFT],
  ["bridge-trunk-primary-casing", "line-color", AMBER_LINE],
  ["tunnel-trunk-primary", "line-color", AMBER_GHOST],
  ["tunnel-trunk-primary-casing", "line-color", AMBER_LINE],
  ["highway-area", "fill-color", PAPER_BRIGHT],
  ["highway-area", "fill-outline-color", INK_LINE_FAINT],
  ["railway", "line-color", INK_LINE],
  ["railway-hatching", "line-color", INK_LINE],
  ["railway-service", "line-color", INK_LINE_FAINT],
  ["railway-service-hatching", "line-color", INK_LINE_FAINT],
  ["railway-transit", "line-color", INK_LINE],
  ["railway-transit-hatching", "line-color", INK_LINE],
);

// Named places keep their lettering; the modern sprite pins go.
const POI_LAYERS = ["poi_r7", "poi_r1"];

function labelColors(ids: string[], color: string): PaintOverride[] {
  return ids.flatMap((id): PaintOverride[] => [
    [id, "text-color", color],
    [id, "text-halo-color", PAPER_BRIGHT],
  ]);
}

const LABEL_PALETTE: PaintOverride[] = [
  ...POI_LAYERS.map((id): PaintOverride => [id, "icon-opacity", 0]),
  ...labelColors(
    [
      "label_city_capital",
      "label_city",
      "label_town",
      "label_village",
      "label_state",
      "label_other",
    ],
    INK,
  ),
  ...labelColors(
    [
      ...POI_LAYERS,
      "highway-name-major",
      "highway-name-minor",
      "highway-name-path",
      "airport",
    ],
    INK_SOFT,
  ),
  ...labelColors(
    ["waterway_line_label", "water_name_point_label", "water_name_line_label"],
    WATER_INK,
  ),
];

const LIGHT_PALETTE: PaintOverride[] = [
  ["background", "background-color", PAPER],
  ["water", "fill-color", WATER],
  ["water-intermittent", "fill-color", WATER],
  ["waterway-river", "line-color", WATER],
  ["waterway-river-intermittent", "line-color", WATER],
  ["waterway-stream-canal", "line-color", WATER],
  ["waterway-stream-canal-intermittent", "line-color", WATER],
  ["waterway-other", "line-color", WATER],
  ["waterway-other-intermittent", "line-color", WATER],
  ["waterway_tunnel", "line-color", WATER],
  ["ferry", "line-color", WATER_INK],
  ["park", "fill-color", SAGE],
  ["landcover-grass", "fill-color", SAGE],
  ["landcover-grass-park", "fill-color", SAGE],
  ["landcover-wood", "fill-color", "#cfd6c0"],
  ["landcover-sand", "fill-color", AMBER_GHOST],
  ["landuse-residential", "fill-color", "hsla(40, 18%, 90%, 0.45)"],
  ["landuse-suburb", "fill-color", "hsla(40, 18%, 90%, 0.45)"],
  ["landuse-commercial", "fill-color", "hsla(40, 70%, 88%, 0.3)"],
  ["landuse-industrial", "fill-color", "hsla(40, 20%, 86%, 0.5)"],
  ["landuse-cemetery", "fill-color", "#e6e7df"],
  ["landuse-hospital", "fill-color", "#efe9e3"],
  ["landuse-school", "fill-color", "#eee9e0"],
  ["landuse-railway", "fill-color", "hsla(40, 10%, 86%, 0.5)"],
  ["aeroway-area", "fill-color", PAPER_BRIGHT],
  ["aeroway-runway", "line-color", PAPER_BRIGHT],
  ["aeroway-taxiway", "line-color", PAPER_BRIGHT],
  ["aeroway-runway-casing", "line-color", INK_LINE],
  ["aeroway-taxiway-casing", "line-color", INK_LINE],
  ["boundary_3", "line-color", INK_LINE],
  ["boundary_2", "line-color", INK_SOFT],
  ...ROAD_PALETTE,
  ...LABEL_PALETTE,
  // Flat footprints read as drawn plans: paper fill, ink outline.
  ["building", "fill-color", HATCH_FILL],
];

type LayoutProperty = Parameters<MapLibreMap["setLayoutProperty"]>[1];
type LayoutValue = Parameters<MapLibreMap["setLayoutProperty"]>[2];
type LayoutOverride = [string, LayoutProperty, LayoutValue];

// Old-map lettering: italic street names, spaced capitals for settlements, and
// none of the shields, transit stops or minor pins that date the basemap.
const LAYOUT_OVERRIDES: LayoutOverride[] = [
  ["highway-name-major", "text-font", ["Noto Sans Italic"]],
  ["highway-name-minor", "text-font", ["Noto Sans Italic"]],
  ["highway-name-path", "text-font", ["Noto Sans Italic"]],
  ...[
    "label_city_capital",
    "label_city",
    "label_town",
    "label_village",
  ].flatMap((id): LayoutOverride[] => [
    [id, "text-transform", "uppercase"],
    [id, "text-letter-spacing", 0.15],
  ]),
  ...[
    "poi_r20",
    "poi_transit",
    "highway-shield-non-us",
    "highway-shield-us-interstate",
    "road_shield_us",
    "road_oneway",
    "road_oneway_opposite",
  ].map((id): LayoutOverride => [id, "visibility", "none"]),
];

const BUILDINGS_3D_BEFORE = "road_oneway";

const BUILDINGS_3D: FillExtrusionLayerSpecification = {
  id: "building-3d",
  type: "fill-extrusion",
  source: "openmaptiles",
  "source-layer": "building",
  minzoom: 14,
  paint: {
    // Low blocks are paper; the tallest pick up the chrome's amber.
    "fill-extrusion-color": [
      "interpolate",
      ["linear"],
      ["coalesce", ["get", "render_height"], 0],
      0,
      "#f2ecdd",
      18,
      "#e4dcc8",
      45,
      "#d3c9b2",
      90,
      "#e9c67c",
    ],
    "fill-extrusion-height": [
      "interpolate",
      ["linear"],
      ["zoom"],
      14,
      0,
      15,
      ["coalesce", ["get", "render_height"], 4],
    ],
    "fill-extrusion-base": [
      "interpolate",
      ["linear"],
      ["zoom"],
      14,
      0,
      15,
      ["coalesce", ["get", "render_min_height"], 0],
    ],
    // Driven by the camera pitch; see syncExtrusionsToPitch.
    "fill-extrusion-opacity": 0,
    "fill-extrusion-vertical-gradient": true,
  },
};

// The hatched footprints read as a plan until the camera leans over and the
// blocks rise out of them. Opacity is a uniform, so updating it per pitch frame
// is cheap.
function syncExtrusionsToPitch(map: MapLibreMap) {
  if (!map.getLayer(BUILDINGS_3D.id)) {
    return;
  }
  const span = EXTRUSION_FULL_PITCH - EXTRUSION_FADE_START_PITCH;
  const t = Math.min(
    Math.max((map.getPitch() - EXTRUSION_FADE_START_PITCH) / span, 0),
    1,
  );
  map.setPaintProperty(
    BUILDINGS_3D.id,
    "fill-extrusion-opacity",
    t * EXTRUSION_OPACITY,
  );
}

// Diagonal ink hatching for building footprints, drawn once and handed to the
// style as a sprite so the flat view looks like an engraved plan.
function makeHatchPattern(): ImageData {
  const ratio = 2;
  const size = 8 * ratio;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return new ImageData(size, size);
  }
  ctx.fillStyle = HATCH_FILL;
  ctx.fillRect(0, 0, size, size);
  ctx.strokeStyle = HATCH_LINE;
  ctx.lineWidth = ratio;
  ctx.lineCap = "square";
  ctx.beginPath();
  // Two strokes so the hatch tiles seamlessly across the pattern edge.
  ctx.moveTo(-size / 2, size);
  ctx.lineTo(size / 2, 0);
  ctx.moveTo(size / 2, size);
  ctx.lineTo(size * 1.5, 0);
  ctx.stroke();
  return ctx.getImageData(0, 0, size, size);
}

const HATCH_IMAGE = "building-hatch";

function applyLightTheme(map: MapLibreMap) {
  for (const [layer, property, value] of LIGHT_PALETTE) {
    if (map.getLayer(layer)) {
      map.setPaintProperty(layer, property, value);
    }
  }

  // The basemap's fake 2.5D roof offset fights with real extrusions.
  if (map.getLayer("building-top")) {
    map.setLayoutProperty("building-top", "visibility", "none");
  }

  if (!map.hasImage(HATCH_IMAGE)) {
    map.addImage(HATCH_IMAGE, makeHatchPattern(), { pixelRatio: 2 });
  }
  if (map.getLayer("building")) {
    map.setPaintProperty("building", "fill-pattern", HATCH_IMAGE);
  }
  for (const [layer, property, value] of LAYOUT_OVERRIDES) {
    if (map.getLayer(layer)) {
      map.setLayoutProperty(layer, property, value);
    }
  }

  if (!map.getLayer(BUILDINGS_3D.id)) {
    map.addLayer(BUILDINGS_3D, BUILDINGS_3D_BEFORE);
  }
  syncExtrusionsToPitch(map);

  // Soft, viewport-fixed light so block faces shade like an inked axonometric
  // drawing and stay consistent as the map rotates.
  map.setLight({
    anchor: "viewport",
    color: PAPER_BRIGHT,
    intensity: 0.28,
    position: [1.15, 210, 30],
  });

  // Warm grey paper sky for when the camera is pitched enough to see the horizon.
  map.setSky({
    "sky-color": "#e3ddcd",
    "horizon-color": PAPER,
    "fog-color": PAPER,
    "sky-horizon-blend": 0.6,
    "horizon-fog-blend": 0.8,
    "fog-ground-blend": 0.9,
  });
}

type MapProps = {
  /** Called when a signed-out visitor starts a report. */
  onSignInRequired: () => void;
};

export default function Map({ onSignInRequired }: MapProps) {
  const session = useSession();
  const containerRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [tilted, setTilted] = useState(false);
  const [styleReady, setStyleReady] = useState(false);
  const [pins, setPins] = useState<EventPin[]>([]);
  // why the last photo report did not save, until the next one is tried
  const [saveError, setSaveError] = useState<string | null>(null);
  const photoSavingRef = useRef(false);
  // filled by the first load; a report saved before then falls back to the default
  const categoriesRef = useRef<CategoryNames>(new globalThis.Map());
  // Which reports escaped grouping, so only those get a pin. Null until the
  // clusters have first reported, when every pin is drawn.
  const [ungroupedIds, setUngroupedIds] = useState<ReadonlySet<string> | null>(
    null,
  );
  // the clicked point while its marker sheet is open
  const [draftLngLat, setDraftLngLat] = useState<[number, number] | null>(null);
  // the clicked pin's master while its report sheet is open
  const [openPinId, setOpenPinId] = useState<string | null>(null);
  const { fix } = useUserPosition();
  // The camera eases to the first fix so the dot isn't off-screen, then leaves
  // the view alone: later fixes only move the dot.
  const centredRef = useRef(false);

  // Reports are saved for the signed-in user. While the session is still
  // being restored the answer is not known yet, so nothing happens.
  const canStartReport = useCallback(() => {
    if (session.status === "signed-out") onSignInRequired();
    return session.status === "signed-in";
  }, [session.status, onSignInRequired]);
  const handleMapClick = useEffectEvent((lngLat: [number, number]) => {
    if (canStartReport()) setDraftLngLat(lngLat);
  });

  // The pins come from the master reports, fetched once on load and in full,
  // since the map opens on the whole city.
  useEffect(() => {
    const controller = new AbortController();
    async function loadMasterReports() {
      try {
        const [categories, masters] = await Promise.all([
          reportsApi.categories(controller.signal),
          reportsApi.allMasterReports(controller.signal),
        ]);
        const names = new globalThis.Map<number, ReportCategoryName>();
        for (const category of categories) {
          if (isReportCategory(category.name)) {
            names.set(category.id, category.name);
          }
        }
        categoriesRef.current = names;
        // most-reported first, so the pin numbering follows how much a place is reported
        const loaded = [...masters]
          .sort((left, right) => right.report_count - left.report_count)
          .map((master) => masterPin(master, names));
        setPins((current) => loaded.reduce(upsertPin, current));
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Could not load the map's reports.", error);
      }
    }
    void loadMasterReports();
    return () => controller.abort();
  }, []);

  // A saved report is drawn as the master it was filed under, so a filing that
  // joined an existing issue bumps that pin's count instead of adding one. The
  // chosen photo stands in until the master's own photos are seen.
  const pinForSavedReport = useCallback(
    async (report: Report, imageUrl: string | null): Promise<EventPin> => {
      const categories = categoriesRef.current;
      if (report.master_report_id) {
        try {
          const master = await reportsApi.masterReport(report.master_report_id);
          return masterPin(master, categories, imageUrl);
        } catch (error) {
          console.error("Could not load the saved report's master.", error);
        }
      }
      return {
        id: report.id,
        lngLat: [report.location.longitude, report.location.latitude],
        description: report.description,
        image: null,
        imageUrl,
        category:
          categories.get(report.report_category_id) ?? DEFAULT_PIN_CATEGORY,
        reportCount: 1,
      };
    },
    [],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    // The map opens on the device's position: the place it was last seen if this
    // browser knows one, and the region view until the first fix lands otherwise.
    const lastKnown = readLastKnownPosition();

    const map = new MapLibreMap({
      container,
      style: BASEMAP_STYLES.streets,
      center: lastKnown ?? MALOPOLSKA,
      zoom: lastKnown ? LOCATE_ZOOM : ZOOM,
      ...FLAT_VIEW,
      maxPitch: 70,
      attributionControl: false,
    });

    // Pulls the tilted view's tiles into the cache while the flat view is idle, so
    // the 3D toggle doesn't stream in a screenful of blank ground.
    const prewarmer = createTiltPrewarmer(map, TILTED_VIEW);

    // Runs on initial load and again after any setStyle, so the overrides survive basemap swaps.
    map.on("style.load", () => {
      applyLightTheme(map);
      setStyleReady(true);
    });
    // Keep the toggle honest when the user tilts with ctrl+drag / two-finger drag.
    map.on("pitch", () => {
      if (!prewarmer.isMeasuring()) {
        syncExtrusionsToPitch(map);
      }
    });
    map.on("pitchend", () => {
      if (!prewarmer.isMeasuring()) {
        setTilted(map.getPitch() > EXTRUSION_FADE_START_PITCH);
      }
    });
    map.on("idle", prewarmer.prewarm);
    // A click on the sheet opens the marker sheet for that point. MapLibre only
    // fires click when the pointer hasn't moved past its tolerance, so drags
    // never open it.
    map.on("click", (event) => {
      if (window.matchMedia(PHONE_LAYOUT).matches) {
        return;
      }
      const target = event.originalEvent.target as Element | null;
      // clicks land on the map even when they hit an existing pin
      if (target?.closest(".maplibregl-marker")) {
        return;
      }
      // a cluster is drawn on the canvas, so only a feature query sees it; it
      // opens on click rather than starting a report on top of the reports it holds
      if (isClusterAt(map, event.point)) {
        return;
      }
      handleMapClick([event.lngLat.lng, event.lngLat.lat]);
    });

    map
      .getCanvas()
      .setAttribute(
        "aria-label",
        "Map. Use the arrow keys to pan and the plus and minus keys to zoom.",
      );

    mapRef.current = map;

    return () => {
      prewarmer.dispose();
      setStyleReady(false);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const flyToFix = useCallback((lngLat: [number, number]) => {
    mapRef.current?.flyTo({ center: lngLat, zoom: LOCATE_ZOOM });
  }, []);

  // The first fix is the starting view, so the camera is set there outright
  // rather than flown across the city; later recentres animate.
  useEffect(() => {
    if (!fix || centredRef.current) {
      return;
    }
    centredRef.current = true;
    mapRef.current?.jumpTo({ center: fix.lngLat, zoom: LOCATE_ZOOM });
    saveLastKnownPosition(fix.lngLat);
  }, [fix]);

  const handleRecenterOnMe = useCallback(() => {
    if (fix) {
      flyToFix(fix.lngLat);
    }
  }, [fix, flyToFix]);

  const handleCloseDraft = useCallback(() => setDraftLngLat(null), []);
  const handleClosePin = useCallback(() => setOpenPinId(null), []);
  // the sheet is keyed by the master, and takes the pin's category with it
  const openPin = openPinId
    ? (pins.find((pin) => pin.id === openPinId) ?? null)
    : null;
  // The sheet has no category field yet, so a new report starts in the default
  // category, looked up by name from the categories the first load brought, or
  // fetched now when it has not run yet. The client sends the user's token.
  const saveReport = useCallback(
    async (
      description: string,
      location: ReportLocation,
      image: File | null,
      categoryName: ReportCategoryName = DEFAULT_PIN_CATEGORY,
    ) => {
      let categoryId: number | undefined;
      for (const [id, name] of categoriesRef.current) {
        if (name === categoryName) categoryId = id;
      }
      if (categoryId === undefined) {
        categoryId = (await reportsApi.categories()).find(
          (category) => category.name === categoryName,
        )?.id;
      }
      if (categoryId === undefined) {
        throw new Error("The report categories could not be loaded.");
      }
      return reportsApi.create({
        report_category_id: categoryId,
        title: titleFrom(description),
        description,
        location,
        photos: image ? [image] : [],
      });
    },
    [],
  );

  const handleAddPin = useCallback(
    async (draft: PinDraft) => {
      if (!draftLngLat) {
        return;
      }
      const categoryName: ReportCategoryName =
        draft.category ?? DEFAULT_PIN_CATEGORY;
      const report = await saveReport(
        draft.description,
        { longitude: draftLngLat[0], latitude: draftLngLat[1] },
        draft.image,
        categoryName,
      );
      const pin = await pinForSavedReport(report, draft.imageUrl);
      setPins((current) => upsertPin(current, pin));
    },
    [draftLngLat, saveReport, pinForSavedReport],
  );

  // The "+" tile skips the sheet: the photo is the report, filed where the
  // device stands, and the camera goes there so the new pin is in view.
  const handlePhotoReport = useCallback(
    async (photo: File) => {
      if (!fix || photoSavingRef.current) {
        return;
      }
      photoSavingRef.current = true;
      setSaveError(null);
      try {
        const report = await saveReport(
          "Photo report",
          { longitude: fix.lngLat[0], latitude: fix.lngLat[1] },
          photo,
        );
        const pin = await pinForSavedReport(report, URL.createObjectURL(photo));
        setPins((current) => upsertPin(current, pin));
        flyToFix(fix.lngLat);
      } catch (error) {
        setSaveError(
          error instanceof Error
            ? error.message
            : "Could not save the photo report.",
        );
      } finally {
        photoSavingRef.current = false;
      }
    },
    [fix, flyToFix, saveReport, pinForSavedReport],
  );

  const handleZoomIn = useCallback(() => mapRef.current?.zoomIn(), []);
  const handleZoomOut = useCallback(() => mapRef.current?.zoomOut(), []);
  const handleRecenter = useCallback(() => {
    mapRef.current?.flyTo({
      center: MALOPOLSKA,
      zoom: ZOOM,
      ...(tilted ? TILTED_VIEW : FLAT_VIEW),
    });
  }, [tilted]);
  const handleToggleTilt = useCallback(() => {
    const next = !tilted;
    setTilted(next);
    mapRef.current?.easeTo({
      ...(next ? TILTED_VIEW : FLAT_VIEW),
      duration: 600,
    });
  }, [tilted]);

  return (
    <section className="map" aria-label="Map">
      {saveError && (
        <aside className="map__notice" role="alert">
          {saveError}
        </aside>
      )}
      <div className="map__frame" ref={frameRef}>
        <div className="map__canvas" ref={containerRef} />
      </div>
      <MapToolbar
        tilted={tilted}
        onToggleTilt={handleToggleTilt}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onRecenter={handleRecenter}
        onRecenterOnMe={handleRecenterOnMe}
        canRecenterOnMe={fix !== null}
        onPhotoReportStart={canStartReport}
        onPhotoReport={handlePhotoReport}
      />
      <UserPosition mapRef={mapRef} styleReady={styleReady} fix={fix} />
      <ReportClusters
        mapRef={mapRef}
        styleReady={styleReady}
        pins={pins}
        onUngroupedChange={setUngroupedIds}
      />
      <EventMarkers
        mapRef={mapRef}
        styleReady={styleReady}
        pins={pins}
        ungroupedIds={ungroupedIds}
        draftLngLat={draftLngLat}
        onPinClick={setOpenPinId}
      />
      {draftLngLat && (
        <PinDialog
          lngLat={draftLngLat}
          onClose={handleCloseDraft}
          onAdd={handleAddPin}
        />
      )}
      {openPin && (
        <MarkerDialog
          key={openPin.id}
          masterId={openPin.id}
          category={openPin.category}
          onClose={handleClosePin}
          onSignInRequired={onSignInRequired}
        />
      )}
      <MapCursor targetRef={frameRef} />
    </section>
  );
}
