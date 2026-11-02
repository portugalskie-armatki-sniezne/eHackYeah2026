import { useEffect, useState } from "react";
import { MAX_PAGE_SIZE, reportsApi, type Report } from "../api/reports";
import { useLocale, useMessages } from "../i18n/locale";
import { formatDate, timeAgo } from "./relativeTime";
import "./MarkerDialog.css";

type MasterReportsProps = {
  masterId: string;
  hidden: boolean;
};

/**
 * The filings folded into a master, newest first, as the marker dialog's side
 * panel lists them. Loaded once, the first time the panel shows them.
 */
export default function MasterReports({
  masterId,
  hidden,
}: MasterReportsProps) {
  const t = useMessages().marker;
  const locale = useLocale();
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      try {
        const page = await reportsApi.list(
          { master_report_id: masterId, limit: MAX_PAGE_SIZE },
          signal,
        );
        if (signal.aborted) return;
        setReports(page.items);
      } catch (error) {
        if (signal.aborted) return;
        setError(error instanceof Error ? error.message : t.reportsLoadFailed);
      }
    }
    void load();
    return () => controller.abort();
    // the fallback text is read once, when the load fails
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [masterId]);

  return (
    <div className="marker-dialog__reports" hidden={hidden}>
      {error ? (
        <p className="marker-dialog__error" role="alert">
          {error}
        </p>
      ) : !reports ? (
        <p className="marker-dialog__hint">{t.loadingReports}</p>
      ) : reports.length === 0 ? (
        <p className="marker-dialog__hint">{t.noReports}</p>
      ) : (
        <ul className="marker-dialog__feed">
          {reports.map((report) => (
            <li key={report.id} className="marker-dialog__report">
              <div className="marker-dialog__comment-head">
                <h4 className="marker-dialog__report-title">{report.title}</h4>
                <time
                  className="marker-dialog__when"
                  dateTime={report.created_at}
                  title={formatDate(report.created_at, locale)}
                >
                  {timeAgo(report.created_at, locale, t.justNow)}
                </time>
              </div>
              <p className="marker-dialog__comment-text">
                {report.description}
              </p>
              {report.photos.length > 0 && (
                <div className="marker-dialog__report-photos">
                  {report.photos.map((photo, index) => (
                    <img
                      key={photo.id}
                      src={reportsApi.photoUrl(photo)}
                      alt={t.reportPhotoOf(index + 1, report.title)}
                    />
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
