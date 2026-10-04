import type { Locale } from "../i18n/messages";

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60],
  ["month", 30 * 24 * 60 * 60],
  ["week", 7 * 24 * 60 * 60],
  ["day", 24 * 60 * 60],
  ["hour", 60 * 60],
  ["minute", 60],
];

// "3 hours ago" rather than a timestamp, the way a feed dates its posts, in
// the interface language; `justNow` is that language's word for under a minute
export function timeAgo(iso: string, locale: Locale, justNow: string): string {
  const relative = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  for (const [unit, span] of UNITS) {
    if (Math.abs(seconds) >= span) {
      return relative.format(-Math.round(seconds / span), unit);
    }
  }
  return justNow;
}

export function formatDate(iso: string, locale: Locale): string {
  return new Date(iso).toLocaleString(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
