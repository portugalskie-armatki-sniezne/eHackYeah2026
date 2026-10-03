import { useState } from "react";
import { signOut, useSession } from "./api/session";
import About from "./components/About";
import AuthDialog from "./components/AuthDialog";
import Map from "./components/Map";
import Navbar from "./components/Navbar";
import SignOutDialog from "./components/SignOutDialog";
import useHashRoute from "./components/useHashRoute";

export default function App() {
  const session = useSession();
  const route = useHashRoute();
  const [authOpen, setAuthOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);

  return (
    <main>
      <Navbar
        session={session}
        onSignIn={() => setAuthOpen(true)}
        onSignOut={() => setSignOutOpen(true)}
      />
      {route === "about" ? (
        <About />
      ) : (
        <Map onSignInRequired={() => setAuthOpen(true)} />
      )}
      {authOpen && <AuthDialog onClose={() => setAuthOpen(false)} />}
      {signOutOpen && (
        <SignOutDialog
          onClose={() => setSignOutOpen(false)}
          onConfirm={signOut}
        />
      )}
    </main>
  );
}
