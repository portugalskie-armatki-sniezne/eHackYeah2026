import {
  useEffect,
  useEffectEvent,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import type { SessionState } from "../api/session";
import { useMessages } from "../i18n/locale";
import {
  closeTour,
  goToStep,
  setTourPaused,
  startTour,
  takeOverTour,
  useTour,
  type TourMode,
  type TourState,
} from "./onboardingState";
import {
  applyScene,
  closeReportSheets,
  createPlayer,
  resolveTarget,
  SkipStep,
  sleep,
  topModal,
  waitFor,
  type TourCursor,
} from "./onboardingPlayer";
import { tourSteps, type TourStep } from "./onboardingSteps";
import "./Onboarding.css";

type OnboardingProps = {
  session: SessionState;
  /** opens the sign-in sheet from the last step */
  onSignIn: () => void;
};

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

// the gap the card keeps from its target, and from the screen's edges
const GAP = 14;
const EDGE = 12;

/**
 * The guide: first the choice between the auto and the manual tour, then the
 * tour itself, which drives the real interface and points at it.
 */
export default function Onboarding({ session, onSignIn }: OnboardingProps) {
  const tour = useTour();
  if (tour.phase === "choosing") return <TourChooser />;
  if (tour.phase === "running") {
    return <TourRunner tour={tour} session={session} onSignIn={onSignIn} />;
  }
  return null;
}

/** Asks how the tour should go, or lets the visitor skip it. */
function TourChooser() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const chosenRef = useRef(false);
  const id = useId();
  const t = useMessages().onboarding;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) return;
    dialog.showModal();
  }, []);

  const choose = (mode: TourMode) => {
    chosenRef.current = true;
    dialogRef.current?.close();
    startTour(mode);
  };

  return (
    <dialog
      ref={dialogRef}
      className="tour-chooser"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-lede`}
      // Escape and the skip button both close it, and so does a choice
      onClose={() => {
        if (!chosenRef.current) closeTour();
      }}
    >
      <div className="tour-chooser__body">
        <h2 id={`${id}-title`} className="tour-chooser__title">
          {t.chooserTitle}
        </h2>
        <p id={`${id}-lede`} className="tour-chooser__lede">
          {t.chooserLede}
        </p>
        <div className="tour-chooser__options">
          <button
            type="button"
            className="tour-chooser__option tour-chooser__option--primary"
            autoFocus
            onClick={() => choose("auto")}
          >
            <span className="tour-chooser__option-glyph" aria-hidden="true">
              &#9654;
            </span>
            <span className="tour-chooser__option-title">{t.autoTitle}</span>
            <span className="tour-chooser__option-text">{t.autoText}</span>
          </button>
          <button
            type="button"
            className="tour-chooser__option"
            onClick={() => choose("manual")}
          >
            <span className="tour-chooser__option-glyph" aria-hidden="true">
              &#9758;
            </span>
            <span className="tour-chooser__option-title">{t.manualTitle}</span>
            <span className="tour-chooser__option-text">{t.manualText}</span>
          </button>
        </div>
        <button
          type="button"
          className="tour-chooser__skip"
          onClick={() => dialogRef.current?.close()}
        >
          {t.skip}
        </button>
        <p className="tour-chooser__hint">{t.rerunHint}</p>
      </div>
    </dialog>
  );
}

type RunningTour = Extract<TourState, { phase: "running" }>;

type TourRunnerProps = {
  tour: RunningTour;
  session: SessionState;
  onSignIn: () => void;
};

/**
 * Plays one step at a time. Each step first sets its scene, then the auto
 * tour moves the drawn cursor and clicks for real, while the manual one waits
 * for the visitor to do what the card asks or press "Next".
 */
function TourRunner({ tour, session, onSignIn }: TourRunnerProps) {
  const t = useMessages().onboarding;
  const id = useId();
  const steps = useMemo(() => tourSteps(tour.layout), [tour.layout]);
  const index = Math.min(tour.step, steps.length - 1);
  const step = steps[index];
  const last = index === steps.length - 1;
  const auto = tour.mode === "auto";
  const playing = auto && !tour.paused;
  const host = useModalHost();
  const [reducedMotion] = useState(
    () => window.matchMedia(REDUCED_MOTION).matches,
  );
  // the step whose task the visitor has just done, for its short "done" note
  const [doneStep, setDoneStep] = useState<number | null>(null);

  const overlayRef = useRef<HTMLDivElement>(null);
  const spotRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLElement>(null);
  const cursorRef = useRef<HTMLDivElement>(null);
  // where the drawn cursor is, kept across a move into or out of a sheet
  const cursorAt = useRef({ x: 0, y: 0 });

  const cursor = useMemo<TourCursor>(
    () => ({
      move: async (x, y, signal) => {
        const from = cursorAt.current;
        const distance = Math.hypot(x - from.x, y - from.y);
        const duration = reducedMotion
          ? 0
          : Math.min(900, Math.max(250, distance * 0.9));
        cursorAt.current = { x, y };
        const element = cursorRef.current;
        if (element) {
          element.style.transitionDuration = `${duration}ms`;
          element.style.transform = `translate(${x}px, ${y}px)`;
        }
        await sleep(duration + 40, signal);
      },
      press: async (signal) => {
        cursorRef.current?.classList.add("tour-cursor--pressed");
        try {
          await sleep(220, signal);
        } finally {
          cursorRef.current?.classList.remove("tour-cursor--pressed");
        }
      },
    }),
    [reducedMotion],
  );

  const messages = useEffectEvent(() => t);

  // the step itself: its scene, then the cursor or the wait for the visitor
  useEffect(() => {
    if (auto && tour.paused) return;
    const controller = new AbortController();
    const { signal } = controller;
    const forward = () => {
      if (index < steps.length - 1) goToStep(index + 1);
    };

    async function run() {
      await applyScene(step.scene, tour.layout, signal);
      await step.enter?.(signal);
      if (auto) {
        const player = createPlayer(cursor, signal, reducedMotion);
        await step.play?.(player, messages());
        if (index < steps.length - 1) {
          await sleep(step.read ?? 1500, signal);
          forward();
        }
        return;
      }
      // Going back, or arriving with the task already done, the card waits
      // for "Next", so the visitor is not bounced straight on again.
      if (tour.back) return;
      if (step.done && !step.done()) {
        await waitFor(step.done, signal, Infinity);
      } else if (step.awaitClick && step.target) {
        await clicked(step, signal);
      } else {
        return;
      }
      setDoneStep(index);
      await sleep(900, signal);
      forward();
    }

    run().catch((error: unknown) => {
      if (signal.aborted) return;
      if (error instanceof SkipStep) {
        if (tour.back && index > 0) goToStep(index - 1, true);
        else forward();
        return;
      }
      console.error("The guide could not play a step.", error);
      if (auto) forward();
    });
    return () => controller.abort();
    // the step is set off again only when it, the mode, or the pause changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, steps, auto, tour.paused, tour.back, cursor, reducedMotion]);

  // a real click or key press stops the animation, so it does not fight the visitor
  useEffect(() => {
    if (!playing) return;
    const stop = (event: Event) => {
      if (!event.isTrusted) return;
      if (overlayRef.current?.contains(event.target as Node)) return;
      setTourPaused(true);
    };
    window.addEventListener("pointerdown", stop, true);
    window.addEventListener("keydown", stop, true);
    window.addEventListener("wheel", stop, true);
    return () => {
      window.removeEventListener("pointerdown", stop, true);
      window.removeEventListener("keydown", stop, true);
      window.removeEventListener("wheel", stop, true);
    };
  }, [playing]);

  // Escape closes the guide, unless a sheet is open and takes it for itself
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !topModal()) closeTour();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);

  // a report sheet opened for the guide would send for real once it is gone
  useEffect(() => () => closeReportSheets(), []);

  // the spotlight and the card follow the target as it moves and scrolls
  useEffect(() => {
    let frame = 0;
    const follow = () => {
      const target = step.target ? resolveTarget(step.target) : null;
      const rect = target?.getBoundingClientRect() ?? null;
      placeSpot(spotRef.current, rect);
      placeCard(cardRef.current, rect);
      frame = requestAnimationFrame(follow);
    };
    follow();
    return () => cancelAnimationFrame(frame);
  }, [step, host]);

  const text = t.steps[step.id];
  const showDone = !auto && doneStep === index;

  const card = (
    <section
      ref={cardRef}
      className="tour-card"
      role="dialog"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-body`}
    >
      <header className="tour-card__head">
        <span className="tour-card__label">
          {t.label} &middot; {t.progress(index + 1, steps.length)}
        </span>
        <button
          type="button"
          className="tour-card__close"
          onClick={() => closeTour()}
        >
          <span aria-hidden="true">&times;</span>
          <span className="visually-hidden">{t.close}</span>
        </button>
      </header>
      <div className="tour-card__progress" aria-hidden="true">
        <span
          className="tour-card__progress-bar"
          style={{ width: `${((index + 1) / steps.length) * 100}%` }}
        />
      </div>
      <div className="tour-card__text" aria-live="polite">
        <h2 id={`${id}-title`} className="tour-card__title">
          {text.title}
        </h2>
        <p id={`${id}-body`} className="tour-card__body">
          {text.body}
        </p>
        {!auto && text.action && !last && (
          <p
            className={
              showDone
                ? "tour-card__action tour-card__action--done"
                : "tour-card__action"
            }
          >
            <span className="tour-card__action-label">
              {showDone ? t.stepDone : t.yourTurn}
            </span>{" "}
            {!showDone && text.action}
          </p>
        )}
        {tour.held && <p className="tour-card__note">{t.held}</p>}
        {auto && tour.paused && <p className="tour-card__note">{t.paused}</p>}
      </div>
      <footer className="tour-card__actions">
        <button
          type="button"
          className="tour-card__button"
          disabled={index === 0}
          onClick={() => goToStep(index - 1, true)}
        >
          {t.back}
        </button>
        {auto && !last && (
          <>
            <button
              type="button"
              className="tour-card__button"
              onClick={() => setTourPaused(!tour.paused)}
            >
              {tour.paused ? t.resume : t.pause}
            </button>
            <button
              type="button"
              className="tour-card__button"
              onClick={() => takeOverTour()}
            >
              {t.takeOver}
            </button>
          </>
        )}
        {!last ? (
          <button
            type="button"
            className="tour-card__button tour-card__button--primary"
            onClick={() => goToStep(index + 1)}
          >
            {t.next}
          </button>
        ) : session.status === "signed-out" ? (
          <>
            <button
              type="button"
              className="tour-card__button"
              onClick={() => closeTour()}
            >
              {t.explore}
            </button>
            <button
              type="button"
              className="tour-card__button tour-card__button--primary"
              onClick={() => {
                closeTour();
                onSignIn();
              }}
            >
              {t.signUp}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="tour-card__button tour-card__button--primary"
            onClick={() => closeTour()}
          >
            {t.finish}
          </button>
        )}
      </footer>
    </section>
  );

  // Inside an open sheet, since a modal dialog leaves the rest of the page
  // inert; the overlay is fixed, so it still covers the whole screen.
  return createPortal(
    <div ref={overlayRef} className="tour">
      <div ref={spotRef} className="tour-spot" aria-hidden="true" />
      {card}
      <div
        ref={(element) => {
          cursorRef.current = element;
          if (!element) return;
          if (cursorAt.current.x === 0 && cursorAt.current.y === 0) {
            cursorAt.current = {
              x: window.innerWidth * 0.5,
              y: window.innerHeight * 0.7,
            };
          }
          const { x, y } = cursorAt.current;
          element.style.transform = `translate(${x}px, ${y}px)`;
        }}
        className={playing ? "tour-cursor tour-cursor--visible" : "tour-cursor"}
        aria-hidden="true"
      >
        <svg className="tour-cursor__arrow" viewBox="0 0 24 24">
          <path d="M3 2 L3 19 L8 14.5 L11.5 22 L14.5 20.5 L11 13.5 L18 13.5 Z" />
        </svg>
      </div>
    </div>,
    host,
  );
}

/** The open modal sheet, or the body while there is none. */
function useModalHost(): HTMLElement {
  const [host, setHost] = useState<HTMLElement>(
    () => topModal() ?? document.body,
  );
  useEffect(() => {
    const update = () => setHost(topModal() ?? document.body);
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["open"],
    });
    return () => observer.disconnect();
  }, []);
  return host;
}

/** Resolves on the visitor's own click on the step's target. */
function clicked(step: TourStep, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const target = step.target;
    const onClick = (event: MouseEvent) => {
      const element = target ? resolveTarget(target) : null;
      if (event.isTrusted && element?.contains(event.target as Node)) {
        cleanup();
        resolve();
      }
    };
    const onAbort = () => {
      cleanup();
      reject(signal.reason);
    };
    const cleanup = () => {
      document.removeEventListener("click", onClick, true);
      signal.removeEventListener("abort", onAbort);
    };
    document.addEventListener("click", onClick, true);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function placeSpot(spot: HTMLElement | null, rect: DOMRect | null) {
  if (!spot) return;
  if (!rect) {
    spot.classList.remove("tour-spot--on");
    return;
  }
  spot.classList.add("tour-spot--on");
  spot.style.transform = `translate(${rect.left - 6}px, ${rect.top - 6}px)`;
  spot.style.width = `${rect.width + 12}px`;
  spot.style.height = `${rect.height + 12}px`;
}

type Corner = "bottom-right" | "bottom-left" | "top-right" | "top-left";

// in order of preference, when more than one corner leaves the target clear
const CORNERS: Corner[] = [
  "bottom-right",
  "bottom-left",
  "top-right",
  "top-left",
];

/**
 * Docks the card in a corner of the screen: bottom right by default, and
 * otherwise the corner that covers the least of the target, so the card
 * stays out of the way of what it points at. The corner only changes when
 * the current one would cover the target, so the card does not jump about.
 */
function placeCard(card: HTMLElement | null, rect: DOMRect | null) {
  if (!card) return;
  const width = card.offsetWidth;
  const height = card.offsetHeight;
  const right = Math.max(EDGE, window.innerWidth - width - EDGE);
  const bottom = Math.max(EDGE, window.innerHeight - height - EDGE);
  const spots: Record<Corner, { x: number; y: number }> = {
    "bottom-right": { x: right, y: bottom },
    "bottom-left": { x: EDGE, y: bottom },
    "top-right": { x: right, y: EDGE },
    "top-left": { x: EDGE, y: EDGE },
  };
  const covered = (corner: Corner) => {
    if (!rect) return 0;
    const { x, y } = spots[corner];
    const overlapX =
      Math.min(x + width, rect.right + GAP) - Math.max(x, rect.left - GAP);
    const overlapY =
      Math.min(y + height, rect.bottom + GAP) - Math.max(y, rect.top - GAP);
    return Math.max(0, overlapX) * Math.max(0, overlapY);
  };

  const current = card.dataset.corner as Corner | undefined;
  let corner = current ?? CORNERS[0];
  if (covered(corner) > 0) {
    corner = CORNERS.reduce((best, candidate) =>
      covered(candidate) < covered(best) ? candidate : best,
    );
  }
  card.dataset.corner = corner;
  const { x, y } = spots[corner];
  card.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
}
