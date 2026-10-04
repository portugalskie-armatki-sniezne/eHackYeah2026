import {
  getTourMap,
  type TourLayout,
  type TourMapBridge,
} from "./onboardingState";
import { readRoute, type Route } from "./useHashRoute";

/** An element the guide points at: a selector, or a lookup for one made late. */
export type TourTarget = string | (() => Element | null);

/** The sheets the guide opens over the map. */
export type TourSheet = "pin" | "photo" | "marker";

/** What has to be on screen before a step can be shown. */
export type TourScene = {
  route: Route;
  /** the sheet open over the page; any other one is closed */
  sheet?: TourSheet;
  /** phone only: the navbar's menu folded open */
  menu?: boolean;
  /** the map's filter list unfolded */
  filters?: boolean;
};

/** Thrown when a step has nothing to show, like a case on an empty map. */
export class SkipStep extends Error {}

/** Resolves after a while, or rejects as soon as the step is left. */
export function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason);
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

/** Polls until the check passes; false once the time is up. */
export async function waitFor(
  check: () => boolean,
  signal: AbortSignal,
  timeout = 5000,
): Promise<boolean> {
  const until = Date.now() + timeout;
  while (!check()) {
    if (Date.now() > until) return false;
    await sleep(100, signal);
  }
  return true;
}

function isShown(element: Element): boolean {
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

/** The target as it is on screen now; null while it is missing or hidden. */
export function resolveTarget(target: TourTarget): Element | null {
  const element =
    typeof target === "string" ? document.querySelector(target) : target();
  return element && isShown(element) ? element : null;
}

async function find(
  target: TourTarget,
  signal: AbortSignal,
  timeout = 5000,
): Promise<Element> {
  const until = Date.now() + timeout;
  for (;;) {
    const element = resolveTarget(target);
    if (element) return element;
    if (Date.now() > until) {
      throw new Error(`The guide could not find ${String(target)}.`);
    }
    await sleep(100, signal);
  }
}

/** The modal sheet on top, whose content is the only part that takes input. */
export function topModal(): HTMLDialogElement | null {
  const open = document.querySelectorAll<HTMLDialogElement>("dialog:modal");
  return open.length > 0 ? open[open.length - 1] : null;
}

/** Which of the guide's sheets is open, "other" for any other dialog. */
export function openSheet(): TourSheet | "other" | null {
  const dialog = topModal();
  if (!dialog) return null;
  if (dialog.classList.contains("marker-dialog")) return "marker";
  if (dialog.classList.contains("pin-dialog")) {
    return dialog.querySelector(".photo-report__preview") ? "photo" : "pin";
  }
  return "other";
}

/** Closes every modal sheet, so the page under it can be used. */
export function closeSheets() {
  for (const dialog of document.querySelectorAll<HTMLDialogElement>(
    "dialog:modal",
  )) {
    dialog.close();
  }
}

/** Closes the report sheets, which send for real once the guide is gone. */
export function closeReportSheets() {
  for (const dialog of document.querySelectorAll<HTMLDialogElement>(
    "dialog.pin-dialog[open]",
  )) {
    dialog.close();
  }
}

let samplePhoto: Promise<File> | null = null;

/** The photo the guide files its sample report with, fetched once. */
export function loadSamplePhoto(): Promise<File> {
  samplePhoto ??= fetch(`${import.meta.env.BASE_URL}onboarding/pothole.jpg`)
    .then((response) => {
      if (!response.ok) throw new Error("The sample photo is missing.");
      return response.blob();
    })
    .then((blob) => new File([blob], "pothole.jpg", { type: blob.type }));
  // a failed fetch is tried again by the next step that needs it
  samplePhoto.catch(() => {
    samplePhoto = null;
  });
  return samplePhoto;
}

async function waitForMap(signal: AbortSignal): Promise<TourMapBridge> {
  await waitFor(() => getTourMap() !== null, signal);
  const map = getTourMap();
  if (!map) throw new Error("The map is not on screen.");
  return map;
}

/** The point on the map a new report is dropped at, clear of the toolbar. */
export function draftPoint(): { x: number; y: number } {
  const frame = document.querySelector(".map__frame");
  const rect = frame?.getBoundingClientRect() ?? {
    left: 0,
    top: 0,
    width: window.innerWidth,
    height: window.innerHeight,
  };
  return {
    x: rect.left + rect.width * 0.38,
    y: rect.top + rect.height * 0.55,
  };
}

async function setExpanded(
  selector: string,
  expanded: boolean,
  signal: AbortSignal,
) {
  const toggle = resolveTarget(selector);
  if (!(toggle instanceof HTMLElement)) return;
  if ((toggle.getAttribute("aria-expanded") === "true") !== expanded) {
    toggle.click();
    await sleep(260, signal);
  }
}

/** Opens and closes what the step needs, from wherever the visitor left off. */
export async function applyScene(
  scene: TourScene,
  layout: TourLayout,
  signal: AbortSignal,
) {
  const wanted = scene.sheet ?? null;
  const open = openSheet();
  if (open !== null && (open !== wanted || readRoute() !== scene.route)) {
    closeSheets();
    await waitFor(() => openSheet() === null, signal, 2000);
  }
  if (readRoute() !== scene.route) {
    window.location.hash = `#${scene.route}`;
    await sleep(150, signal);
  }
  if (layout === "phone") {
    await setExpanded(".navbar__toggle", scene.menu ?? false, signal);
  }
  if (scene.route === "map") {
    await setExpanded(".map-filters__toggle", scene.filters ?? false, signal);
  }
  if (!wanted || openSheet() === wanted) return;

  const map = await waitForMap(signal);
  if (wanted === "pin") {
    const { x, y } = draftPoint();
    map.openDraftAt(x, y);
  } else if (wanted === "photo") {
    map.openPhotoDraft(await loadSamplePhoto());
  } else {
    const id = await topPin(signal);
    map.openPin(id);
  }
  await waitFor(() => openSheet() === wanted, signal);
}

/** The case the guide shows, once the map has loaded one. */
export async function topPin(signal: AbortSignal): Promise<string> {
  const map = await waitForMap(signal);
  await waitFor(() => map.topPinId() !== null, signal, 4000);
  const id = map.topPinId();
  if (!id) throw new SkipStep("The map has no case to show.");
  return id;
}

/** The pin drawn for the case the guide shows, while it is not in a group. */
export function topPinElement(): Element | null {
  const id = getTourMap()?.topPinId();
  return id
    ? document.querySelector(`[data-pin-id="${CSS.escape(id)}"]`)
    : null;
}

/** Where the drawn cursor is moved and pressed. */
export type TourCursor = {
  move: (x: number, y: number, signal: AbortSignal) => Promise<void>;
  press: (signal: AbortSignal) => Promise<void>;
};

/** What the auto tour does with the page, as a visitor would. */
export type Player = {
  signal: AbortSignal;
  wait: (ms: number) => Promise<void>;
  find: (target: TourTarget, timeout?: number) => Promise<Element>;
  /** like find, but null rather than a failure when it does not turn up */
  look: (target: TourTarget, timeout?: number) => Promise<Element | null>;
  /** moves the cursor over the element, scrolling it into view first */
  point: (target: TourTarget | Element) => Promise<Element>;
  pointAt: (x: number, y: number) => Promise<void>;
  /** points and presses without clicking, for what a click would misfire */
  tap: (target: TourTarget | Element) => Promise<Element>;
  click: (target: TourTarget | Element) => Promise<void>;
  /** replaces the field's text one letter at a time */
  type: (target: TourTarget, text: string) => Promise<void>;
  attach: (target: TourTarget, file: File) => Promise<void>;
};

// React tracks a field's value itself, so it is set past its own setter
function setFieldValue(
  field: HTMLInputElement | HTMLTextAreaElement,
  value: string,
) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value);
  field.dispatchEvent(new Event("input", { bubbles: true }));
}

function inView(rect: DOMRect): boolean {
  return (
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <= window.innerHeight &&
    rect.right <= window.innerWidth
  );
}

export function createPlayer(
  cursor: TourCursor,
  signal: AbortSignal,
  reducedMotion: boolean,
): Player {
  const wait = (ms: number) => sleep(ms, signal);
  const lookUp = (target: TourTarget | Element, timeout?: number) =>
    target instanceof Element
      ? Promise.resolve(target)
      : find(target, signal, timeout);

  const point = async (target: TourTarget | Element) => {
    const element = await lookUp(target);
    if (!inView(element.getBoundingClientRect())) {
      element.scrollIntoView({
        block: "center",
        behavior: reducedMotion ? "auto" : "smooth",
      });
      await wait(reducedMotion ? 50 : 450);
    }
    const rect = element.getBoundingClientRect();
    await cursor.move(
      rect.left + rect.width / 2,
      rect.top + rect.height / 2,
      signal,
    );
    return element;
  };

  const tap = async (target: TourTarget | Element) => {
    const element = await point(target);
    await cursor.press(signal);
    return element;
  };

  return {
    signal,
    wait,
    find: (target, timeout) => find(target, signal, timeout),
    look: (target, timeout = 1500) =>
      find(target, signal, timeout).catch((error: unknown) => {
        if (signal.aborted) throw error;
        return null;
      }),
    point,
    pointAt: (x, y) => cursor.move(x, y, signal),
    tap,
    click: async (target) => {
      const element = await tap(target);
      if (element instanceof HTMLElement) element.click();
    },
    type: async (target, text) => {
      const field = await point(target);
      if (
        !(field instanceof HTMLInputElement) &&
        !(field instanceof HTMLTextAreaElement)
      ) {
        throw new Error("The guide can only type into a field.");
      }
      if (reducedMotion) {
        setFieldValue(field, text);
        return;
      }
      for (let length = 0; length <= text.length; length += 1) {
        setFieldValue(field, text.slice(0, length));
        await wait(28);
      }
    },
    attach: async (target, file) => {
      const input = await lookUp(target);
      if (!(input instanceof HTMLInputElement)) {
        throw new Error("The guide can only attach a file to an input.");
      }
      // the input itself is hidden, so the cursor goes to the button around it
      await tap(input.closest("label") ?? input);
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    },
  };
}
