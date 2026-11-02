import { useSyncExternalStore } from "react";

export type TourMode = "auto" | "manual";
export type TourLayout = "desktop" | "phone";

export type TourState =
  | { phase: "off" }
  | { phase: "choosing" }
  | {
      phase: "running";
      mode: TourMode;
      layout: TourLayout;
      step: number;
      /** whether the step was reached going back, so it waits for "Next" */
      back: boolean;
      /** auto only: the animation stopped, by the pause button or a real click */
      paused: boolean;
      /** a report was sent while the guide ran, and held back */
      held: boolean;
      /** when the tour began, so the sample data reads as recent */
      startedAt: number;
    };

const SEEN_KEY = "onboarding-seen";

// the phone layout, as the chrome's stylesheets and the map draw it
const PHONE_LAYOUT = "(max-width: 40rem)";

/** Whether the guide was already offered in this browser. */
function readSeen(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(SEEN_KEY) !== null;
  } catch {
    // with storage blocked the guide would offer itself on every visit
    return true;
  }
}

function markSeen() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SEEN_KEY, "1");
  } catch {
    // it still stays closed for this page load
  }
}

// the first visit opens on the choice, which also offers to skip the guide
let state: TourState = readSeen() ? { phase: "off" } : { phase: "choosing" };
const listeners = new Set<() => void>();

function setState(next: TourState) {
  state = next;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getTourState(): TourState {
  return state;
}

/** The guide's state; every caller shares one tour. */
export function useTour(): TourState {
  return useSyncExternalStore(subscribe, getTourState);
}

/** Whether the guide is running, outside of rendering. */
export function isTourActive(): boolean {
  return state.phase === "running";
}

/**
 * Whether the guide is running, so the parts it shows off can stand in for an
 * account: sending is held back and sample data fills what would be empty.
 */
export function useTourActive(): boolean {
  return useSyncExternalStore(subscribe, isTourActive);
}

/** Offers the choice between the auto and the manual tour. */
export function openTourChooser() {
  setState({ phase: "choosing" });
}

export function startTour(mode: TourMode, forcedLayout?: TourLayout) {
  markSeen();
  const isPhone =
    typeof window !== "undefined" &&
    Boolean(window.matchMedia?.(PHONE_LAYOUT)?.matches);
  setState({
    phase: "running",
    mode,
    layout: forcedLayout ?? (isPhone ? "phone" : "desktop"),
    step: 0,
    back: false,
    paused: false,
    held: false,
    startedAt: Date.now(),
  });
}

export function closeTour() {
  markSeen();
  setState({ phase: "off" });
}

/** Moves to another step; the held-back note belongs to the step it was on. */
export function goToStep(step: number, back = false) {
  if (state.phase !== "running") return;
  setState({ ...state, step, back, paused: false, held: false });
}

export function setTourPaused(paused: boolean) {
  if (state.phase !== "running" || state.paused === paused) return;
  setState({ ...state, paused });
}

/** Hands the wheel over: the auto tour goes on as a manual one from here. */
export function takeOverTour() {
  if (state.phase !== "running") return;
  setState({ ...state, mode: "manual", paused: false, back: true });
}

/** Notes a report the guide held back instead of sending. */
export function noteHeldReport() {
  if (state.phase !== "running") return;
  setState({ ...state, held: true });
}

/**
 * What the map lends the guide, so it can open the sheets a click would and
 * find a case to show. The map fills it in while it is on screen.
 */
export type TourMapBridge = {
  /** the case reported most often, or null while the map has none */
  topPinId: () => string | null;
  /** flies to a case, close enough for its pin to stand on its own */
  showPin: (id: string) => Promise<void>;
  openPin: (id: string) => void;
  /** opens the new report sheet where a click at this screen point would */
  openDraftAt: (x: number, y: number) => void;
  /** opens the phone's photo report sheet as if the camera had returned */
  openPhotoDraft: (photo: File) => void;
};

let mapBridge: TourMapBridge | null = null;

export function registerTourMap(bridge: TourMapBridge): () => void {
  mapBridge = bridge;
  return () => {
    if (mapBridge === bridge) mapBridge = null;
  };
}

export function getTourMap(): TourMapBridge | null {
  return mapBridge;
}
