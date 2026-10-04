import { useCallback, useEffect, useState } from "react";
import { reportsApi } from "../api/reports";
import { useSession } from "../api/session";

/** the account the read belongs to, so a stale answer is not taken for it */
type MyCases = { userId: string; ids: ReadonlySet<string> };

export type MyCasesState = {
  /**
   * The cases the account has a filing on. Null while the answer is not known:
   * for a signed-out visitor, and until the account's reports are read, so a
   * filter can hold the option back rather than offer one that would empty the
   * view.
   */
  cases: ReadonlySet<string> | null;
  /**
   * Counts a case the account has just filed as its own, so a pin dropped
   * while the filter is on does not vanish under it.
   */
  note: (caseId: string) => void;
};

/**
 * The cases the signed-in account has a filing on, which is what the map's and
 * the reports page's "only mine" filter narrows to.
 */
export default function useMyCases(): MyCasesState {
  const session = useSession();
  const userId = session.status === "signed-in" ? session.user.id : null;
  const [read, setRead] = useState<MyCases | null>(null);

  useEffect(() => {
    if (!userId) {
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    reportsApi.myMasterReportIds(userId, signal).then(
      (ids) => {
        if (!signal.aborted) setRead({ userId, ids });
      },
      (error) => {
        if (!signal.aborted) {
          console.error("Could not read the account's own reports.", error);
        }
      },
    );
    return () => controller.abort();
  }, [userId]);

  const note = useCallback(
    (caseId: string) =>
      setRead((current) =>
        current && current.userId === userId && !current.ids.has(caseId)
          ? { userId, ids: new Set(current.ids).add(caseId) }
          : current,
      ),
    [userId],
  );

  // The read is kept with its account rather than cleared on sign-out, so what
  // the last account filed is never handed to the next one.
  return {
    cases: read && read.userId === userId ? read.ids : null,
    note,
  };
}
