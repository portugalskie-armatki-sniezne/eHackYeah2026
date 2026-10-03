import { useState } from "react";
import { useSession } from "./api/useSession";
import AuthDialog from "./components/AuthDialog";
import Map from "./components/Map";
import Navbar from "./components/Navbar";
import SignOutDialog from "./components/SignOutDialog";

export default function App() {
  const { state: session, signIn, signOut } = useSession();
  const [authOpen, setAuthOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);

  return (
    <main>
      <Navbar
        session={session}
        onSignIn={() => setAuthOpen(true)}
        onSignOut={() => setSignOutOpen(true)}
      />
      <Map />
      {authOpen && (
        <AuthDialog onClose={() => setAuthOpen(false)} onSignedIn={signIn} />
      )}
      {signOutOpen && (
        <SignOutDialog
          onClose={() => setSignOutOpen(false)}
          onConfirm={signOut}
        />
      )}
    </main>
  );
}
