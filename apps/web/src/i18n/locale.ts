import { useSyncExternalStore } from "react";
import { isLocale, messages, type Locale, type Messages } from "./messages";

const STORAGE_KEY = "locale";

const DEFAULT_LOCALE: Locale = "pl";

/**
 * The interface language. It starts from the last choice saved in this
 * browser and is Polish otherwise. Changing it re-renders every subscriber
 * and marks the document.
 */
function readInitial(): Locale {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLocale(stored)) {
      return stored;
    }
  } catch {
    // storage can be blocked; the default holds
  }
  return DEFAULT_LOCALE;
}

let current: Locale = readInitial();
const listeners = new Set<() => void>();

function apply(locale: Locale) {
  document.documentElement.lang = locale;
}

apply(current);

export function getLocale(): Locale {
  return current;
}

export function setLocale(locale: Locale) {
  if (locale === current) {
    return;
  }
  current = locale;
  apply(locale);
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // the choice still holds for this page load
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The current interface language; follows the toggle as it changes. */
export function useLocale(): Locale {
  return useSyncExternalStore(subscribe, getLocale, getLocale);
}

/** The interface strings for the current language. */
export function useMessages(): Messages {
  return messages[useLocale()];
}
