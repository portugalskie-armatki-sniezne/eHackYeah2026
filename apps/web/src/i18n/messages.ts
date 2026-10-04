/**
 * Every string the interface shows in its own voice, per language. Text that
 * comes from the database (reports, letters, statuses) is not in here and is
 * shown exactly as stored.
 */

export const locales = ["en", "pl"] as const;

export type Locale = (typeof locales)[number];

export function isLocale(value: unknown): value is Locale {
  return (
    typeof value === "string" && (locales as readonly string[]).includes(value)
  );
}

const en = {
  language: {
    label: "Language",
    names: { en: "English", pl: "Polski" } as Record<Locale, string>,
  },
  nav: {
    skipToMap: "Skip to map",
    openMenu: "Open menu",
    closeMenu: "Close menu",
    main: "Main",
    map: "Map",
    reports: "Reports",
    initiatives: "Initiatives",
    about: "About",
    signIn: "Sign in",
    signedInAs: "Signed in as ",
    myProfile: "My Profile",
    logout: "Logout",
  },
  about: {
    lede: "A unified platform for reporting local issues, proposing citizen initiatives, and tracking their progress. Changing your city without excessive complications.",
    backToMap: "Go back to map",
    pillars: [
      {
        title: "Report local issues",
        text: "A broken lamp, a pothole, an overflowing bin. Pin it on the map, add a photo, and we will contact the appropriate services.",
      },
      {
        title: "Propose initiatives",
        text: "A bench, a crossing, a bike rack. Put the idea where it belongs and let neighbours back it.",
      },
      {
        title: "Track their progress",
        text: "Every case carries a shared status and the institution's response, so nobody has to ask twice.",
      },
    ],
    howHeading: "How a report travels",
    steps: [
      {
        title: "Drop a pin",
        text: "Click the map where something is wrong, or take a photo from where you stand. The pin keeps the GPS position and the picture.",
      },
      {
        title: "Describe it",
        text: "A sentence is enough. The report is saved right away, before anything else happens to it.",
      },
      {
        title: "Let the machine find the office",
        text: "Deterministic classifiers and generative models read the text and the photo, decide what kind of service the problem needs, and pick the authority responsible for it from a database built from publicly available information about institutions.",
      },
      {
        title: "One issue, one case",
        text: "Reports about the same thing in the same place are merged into one master report, so one broken lamp is one case and not twenty.",
      },
      {
        title: "Follow it",
        text: "Comment, like, and watch the status change until the case is finished.",
      },
    ],
    whyHeading: "Why it exists",
    whyText:
      "Telling the right public institution about a problem should not require knowing which institution that is. Finding the office, the form, and the address is work that keeps people from reporting at all, and the same problem gets reported many times by whoever does. pomożeMy keeps the map, the photos, and the conversation in one place, works out who is responsible, and lets everyone see what happened next.",
  },
  toolbar: {
    zoom: "Zoom",
    zoomIn: "Zoom in",
    zoomOut: "Zoom out",
    noFix: "No location fix yet",
    photoReport: "Take a photo and report it at my location",
    photoReportWaiting: "Report at my location, waiting for a location fix",
    view: "View",
    recenterOnMe: "Recenter on me",
  },
  profile: {
    title: "Profile",
    section: "Section",
    tabs: {
      account: "Account",
      password: "Password",
      reports: "Reports",
      preferences: "Preferences",
    },
    language: "Language",
    close: "Close",
    edit: "Edit",
    cancel: "Cancel",
    save: "Save",
    pleaseWait: "Please wait...",
    somethingWrong: "Something went wrong.",
    roles: { user: "Resident", office: "Office", admin: "Administrator" },
    name: "Name",
    email: "Email",
    phone: "Phone",
    role: "Role",
    google: "Google",
    linked: "Linked",
    notLinked: "Not linked",
    notSet: "Not set",
    memberSince: "Member since",
    firstName: "First name",
    lastName: "Last name",
    contactHint:
      "Keep an email, a phone number, or both. Either one signs you in.",
    contactRequired: "Enter an email address or a phone number.",
    detailsSaved: "Your details have been saved.",
    newPassword: "New password",
    repeatPassword: "Repeat new password",
    passwordHint: (min: number) => `At least ${min} characters.`,
    passwordMismatch: "The passwords do not match.",
    passwordChanged: "Your password has been changed.",
    changePassword: "Change password",
    loadingReports: "Loading your reports...",
    noReports: "You have not sent any reports yet.",
    showingLatest: (shown: number, total: number) =>
      `Showing the latest ${shown} of ${total} reports.`,
    reportCount: (total: number) =>
      `${total} ${total === 1 ? "report" : "reports"}.`,
  },
};

export type Messages = typeof en;

const pl: Messages = {
  language: {
    label: "Język",
    names: { en: "English", pl: "Polski" },
  },
  nav: {
    skipToMap: "Przejdź do mapy",
    openMenu: "Otwórz menu",
    closeMenu: "Zamknij menu",
    main: "Główna",
    map: "Mapa",
    reports: "Zgłoszenia",
    initiatives: "Inicjatywy",
    about: "O nas",
    signIn: "Zaloguj się",
    signedInAs: "Zalogowano jako ",
    myProfile: "Mój profil",
    logout: "Wyloguj",
  },
  about: {
    lede: "Jedna platforma do zgłaszania lokalnych problemów, proponowania inicjatyw obywatelskich i śledzenia ich postępów. Zmieniaj swoje miasto bez zbędnych komplikacji.",
    backToMap: "Wróć do mapy",
    pillars: [
      {
        title: "Zgłaszaj lokalne problemy",
        text: "Zepsuta lampa, dziura w jezdni, przepełniony kosz. Zaznacz to na mapie, dodaj zdjęcie, a my skontaktujemy się z właściwymi służbami.",
      },
      {
        title: "Proponuj inicjatywy",
        text: "Ławka, przejście dla pieszych, stojak na rowery. Umieść pomysł tam, gdzie jego miejsce, i pozwól sąsiadom go poprzeć.",
      },
      {
        title: "Śledź ich postępy",
        text: "Każda sprawa ma wspólny status i odpowiedź instytucji, więc nikt nie musi pytać dwa razy.",
      },
    ],
    howHeading: "Jak wędruje zgłoszenie",
    steps: [
      {
        title: "Postaw pinezkę",
        text: "Kliknij na mapie tam, gdzie coś jest nie tak, albo zrób zdjęcie z miejsca, w którym stoisz. Pinezka zapamięta pozycję GPS i zdjęcie.",
      },
      {
        title: "Opisz problem",
        text: "Wystarczy jedno zdanie. Zgłoszenie zapisuje się od razu, zanim cokolwiek innego się z nim stanie.",
      },
      {
        title: "Pozwól maszynie znaleźć urząd",
        text: "Deterministyczne klasyfikatory i modele generatywne czytają tekst i zdjęcie, ustalają, jakiego rodzaju służb wymaga problem, i wybierają odpowiedzialną instytucję z bazy zbudowanej z publicznie dostępnych informacji o instytucjach.",
      },
      {
        title: "Jeden problem, jedna sprawa",
        text: "Zgłoszenia dotyczące tej samej rzeczy w tym samym miejscu są łączone w jedno zgłoszenie główne, więc jedna zepsuta lampa to jedna sprawa, a nie dwadzieścia.",
      },
      {
        title: "Śledź dalej",
        text: "Komentuj, polub i obserwuj zmiany statusu, aż sprawa zostanie zakończona.",
      },
    ],
    whyHeading: "Dlaczego istnieje",
    whyText:
      "Powiadomienie właściwej instytucji publicznej o problemie nie powinno wymagać wiedzy, która to instytucja. Szukanie urzędu, formularza i adresu to praca, która powstrzymuje ludzi przed zgłaszaniem czegokolwiek, a ten sam problem zgłasza wielokrotnie każdy, kto się na to zdecyduje. pomożeMy trzyma mapę, zdjęcia i rozmowę w jednym miejscu, ustala, kto jest odpowiedzialny, i pozwala wszystkim zobaczyć, co wydarzyło się dalej.",
  },
  toolbar: {
    zoom: "Powiększenie",
    zoomIn: "Przybliż",
    zoomOut: "Oddal",
    noFix: "Brak jeszcze ustalonej pozycji",
    photoReport: "Zrób zdjęcie i zgłoś w moim położeniu",
    photoReportWaiting: "Zgłoś w moim położeniu, czekam na ustalenie pozycji",
    view: "Widok",
    recenterOnMe: "Wyśrodkuj na mnie",
  },
  profile: {
    title: "Profil",
    section: "Sekcja",
    tabs: {
      account: "Konto",
      password: "Hasło",
      reports: "Zgłoszenia",
      preferences: "Preferencje",
    },
    language: "Język",
    close: "Zamknij",
    edit: "Edytuj",
    cancel: "Anuluj",
    save: "Zapisz",
    pleaseWait: "Proszę czekać...",
    somethingWrong: "Coś poszło nie tak.",
    roles: { user: "Mieszkaniec", office: "Urząd", admin: "Administrator" },
    name: "Imię i nazwisko",
    email: "E-mail",
    phone: "Telefon",
    role: "Rola",
    google: "Google",
    linked: "Połączone",
    notLinked: "Niepołączone",
    notSet: "Nie ustawiono",
    memberSince: "W serwisie od",
    firstName: "Imię",
    lastName: "Nazwisko",
    contactHint:
      "Podaj e-mail, numer telefonu lub oba. Każde z nich pozwala się zalogować.",
    contactRequired: "Podaj adres e-mail lub numer telefonu.",
    detailsSaved: "Twoje dane zostały zapisane.",
    newPassword: "Nowe hasło",
    repeatPassword: "Powtórz nowe hasło",
    passwordHint: (min: number) => `Co najmniej ${min} znaków.`,
    passwordMismatch: "Hasła nie są takie same.",
    passwordChanged: "Twoje hasło zostało zmienione.",
    changePassword: "Zmień hasło",
    loadingReports: "Wczytywanie Twoich zgłoszeń...",
    noReports: "Nie wysłano jeszcze żadnych zgłoszeń.",
    showingLatest: (shown: number, total: number) =>
      `Wyświetlono ${shown} najnowszych z ${total} zgłoszeń.`,
    reportCount: (total: number) => `${plReports(total)}.`,
  },
};

/** Polish counts: 1 zgłoszenie, 2-4 zgłoszenia, 5+ zgłoszeń (with the teens). */
function plReports(n: number) {
  const last = n % 10;
  const tens = n % 100;
  if (n === 1) return "1 zgłoszenie";
  if (last >= 2 && last <= 4 && (tens < 12 || tens > 14))
    return `${n} zgłoszenia`;
  return `${n} zgłoszeń`;
}

export const messages: Record<Locale, Messages> = { en, pl };
