import { useState } from "react";
import { signOut, useSession } from "./api/session";
import About from "./components/About";
import AuthDialog from "./components/AuthDialog";
import Map from "./components/Map";
import Navbar from "./components/Navbar";
import ProjectsCatalog from "./components/ProjectsCatalog";
import ProfileDialog from "./components/ProfileDialog";
import SignOutDialog from "./components/SignOutDialog";
import useHashRoute from "./components/useHashRoute";

export default function App() {
  const session = useSession();
  const route = useHashRoute();
  const [authOpen, setAuthOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);

  // an expired session closes the profile, so the next sign-in does not reopen it
  if (profileOpen && session.status === "signed-out") {
    setProfileOpen(false);
  }

  return (
    <main>
      <Navbar
        session={session}
        onSignIn={() => setAuthOpen(true)}
        onSignOut={() => setSignOutOpen(true)}
        onProfile={() => setProfileOpen(true)}
      />
      {route === "about" ? (
        <About />
      ) : route === "initiatives" ? (
        <ProjectsCatalog />
      ) : (
        <Map onSignInRequired={() => setAuthOpen(true)} />
      )}
      {authOpen && <AuthDialog onClose={() => setAuthOpen(false)} />}
      {profileOpen && session.status === "signed-in" && (
        <ProfileDialog
          user={session.user}
          onClose={() => setProfileOpen(false)}
        />
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
