import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { authApi } from "../api/auth";
import { signIn, signInWithGoogle } from "../api/session";
import GoogleButton from "./GoogleButton";
import "./AuthDialog.css";

type AuthMode = "sign-in" | "register";

type AuthDialogProps = {
  onClose: () => void;
};

const MIN_PASSWORD_LENGTH = 8;

/**
 * The sign-in and registration sheet. Both forms share one native dialog with
 * a switch between them; a new account is signed in right after it is made.
 * The Google button signs in from either form.
 */
export default function AuthDialog({ onClose }: AuthDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [login, setLogin] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const id = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }
    dialog.showModal();
  }, []);

  const switchMode = (next: AuthMode) => {
    setMode(next);
    setError(null);
  };

  const submit = async () => {
    if (mode === "sign-in") {
      return signIn(login.trim(), password);
    }
    const contact = { email: email.trim(), phone: phone.trim() };
    if (!contact.email && !contact.phone) {
      throw new Error("Enter an email address or a phone number.");
    }
    await authApi.register({
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: contact.email || undefined,
      phone: contact.phone || undefined,
      password,
    });
    // the account exists now, so a failed sign-in is retried from the sign-in form
    const newLogin = contact.email || contact.phone;
    setLogin(newLogin);
    try {
      return await signIn(newLogin, password);
    } catch (error) {
      setMode("sign-in");
      throw error;
    }
  };

  // one request at a time, from the form and the Google button alike
  const run = async (action: () => Promise<void>) => {
    if (busyRef.current) {
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      await action();
      onClose();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Something went wrong.",
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(submit);
  };

  const registering = mode === "register";
  const title = registering ? "Create account" : "Sign in";

  return (
    <dialog
      ref={dialogRef}
      className="auth-dialog"
      aria-labelledby={`${id}-title`}
      onClose={onClose}
      onCancel={(event) => {
        if (busyRef.current) event.preventDefault();
      }}
    >
      <form className="auth-dialog__form" onSubmit={handleSubmit}>
        <header className="auth-dialog__header">
          <h2 id={`${id}-title`} className="auth-dialog__title">
            {title}
          </h2>
          <div className="auth-dialog__switch" role="group" aria-label="Mode">
            <button
              type="button"
              className="auth-dialog__tab"
              aria-pressed={!registering}
              disabled={busy}
              onClick={() => switchMode("sign-in")}
            >
              Sign in
            </button>
            <button
              type="button"
              className="auth-dialog__tab"
              aria-pressed={registering}
              disabled={busy}
              onClick={() => switchMode("register")}
            >
              Register
            </button>
          </div>
        </header>

        {error && (
          <p className="auth-dialog__error" role="alert">
            {error}
          </p>
        )}

        {registering ? (
          <>
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
                Enter an email, a phone number, or both. Either one signs you
                in.
              </p>
            </div>
          </>
        ) : (
          <div className="auth-dialog__field">
            <label className="auth-dialog__label" htmlFor={`${id}-login`}>
              Email or phone
            </label>
            <input
              id={`${id}-login`}
              className="auth-dialog__input"
              name="username"
              autoComplete="username"
              required
              disabled={busy}
              value={login}
              onChange={(event) => setLogin(event.target.value)}
            />
          </div>
        )}

        <div className="auth-dialog__field">
          <label className="auth-dialog__label" htmlFor={`${id}-password`}>
            Password
          </label>
          <input
            id={`${id}-password`}
            className="auth-dialog__input"
            type="password"
            name="password"
            autoComplete={registering ? "new-password" : "current-password"}
            required
            minLength={registering ? MIN_PASSWORD_LENGTH : undefined}
            disabled={busy}
            aria-describedby={registering ? `${id}-password-hint` : undefined}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {registering && (
            <p id={`${id}-password-hint`} className="auth-dialog__hint">
              At least {MIN_PASSWORD_LENGTH} characters.
            </p>
          )}
        </div>

        <footer className="auth-dialog__actions">
          <button
            type="button"
            className="auth-dialog__button"
            onClick={() => dialogRef.current?.close()}
            disabled={busy}
          >
            Close
          </button>
          <button
            type="submit"
            className="auth-dialog__button auth-dialog__button--primary"
            disabled={busy}
          >
            {busy ? "Please wait..." : title}
          </button>
        </footer>

        <GoogleButton
          className="auth-dialog__google"
          onCredential={(credential) =>
            void run(() => signInWithGoogle(credential))
          }
          onError={() => setError("Google sign-in failed.")}
        />
      </form>
    </dialog>
  );
}
