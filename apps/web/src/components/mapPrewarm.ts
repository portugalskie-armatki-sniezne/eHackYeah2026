import type { Map as MapLibreMap, OverscaledTileID, Source } from "maplibre-gl";

const PREFETCH_CONCURRENCY = 6;
const PREFETCH_LIMIT = 192;
const DEFAULT_TILE_SIZE = 512;

type TiledSource = {
  tiles: string[];
  tileSize?: number;
  minzoom?: number;
  maxzoom?: number;
  scheme?: string | null;
  roundZoom?: boolean;
  hasTile?: (tileID: OverscaledTileID) => boolean;
};

type CameraView = {
  pitch: number;
  bearing: number;
};

export type TiltPrewarmer = {
  isMeasuring: () => boolean;
  prewarm: () => void;
  dispose: () => void;
};

function isTiledSource(
  source: Source | undefined,
): source is Source & TiledSource {
  return Array.isArray((source as { tiles?: unknown } | undefined)?.tiles);
}

function tiledSources(map: MapLibreMap): TiledSource[] {
  const sources = map.getStyle()?.sources;
  if (!sources) {
    return [];
  }
  return Object.keys(sources)
    .map((id) => map.getSource(id))
    .filter(isTiledSource);
}

// Tile URLs for the camera as it currently stands, built the same way the source
// itself builds them so the prefetch and the real request share a cache entry.
function coveringTileUrls(
  map: MapLibreMap,
  source: TiledSource,
): Array<{ zoom: number; url: string }> {
  const pixelRatio = window.devicePixelRatio || 1;
  const tiles: Array<{ zoom: number; url: string }> = [];

  for (const tileID of map.coveringTiles({
    tileSize: source.tileSize ?? DEFAULT_TILE_SIZE,
    minzoom: source.minzoom,
    maxzoom: source.maxzoom,
    roundZoom: source.roundZoom,
  })) {
    if (source.hasTile && !source.hasTile(tileID)) {
      continue;
    }
    tiles.push({
      zoom: tileID.canonical.z,
      url: tileID.canonical.url(source.tiles, pixelRatio, source.scheme),
    });
  }

  return tiles;
}

export function createTiltPrewarmer(
  map: MapLibreMap,
  tiltedView: CameraView,
): TiltPrewarmer {
  const warmed = new Set<string>();
  const abort = new AbortController();
  let measuring = false;
  let fetching = false;
  let disposed = false;
  let lastCamera = "";

  const cameraKey = () => {
    const { lng, lat } = map.getCenter();
    return `${lng},${lat},${map.getZoom()},${map.getPitch()},${map.getBearing()}`;
  };

  // `jumpTo` only schedules a repaint, so doing both moves in one task means the
  // tilted camera is measured but never painted. It still fires move/pitch
  // events, hence `measuring`.
  const tiltedTileUrls = () => {
    const sources = tiledSources(map);
    if (sources.length === 0) {
      return [];
    }

    const alreadyVisible = new Set<string>();
    for (const source of sources) {
      for (const tile of coveringTileUrls(map, source)) {
        alreadyVisible.add(tile.url);
      }
    }

    const restore = {
      center: map.getCenter(),
      zoom: map.getZoom(),
      pitch: map.getPitch(),
      bearing: map.getBearing(),
    };

    const tilted = new Map<string, number>();
    measuring = true;
    try {
      map.jumpTo(tiltedView);
      for (const source of sources) {
        for (const tile of coveringTileUrls(map, source)) {
          tilted.set(tile.url, tile.zoom);
        }
      }
    } finally {
      map.jumpTo(restore);
      measuring = false;
    }

    return [...tilted]
      .filter(([url]) => !alreadyVisible.has(url) && !warmed.has(url))
      .sort(([, a], [, b]) => a - b)
      .slice(0, PREFETCH_LIMIT)
      .map(([url]) => url);
  };

  const fetchAll = async (urls: string[]) => {
    let next = 0;
    const worker = async () => {
      while (next < urls.length && !disposed) {
        const url = urls[next++];
        // Marked up front so a failing tile isn't retried on every idle.
        warmed.add(url);
        try {
          const response = await fetch(url, {
            credentials: "omit",
            signal: abort.signal,
          });
          // Drain the body so the response actually lands in the cache.
          await response.arrayBuffer();
        } catch {
          // Best effort — a cold tile just loads the slow way on toggle.
        }
      }
    };
    await Promise.all(
      Array.from(
        { length: Math.min(PREFETCH_CONCURRENCY, urls.length) },
        worker,
      ),
    );
  };

  const prewarm = () => {
    if (disposed || measuring || fetching) {
      return;
    }
    // Measuring restores the camera exactly, so the `idle` it triggers lands here
    // with an unchanged key and stops the loop.
    const camera = cameraKey();
    if (camera === lastCamera) {
      return;
    }
    lastCamera = camera;

    const urls = tiltedTileUrls();
    if (urls.length === 0) {
      return;
    }

    fetching = true;
    void fetchAll(urls).finally(() => {
      fetching = false;
    });
  };

  return {
    isMeasuring: () => measuring,
    prewarm,
    dispose: () => {
      disposed = true;
      abort.abort();
    },
  };
}
