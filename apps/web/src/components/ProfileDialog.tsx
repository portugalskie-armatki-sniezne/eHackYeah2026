import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type RefObject,
} from "react";
import { authApi, type User, type UserUpdate } from "../api/auth";
import { reportsApi, type Report } from "../api/reports";
import { updateUser } from "../api/session";
import { useLocale, useMessages } from "../i18n/locale";
import LanguageToggle from "./LanguageToggle";
import type { Locale, Messages } from "../i18n/messages";
import "./AuthDialog.css";
import "./ProfileDialog.css";

type ProfileTab = "account" | "password" | "reports" | "preferences";

type ProfileDialogProps = {
  user: User;
  onClose: () => void;
};

const MIN_PASSWORD_LENGTH = 8;
const REPORTS_LIMIT = 50;

type ProfileMessages = Messages["profile"];

function formatDate(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(
    new Date(value),
  );
}

// server errors arrive in whatever language the API speaks; only the
// fallback for a non-Error is ours to translate
function errorText(error: unknown, t: ProfileMessages) {
  return error instanceof Error ? error.message : t.somethingWrong;
}

/**
 * The signed-in user's profile sheet: account details with an edit form, a
 * password change, and the reports the user has sent. It shares the account
 * sheet's look and stays open while a change is being saved.
 */
export default function ProfileDialog({ user, onClose }: ProfileDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<ProfileTab>("account");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const id = useId();
  const t = useMessages().profile;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }
    dialog.showModal();
  }, []);

  // runs one save at a time and keeps the sheet open until it settles
  const run = async (task: () => Promise<void>) => {
    if (busyRef.current) {
      return;
    }
    busyRef.current = true;
    setBusy(true);
    try {
      await task();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const tabs: { value: ProfileTab; label: string }[] = [
    { value: "account", label: t.tabs.account },
    { value: "password", label: t.tabs.password },
    { value: "reports", label: t.tabs.reports },
    { value: "preferences", label: t.tabs.preferences },
  ];

  return (
    <dialog
      ref={dialogRef}
      className="auth-dialog profile-dialog"
      aria-labelledby={`${id}-title`}
      onClose={onClose}
      onCancel={(event) => {
        if (busyRef.current) event.preventDefault();
      }}
    >
      <div className="auth-dialog__form">
        <header className="auth-dialog__header">
          <h2 id={`${id}-title`} className="auth-dialog__title">
            {t.title}
          </h2>
          <div
            className="auth-dialog__switch"
            role="group"
            aria-label={t.section}
          >
            {tabs.map((item) => (
              <button
                key={item.value}
                type="button"
                className="auth-dialog__tab"
                aria-pressed={tab === item.value}
                disabled={busy}
                onClick={() => setTab(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </header>

        {tab === "account" && (
          <AccountSection
            user={user}
            busy={busy}
            run={run}
            dialogRef={dialogRef}
          />
        )}
        {tab === "password" && (
          <PasswordSection
            user={user}
            busy={busy}
            run={run}
            dialogRef={dialogRef}
          />
        )}
        {tab === "reports" && (
          <ReportsSection user={user} dialogRef={dialogRef} />
        )}
        {tab === "preferences" && <PreferencesSection dialogRef={dialogRef} />}
      </div>
    </dialog>
  );
}

type SectionProps = {
  user: User;
  busy: boolean;
  run: (task: () => Promise<void>) => Promise<void>;
  dialogRef: RefObject<HTMLDialogElement | null>;
};

function CloseButton({
  dialogRef,
  disabled,
}: {
  dialogRef: RefObject<HTMLDialogElement | null>;
  disabled?: boolean;
}) {
  const label = useMessages().profile.close;
  return (
    <button
      type="button"
      className="auth-dialog__button"
      disabled={disabled}
      onClick={() => dialogRef.current?.close()}
    >
      {label}
    </button>
  );
}

function AccountSection({ user, busy, run, dialogRef }: SectionProps) {
  const [editing, setEditing] = useState(false);
  const [firstName, setFirstName] = useState(user.first_name);
  const [lastName, setLastName] = useState(user.last_name);
  const [email, setEmail] = useState(user.email ?? "");
  const [phone, setPhone] = useState(user.phone ?? "");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const id = useId();
  const t = useMessages().profile;
  const locale = useLocale();

  const startEditing = () => {
    setFirstName(user.first_name);
    setLastName(user.last_name);
    setEmail(user.email ?? "");
    setPhone(user.phone ?? "");
    setError(null);
    setNotice(null);
    setEditing(true);
  };

  // only the fields that differ are sent, so an untouched form saves nothing
  const changes = (): UserUpdate => {
    const next = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: email.trim() || null,
      phone: phone.trim() || null,
    };
    const update: UserUpdate = {};
    if (next.first_name !== user.first_name)
      update.first_name = next.first_name;
    if (next.last_name !== user.last_name) update.last_name = next.last_name;
    if (next.email !== user.email) update.email = next.email;
    if (next.phone !== user.phone) update.phone = next.phone;
    return update;
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(async () => {
      setError(null);
      if (!email.trim() && !phone.trim()) {
        setError(t.contactRequired);
        return;
      }
      const update = changes();
      if (Object.keys(update).length === 0) {
        setEditing(false);
        return;
      }
      try {
        updateUser(await authApi.updateUser(user.id, update));
        setEditing(false);
        setNotice(t.detailsSaved);
      } catch (error) {
        setError(errorText(error, t));
      }
    });
  };

  if (!editing) {
    const details: [string, string][] = [
      [t.name, `${user.first_name} ${user.last_name}`],
      [t.email, user.email ?? t.notSet],
      [t.phone, user.phone ?? t.notSet],
      [t.role, t.roles[user.role]],
      [t.google, user.google_linked ? t.linked : t.notLinked],
      [t.memberSince, formatDate(user.created_at, locale)],
    ];
    return (
      <>
        {notice && (
          <p className="profile-dialog__notice" role="status">
            {notice}
          </p>
        )}
        <dl className="profile-dialog__details">
          {details.map(([term, value]) => (
            <div key={term} className="profile-dialog__detail">
              <dt className="auth-dialog__label">{term}</dt>
              <dd className="profile-dialog__value">{value}</dd>
            </div>
          ))}
        </dl>
        <footer className="auth-dialog__actions">
          <CloseButton dialogRef={dialogRef} />
          <button
            type="button"
            className="auth-dialog__button auth-dialog__button--primary"
            onClick={startEditing}
          >
            {t.edit}
          </button>
        </footer>
      </>
    );
  }

  return (
    <form className="profile-dialog__section" onSubmit={handleSubmit}>
      {error && (
        <p className="auth-dialog__error" role="alert">
          {error}
        </p>
      )}
      <div className="auth-dialog__row">
        <div className="auth-dialog__field">
          <label className="auth-dialog__label" htmlFor={`${id}-first`}>
            {t.firstName}
          </label>
          <input
            id={`${id}-first`}
            className="auth-dialog__input"
            name="first_name"
            autoComplete="given-name"
            required
            disabled={busy}
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
          />
        </div>
        <div className="auth-dialog__field">
          <label className="auth-dialog__label" htmlFor={`${id}-last`}>
            {t.lastName}
          </label>
          <input
            id={`${id}-last`}
            className="auth-dialog__input"
            name="last_name"
            autoComplete="family-name"
            required
            disabled={busy}
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
          />
        </div>
      </div>
      <div className="auth-dialog__field">
        <label className="auth-dialog__label" htmlFor={`${id}-email`}>
          {t.email}
        </label>
        <input
          id={`${id}-email`}
          className="auth-dialog__input"
          type="email"
          name="email"
          autoComplete="email"
          disabled={busy}
          aria-describedby={`${id}-contact-hint`}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="auth-dialog__field">
        <label className="auth-dialog__label" htmlFor={`${id}-phone`}>
          {t.phone}
        </label>
        <input
          id={`${id}-phone`}
          className="auth-dialog__input"
          type="tel"
          name="phone"
          autoComplete="tel"
          disabled={busy}
          aria-describedby={`${id}-contact-hint`}
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
        <p id={`${id}-contact-hint`} className="auth-dialog__hint">
          {t.contactHint}
        </p>
      </div>
      <footer className="auth-dialog__actions">
        <button
          type="button"
          className="auth-dialog__button"
          disabled={busy}
          onClick={() => {
            setError(null);
            setEditing(false);
          }}
        >
          {t.cancel}
        </button>
        <button
          type="submit"
          className="auth-dialog__button auth-dialog__button--primary"
          disabled={busy}
        >
          {busy ? t.pleaseWait : t.save}
        </button>
      </footer>
    </form>
  );
}

function PasswordSection({ user, busy, run, dialogRef }: SectionProps) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const id = useId();
  const t = useMessages().profile;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(async () => {
      setError(null);
      setNotice(null);
      if (password !== confirmation) {
        setError(t.passwordMismatch);
        return;
      }
      try {
        await authApi.updateUser(user.id, { password });
        setPassword("");
        setConfirmation("");
        setNotice(t.passwordChanged);
      } catch (error) {
        setError(errorText(error, t));
      }
    });
  };

  return (
    <form className="profile-dialog__section" onSubmit={handleSubmit}>
      {error && (
        <p className="auth-dialog__error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="profile-dialog__notice" role="status">
          {notice}
        </p>
      )}
      {/* lets password managers tie the new password to this account */}
      <input
        type="text"
        name="username"
        autoComplete="username"
        value={user.email ?? user.phone ?? ""}
        readOnly
        hidden
      />
      <div className="auth-dialog__field">
        <label className="auth-dialog__label" htmlFor={`${id}-password`}>
          {t.newPassword}
        </label>
        <input
          id={`${id}-password`}
          className="auth-dialog__input"
          type="password"
          name="new-password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          disabled={busy}
          aria-describedby={`${id}-password-hint`}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p id={`${id}-password-hint`} className="auth-dialog__hint">
          {t.passwordHint(MIN_PASSWORD_LENGTH)}
        </p>
      </div>
      <div className="auth-dialog__field">
        <label className="auth-dialog__label" htmlFor={`${id}-confirmation`}>
          {t.repeatPassword}
        </label>
        <input
          id={`${id}-confirmation`}
          className="auth-dialog__input"
          type="password"
          name="confirm-password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          disabled={busy}
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
        />
      </div>
      <footer className="auth-dialog__actions">
        <CloseButton dialogRef={dialogRef} disabled={busy} />
        <button
          type="submit"
          className="auth-dialog__button auth-dialog__button--primary"
          disabled={busy}
        >
          {busy ? t.pleaseWait : t.changePassword}
        </button>
      </footer>
    </form>
  );
}

/** Settings kept in this browser rather than on the account. */
function PreferencesSection({ dialogRef }: Pick<SectionProps, "dialogRef">) {
  const t = useMessages().profile;
  const id = useId();
  return (
    <>
      <div className="profile-dialog__section">
        <div className="auth-dialog__field">
          <span id={`${id}-language`} className="auth-dialog__label">
            {t.language}
          </span>
          <LanguageToggle labelledBy={`${id}-language`} />
          <p className="auth-dialog__hint">{t.languageHint}</p>
        </div>
      </div>
      <footer className="auth-dialog__actions">
        <CloseButton dialogRef={dialogRef} />
      </footer>
    </>
  );
}

type ReportsState =
  | { status: "loading" }
  | { status: "failed"; error: string }
  | {
      status: "ready";
      reports: Report[];
      total: number;
      categories: Map<number, string>;
    };

function ReportsSection({
  user,
  dialogRef,
}: Pick<SectionProps, "user" | "dialogRef">) {
  const [state, setState] = useState<ReportsState>({ status: "loading" });
  const t = useMessages().profile;
  const locale = useLocale();

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    Promise.all([
      reportsApi.list({ user_id: user.id, limit: REPORTS_LIMIT }, signal),
      // names are a nicety; the list still shows without them
      reportsApi.categories(signal).catch(() => []),
    ])
      .then(([page, categories]) =>
        setState({
          status: "ready",
          reports: page.items,
          total: page.total,
          categories: new Map(
            categories.map((category) => [category.id, category.name]),
          ),
        }),
      )
      .catch((error: unknown) => {
        if (!signal.aborted) {
          setState({ status: "failed", error: errorText(error, t) });
        }
      });
    return () => controller.abort();
  }, [user.id, t]);

  return (
    <>
      {state.status === "loading" && (
        <div className="profile-dialog__loading" role="status">
          <span className="profile-dialog__spinner" aria-hidden="true" />
          <span className="visually-hidden">{t.loadingReports}</span>
        </div>
      )}
      {state.status === "failed" && (
        <p className="auth-dialog__error" role="alert">
          {state.error}
        </p>
      )}
      {state.status === "ready" &&
        (state.reports.length === 0 ? (
          <p className="auth-dialog__text">{t.noReports}</p>
        ) : (
          <>
            <p className="auth-dialog__hint">
              {state.total > state.reports.length
                ? t.showingLatest(state.reports.length, state.total)
                : t.reportCount(state.total)}
            </p>
            <ul className="profile-dialog__reports">
              {state.reports.map((report) => (
                <li key={report.id} className="profile-dialog__report">
                  {report.photos[0] ? (
                    <img
                      className="profile-dialog__thumb"
                      src={reportsApi.photoUrl(report.photos[0])}
                      alt=""
                      loading="lazy"
                    />
                  ) : (
                    <span
                      className="profile-dialog__thumb profile-dialog__thumb--empty"
                      aria-hidden="true"
                    />
                  )}
                  <div className="profile-dialog__report-body">
                    <p className="profile-dialog__report-title">
                      {report.title}
                    </p>
                    <p className="auth-dialog__hint">
                      {[
                        state.categories.get(report.report_category_id),
                        formatDate(report.created_at, locale),
                      ]
                        .filter(Boolean)
                        .join(" - ")}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </>
        ))}
      <footer className="auth-dialog__actions">
        <CloseButton dialogRef={dialogRef} />
      </footer>
    </>
  );
}
