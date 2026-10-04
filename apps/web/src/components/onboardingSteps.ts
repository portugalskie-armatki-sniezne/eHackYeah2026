import type { Messages, TourStepId } from "../i18n/messages";
import { getTourMap, type TourLayout } from "./onboardingState";
import {
  draftPoint,
  loadSamplePhoto,
  openSheet,
  topPin,
  topPinElement,
  type Player,
  type TourScene,
  type TourTarget,
} from "./onboardingPlayer";
import { readRoute, type Route } from "./useHashRoute";

export type TourStep = {
  id: TourStepId;
  /** the one layout the step belongs to; both when left out */
  layout?: TourLayout;
  scene: TourScene;
  /** what the spotlight is on; the card sits in the middle without one */
  target?: TourTarget;
  /** run in both modes once the scene is set, say to bring a pin into view */
  enter?: (signal: AbortSignal) => Promise<void>;
  /** auto: what the cursor does, as a visitor would */
  play?: (player: Player, t: Messages["onboarding"]) => Promise<void>;
  /** manual: whether the visitor has done what the card asks */
  done?: () => boolean;
  /** manual: a click on the target is what the card asks for */
  awaitClick?: boolean;
  /** auto: how long the card stays up once the cursor is done, to be read */
  read?: number;
};

const isPressed = (selector: string) =>
  document.querySelector(selector)?.getAttribute("aria-pressed") === "true";

const isExpanded = (selector: string) =>
  document.querySelector(selector)?.getAttribute("aria-expanded") === "true";

const hasText = (selector: string) => {
  const field = document.querySelector(selector);
  return (
    (field instanceof HTMLInputElement ||
      field instanceof HTMLTextAreaElement) &&
    field.value.trim().length > 0
  );
};

/** The navbar link to a page; phones fold it under the menu. */
function navStep(id: TourStepId, route: Route, from: Route): TourStep {
  const link = `.navbar__link[href="#${route}"]`;
  return {
    id,
    scene: { route: from, menu: true },
    target: link,
    play: (player) => player.click(link),
    done: () => readRoute() === route,
    read: 1200,
  };
}

const REPORT_SEND = ".pin-dialog .pin-dialog__button--primary";
const REPORT_CLOSE =
  ".pin-dialog .pin-dialog__actions .pin-dialog__button:not(.pin-dialog__button--primary)";

/** The send button of either report sheet, shown but not pressed. */
function sendStep(layout: TourLayout): TourStep {
  return {
    id: "reportSend",
    layout,
    scene: { route: "map", sheet: layout === "phone" ? "photo" : "pin" },
    target: REPORT_SEND,
    play: async (player) => {
      await player.point(REPORT_SEND);
      await player.wait(3200);
      await player.click(REPORT_CLOSE);
    },
    done: () => openSheet() === null,
    read: 600,
  };
}

const TILT = '[data-tour="tilt"]';
const FILTERS = ".map-filters__toggle";

/**
 * The whole tour, in order: the map, a new report, the reports and the
 * notifications, then the initiatives and the about page. Each step starts
 * from its scene, so it can be reached going back or after a pause too.
 */
export const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    scene: { route: "map" },
    play: async (player) => {
      await player.pointAt(window.innerWidth * 0.5, window.innerHeight * 0.45);
    },
    read: 3800,
  },
  {
    id: "zoom",
    scene: { route: "map" },
    target: '[data-tour="zoom"]',
    play: async (player) => {
      await player.click('[data-tour="zoom-in"]');
      await player.wait(500);
      await player.click('[data-tour="zoom-in"]');
      await player.wait(1200);
      await player.click('[data-tour="zoom-out"]');
      await player.wait(500);
      await player.click('[data-tour="zoom-out"]');
    },
    awaitClick: true,
    read: 1800,
  },
  {
    id: "filters",
    scene: { route: "map" },
    target: FILTERS,
    play: (player) => player.click(FILTERS),
    done: () => isExpanded(FILTERS),
    read: 1200,
  },
  {
    id: "filterList",
    scene: { route: "map", filters: true },
    target: ".map-filters",
    play: async (player) => {
      // one kind taken off the map and put back, so the pins visibly react
      const box = '.map-filters input[type="checkbox"]';
      await player.click(box);
      await player.wait(1400);
      await player.click(box);
    },
    read: 2400,
  },
  {
    id: "tilt",
    scene: { route: "map" },
    target: TILT,
    play: async (player) => {
      if (!isPressed(TILT)) await player.click(TILT);
      await player.wait(2800);
      if (isPressed(TILT)) await player.click(TILT);
    },
    done: () => isPressed(TILT),
    read: 800,
  },
  {
    id: "openCase",
    scene: { route: "map" },
    target: topPinElement,
    enter: async (signal) => {
      const id = await topPin(signal);
      await getTourMap()?.showPin(id);
    },
    play: async (player) => {
      const pin = await player.look(topPinElement);
      if (pin) {
        await player.click(pin);
        return;
      }
      // a pin still drawn inside a group is opened the way its disc would be
      const { x, y } = draftPoint();
      await player.pointAt(x, y);
      const id = await topPin(player.signal);
      getTourMap()?.openPin(id);
    },
    done: () => openSheet() === "marker",
    read: 600,
  },
  {
    id: "caseSheet",
    scene: { route: "map", sheet: "marker" },
    target: ".marker-dialog__post",
    play: async (player) => {
      const badge = await player.look(".marker-dialog__badge", 4000);
      if (badge) {
        await player.point(badge);
        await player.wait(1200);
      }
      const envelope = await player.look(".marker-dialog__envelope");
      if (envelope) {
        await player.point(envelope);
        await player.wait(1400);
      }
      const comments = await player.look(".marker-dialog__toggle");
      if (comments) {
        await player.click(comments);
        await player.wait(2200);
        await player.click(".marker-dialog__panel-close");
      }
    },
    read: 1200,
  },
  {
    id: "reportClick",
    layout: "desktop",
    scene: { route: "map" },
    play: async (player) => {
      const { x, y } = draftPoint();
      await player.pointAt(x, y);
      await player.wait(300);
      getTourMap()?.openDraftAt(x, y);
    },
    done: () => openSheet() === "pin",
    read: 600,
  },
  {
    id: "photoTile",
    layout: "phone",
    scene: { route: "map" },
    target: ".toolbar__add",
    play: async (player) => {
      // a click would open the camera, so the tile is only pressed
      await player.tap(".toolbar__add");
      getTourMap()?.openPhotoDraft(await loadSamplePhoto());
    },
    done: () => openSheet() === "photo",
    read: 600,
  },
  {
    id: "reportKind",
    layout: "desktop",
    scene: { route: "map", sheet: "pin" },
    target: ".pin-dialog__tabs",
    play: async (player) => {
      await player.click(".pin-dialog__tab:nth-child(2)");
      await player.wait(1800);
      await player.click(".pin-dialog__tab:nth-child(1)");
    },
    awaitClick: true,
    read: 1200,
  },
  {
    id: "reportForm",
    layout: "desktop",
    scene: { route: "map", sheet: "pin" },
    target: ".pin-dialog__form",
    play: async (player, t) => {
      await player.type('.pin-dialog input[name="title"]', t.sampleTitle);
      await player.type(
        '.pin-dialog textarea[name="description"]',
        t.sampleDescription,
      );
      await player.attach(
        '.pin-dialog input[name="image"]',
        await loadSamplePhoto(),
      );
    },
    done: () => hasText(".pin-dialog textarea"),
    read: 1400,
  },
  {
    id: "photoForm",
    layout: "phone",
    scene: { route: "map", sheet: "photo" },
    target: ".pin-dialog__form",
    play: (player, t) =>
      player.type(".pin-dialog textarea", t.sampleDescription),
    done: () => hasText(".pin-dialog textarea"),
    read: 1200,
  },
  sendStep("desktop"),
  sendStep("phone"),
  navStep("navReports", "reports", "map"),
  {
    id: "reports",
    scene: { route: "reports" },
    target: ".reports-page__controls",
    play: async (player) => {
      await player.look(".reports-page__list", 5000);
      const status = await player.look(".reports-page__pill:nth-child(2)");
      if (status) {
        await player.click(status);
        await player.wait(1400);
        await player.click(".reports-page__pill:nth-child(1)");
      }
      // only an account has its own cases, or the guide's stand-ins for them
      const mine = await player.look(".reports-page__pill[title]", 500);
      if (mine) {
        await player.click(mine);
        await player.wait(1400);
        await player.click(mine);
      }
      const first = await player.look(".reports-page__list > li");
      if (first) await player.point(first);
    },
    awaitClick: true,
    read: 1800,
  },
  navStep("navNotifications", "notifications", "reports"),
  {
    id: "notifications",
    scene: { route: "notifications" },
    // the sample list, an account's own, or the note to sign in
    target: () =>
      document.querySelector(".notifications-page__list") ??
      document.querySelector(".notifications-page__notice"),
    play: async (player) => {
      const cards = await player.look(".notifications-page__card", 4000);
      if (!cards) return;
      await player.point(cards);
      await player.wait(1600);
      const second = await player.look(
        ".notifications-page__list > li:nth-child(2)",
      );
      if (second) await player.point(second);
    },
    read: 2200,
  },
  navStep("navInitiatives", "initiatives", "notifications"),
  {
    id: "catalog",
    scene: { route: "initiatives" },
    target: ".catalog__controls",
    play: async (player, t) => {
      await player.type(".catalog__input", t.catalogQuery);
      await player.wait(1600);
      const card = await player.look(".catalog__card", 4000);
      if (card) {
        await player.point(card);
        await player.wait(1600);
      }
      await player.type(".catalog__input", "");
    },
    done: () => hasText(".catalog__input"),
    read: 1200,
  },
  navStep("navAbout", "about", "initiatives"),
  {
    id: "about",
    scene: { route: "about" },
    target: ".about__pillars",
    play: async (player) => {
      for (const tile of document.querySelectorAll(".about__tile")) {
        await player.point(tile);
        await player.wait(900);
      }
    },
    read: 1600,
  },
  {
    id: "finish",
    scene: { route: "map", menu: true },
    target: '[data-tour="guide"]',
    play: async (player) => {
      await player.point('[data-tour="guide"]');
    },
  },
];

/** The steps of the tour for one layout. */
export function tourSteps(layout: TourLayout): TourStep[] {
  return TOUR_STEPS.filter((step) => !step.layout || step.layout === layout);
}
