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
import "./AuthDialog.css";
import "./ProfileDialog.css";

type ProfileTab = "account" | "password" | "reports";

type ProfileDialogProps = {
  user: User;
  onClose: () => void;
};

const MIN_PASSWORD_LENGTH = 8;
const REPORTS_LIMIT = 50;

const ROLE_LABELS: Record<User["role"], string> = {
  user: "Resident",
  office: "Office",
  admin: "Administrator",
};

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

function formatDate(value: string) {
  return dateFormat.format(new Date(value));
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
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
    { value: "account", label: "Account" },
    { value: "password", label: "Password" },
    { value: "reports", label: "Reports" },
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
            Profile
          </h2>
          <div
            className="auth-dialog__switch"
            role="group"
            aria-label="Section"
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
  label = "Close",
}: {
  dialogRef: RefObject<HTMLDialogElement | null>;
  disabled?: boolean;
  label?: string;
}) {
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
        setError("Enter an email address or a phone number.");
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
        setNotice("Your details have been saved.");
      } catch (error) {
        setError(errorText(error));
      }
    });
  };

  if (!editing) {
    const details: [string, string][] = [
      ["Name", `${user.first_name} ${user.last_name}`],
      ["Email", user.email ?? "Not set"],
      ["Phone", user.phone ?? "Not set"],
      ["Role", ROLE_LABELS[user.role]],
      ["Google", user.google_linked ? "Linked" : "Not linked"],
      ["Member since", formatDate(user.created_at)],
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
            Edit
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
            First name
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
            Last name
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
          Email
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
          Phone
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
          Keep an email, a phone number, or both. Either one signs you in.
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
          Cancel
        </button>
        <button
          type="submit"
          className="auth-dialog__button auth-dialog__button--primary"
          disabled={busy}
        >
          {busy ? "Please wait..." : "Save"}
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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(async () => {
      setError(null);
      setNotice(null);
      if (password !== confirmation) {
        setError("The passwords do not match.");
        return;
      }
      try {
        await authApi.updateUser(user.id, { password });
        setPassword("");
        setConfirmation("");
        setNotice("Your password has been changed.");
      } catch (error) {
        setError(errorText(error));
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
          New password
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
          At least {MIN_PASSWORD_LENGTH} characters.
        </p>
      </div>
      <div className="auth-dialog__field">
        <label className="auth-dialog__label" htmlFor={`${id}-confirmation`}>
          Repeat new password
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
          {busy ? "Please wait..." : "Change password"}
        </button>
      </footer>
    </form>
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
          setState({ status: "failed", error: errorText(error) });
        }
      });
    return () => controller.abort();
  }, [user.id]);

  return (
    <>
      {state.status === "loading" && (
        <div className="profile-dialog__loading" role="status">
          <span className="profile-dialog__spinner" aria-hidden="true" />
          <span className="visually-hidden">Loading your reports...</span>
        </div>
      )}
      {state.status === "failed" && (
        <p className="auth-dialog__error" role="alert">
          {state.error}
        </p>
      )}
      {state.status === "ready" &&
        (state.reports.length === 0 ? (
          <p className="auth-dialog__text">
            You have not sent any reports yet.
          </p>
        ) : (
          <>
            <p className="auth-dialog__hint">
              {state.total > state.reports.length
                ? `Showing the latest ${state.reports.length} of ${state.total} reports.`
                : `${state.total} ${state.total === 1 ? "report" : "reports"}.`}
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
                        formatDate(report.created_at),
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
