import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

// the same OAuth client ID as GOOGLE_CLIENT_ID of the API
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

type GoogleButtonProps = {
  className?: string;
  /** The ID token of the chosen Google account, which the API verifies. */
  onCredential: (credential: string) => void;
  onError: () => void;
};

/**
 * Google's own sign-in button. Its script loads only while the button is
 * shown, and a build without a client ID renders nothing.
 */
export default function GoogleButton({
  className,
  onCredential,
  onError,
}: GoogleButtonProps) {
  if (!CLIENT_ID) {
    return null;
  }
  return (
    <GoogleOAuthProvider clientId={CLIENT_ID}>
      <GoogleLogin
        text="continue_with"
        containerProps={{ className }}
        onSuccess={({ credential }) =>
          credential ? onCredential(credential) : onError()
        }
        onError={onError}
      />
    </GoogleOAuthProvider>
  );
}
