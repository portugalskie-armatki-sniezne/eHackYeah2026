import { describe, expect, test } from "bun:test";
import {
  closeTour,
  getTourState,
  goToStep,
  setTourPaused,
  startTour,
  takeOverTour,
} from "../src/components/onboardingState";
import { tourSteps } from "../src/components/onboardingSteps";
import { messages } from "../src/i18n/messages";

describe("onboarding tour state", () => {
  test("starts tour in auto mode, pauses, takes over, and closes", () => {
    startTour("auto");
    const running = getTourState();
    expect(running.phase).toBe("running");
    if (running.phase !== "running") return;
    expect(running.mode).toBe("auto");
    expect(running.step).toBe(0);

    setTourPaused(true);
    const paused = getTourState();
    if (paused.phase !== "running") return;
    expect(paused.paused).toBe(true);

    takeOverTour();
    const manual = getTourState();
    if (manual.phase !== "running") return;
    expect(manual.mode).toBe("manual");
    expect(manual.paused).toBe(false);

    goToStep(2);
    const stepped = getTourState();
    if (stepped.phase !== "running") return;
    expect(stepped.step).toBe(2);

    closeTour();
    expect(getTourState().phase).toBe("off");
  });
});

describe("onboarding tour steps", () => {
  test("defines desktop and phone specific steps", () => {
    const desktop = tourSteps("desktop");
    const phone = tourSteps("phone");

    expect(desktop.some((step) => step.id === "reportClick")).toBe(true);
    expect(desktop.some((step) => step.id === "photoTile")).toBe(false);

    expect(phone.some((step) => step.id === "photoTile")).toBe(true);
    expect(phone.some((step) => step.id === "reportClick")).toBe(false);
  });

  test("has matching i18n messages in pl and en for all step ids", () => {
    for (const locale of ["en", "pl"] as const) {
      const localeSteps = messages[locale].onboarding.steps;
      for (const step of tourSteps("desktop")) {
        const item = localeSteps[step.id];
        expect(item).toBeDefined();
        expect(item.title.length).toBeGreaterThan(0);
        expect(item.body.length).toBeGreaterThan(0);
      }
    }
  });
});
