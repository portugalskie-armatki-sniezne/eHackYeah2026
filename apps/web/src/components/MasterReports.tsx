import { useEffect, useState } from "react";
import { MAX_PAGE_SIZE, reportsApi, type Report } from "../api/reports";
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
        setError(
          error instanceof Error
            ? error.message
            : "Could not load the reports.",
        );
      }
    }
    void load();
    return () => controller.abort();
  }, [masterId]);

  return (
    <div className="marker-dialog__reports" hidden={hidden}>
      {error ? (
        <p className="marker-dialog__error" role="alert">
          {error}
        </p>
      ) : !reports ? (
        <p className="marker-dialog__hint">Loading reports...</p>
      ) : reports.length === 0 ? (
        <p className="marker-dialog__hint">No reports to show.</p>
      ) : (
        <ul className="marker-dialog__feed">
          {reports.map((report) => (
            <li key={report.id} className="marker-dialog__report">
              <div className="marker-dialog__comment-head">
                <h4 className="marker-dialog__report-title">{report.title}</h4>
                <time
                  className="marker-dialog__when"
                  dateTime={report.created_at}
                  title={formatDate(report.created_at)}
                >
                  {timeAgo(report.created_at)}
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
                      alt={`Photo ${index + 1} of: ${report.title}`}
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
