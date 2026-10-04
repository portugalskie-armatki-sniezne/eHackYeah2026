/**
 * Every string the interface shows in its own voice, per language. Text that
 * comes from the database (reports, letters, statuses) is not in here and is
 * shown exactly as stored.
 */

export const locales = ["en", "pl"] as const;

export type Locale = (typeof locales)[number];

/** The two kinds of pin; mirrors ReportCategoryName of the API. */
type PinKind = "issue" | "improvement";

export function isLocale(value: unknown): value is Locale {
  return (
    typeof value === "string" && (locales as readonly string[]).includes(value)
  );
}

const en = {
  language: {
    label: "Language",
    names: { en: "English", pl: "Polski" } as Record<Locale, string>,
    switchTo: (name: string) => `Switch language to ${name}`,
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
  reports: {
    title: "Reports",
    lede: "Every case on the map in one list, with its status and the discussion under it. Office and admin accounts move cases along and answer them with official comments.",
    backToMap: "Go back to map",
    signInToComment: "Sign in to comment",
    loading: "Loading cases...",
    empty: "No cases match.",
    search: "Search",
    searchPlaceholder: "Search by title or description...",
    statusFilter: "Status",
    allStatuses: "All",
    shown: (shown: number, total: number) => `${shown} of ${total} cases`,
    kinds: { issue: "Fault report", improvement: "Improvement idea" },
    statuses: {
      created: "Created",
      reported: "Reported",
      inprogress: "In progress",
      finished: "Finished",
    },
    setStatus: "Set status",
    reportCount: (total: number) =>
      `${total} ${total === 1 ? "report" : "reports"}`,
    remove: "Remove case",
    removeHint:
      "Takes the pin off the map with its reports, photos, and comments.",
    confirmRemove: "Remove for good",
    removing: "Removing...",
    cancel: "Cancel",
    showComments: "Show comments",
    hideComments: "Hide comments",
    loadingComments: "Loading comments...",
    noComments: "No comments yet.",
    official: "Official",
    office: "Office",
    resident: "Resident",
    you: "You",
    deleteComment: "Delete",
    composeLabel: "New comment",
    composePlaceholder: "Write a comment...",
    highlight: "Highlight as official",
    post: "Post",
    posting: "Posting...",
    somethingWrong: "Something went wrong.",
    officialResponse: "Official response",
    photoOf: (title: string) => `Photo of the case "${title}"`,
    noPhoto: "No photo yet",
    proposePhoto: "Propose photo",
    proposePhotoMock:
      "Mockup: offering a photo for this case is not wired up yet.",
  },
  status: {
    created: "Created",
    reported: "Reported",
    inprogress: "In progress",
    finished: "Finished",
    unknown: "Unknown",
  },
  auth: {
    signIn: "Sign in",
    createAccount: "Create account",
    register: "Register",
    mode: "Mode",
    firstName: "First name",
    lastName: "Last name",
    email: "Email",
    phone: "Phone",
    contactHint:
      "Enter an email, a phone number, or both. Either one signs you in.",
    contactRequired: "Enter an email address or a phone number.",
    login: "Email or phone",
    password: "Password",
    passwordHint: (min: number) => `At least ${min} characters.`,
    close: "Close",
    pleaseWait: "Please wait...",
    googleFailed: "Google sign-in failed.",
    somethingWrong: "Something went wrong.",
  },
  signOut: {
    title: "Sign out",
    question: "Are you sure you want to sign out?",
    cancel: "Cancel",
    confirm: "Sign out",
  },
  map: {
    label: "Map",
    canvasLabel:
      "Map. Use the arrow keys to pan and the plus and minus keys to zoom.",
    categoriesError: "The report categories could not be loaded.",
    newPin: "New pin",
    pinLabel: (
      kind: PinKind,
      number: number,
      status: string | null,
      reportCount: number,
      description: string,
    ) =>
      `${kind === "improvement" ? "Improvement" : "Fault"} pin ${number}${
        status ? `, ${status.toLowerCase()}` : ""
      }${reportCount > 1 ? `, ${reportCount} reports` : ""}: ${description}`,
  },
  pin: {
    issueTab: "Fault / report",
    initiativeTab: "Community initiative",
    newMarker: "New marker",
    description: "Description",
    descriptionPlaceholder: "What is happening here?",
    image: "Image",
    chosenImage: "Chosen image",
    noImage: "No image",
    changeImage: "Change image",
    chooseImage: "Choose image",
    close: "Close",
    cancel: "Cancel",
    saving: "Saving...",
    addMarker: "Add marker",
    saveFailed: "Could not save the report.",
    matchFound: (percent: number) =>
      `Similar innovation found (${percent}% match)`,
    useProject: "Build on this project",
    saveAsNew: "Submit as a new idea",
    backToEdit: "Back to editing",
    ideaLabel: "Your idea for this place",
    ideaPlaceholder:
      "Describe your proposal for an initiative or innovation at this location...",
    checking: "Checking the database...",
    sendInitiative: "Send initiative",
  },
  photoReport: {
    title: "Photo report",
    hint: "Filed where you are standing.",
    photoAlt: "The photo just taken",
    description: "Description",
    descriptionPlaceholder: "What is in the photo?",
    discard: "Discard photo",
    send: "Send report",
    saving: "Saving...",
    saveFailed: "Could not save the photo report.",
  },
  marker: {
    kinds: { issue: "Fault report", improvement: "Improvement idea" },
    close: "Close",
    photoOf: (title: string) => `Photo of: ${title}`,
    reportPhoto: "Report photo",
    loading: "Loading...",
    noPhoto: "No photo yet",
    photos: "Photos",
    photoIndex: (number: number, total: number) =>
      `Photo ${number} of ${total}`,
    reportCount: (total: number) =>
      `${total} ${total === 1 ? "report" : "reports"}`,
    report: "Report",
    loadingReport: "Loading report",
    loadFailed: "Could not load the report.",
    likeFailed: "Could not save the like.",
    postFailed: "Could not post the comment.",
    justNow: "just now",
    to: "To",
    subject: "Subject",
    noEmail: "no email on record",
    notAssigned: "not assigned yet",
    ropsLabel: "ROPS innovation",
    ropsLink: "See the innovation model on rops.krakow.pl",
    officialResponse: "Official response",
    comments: (total: number) =>
      total === 0
        ? "Comments"
        : total === 1
          ? "1 comment"
          : `${total} comments`,
    noComments: "Nobody has weighed in yet. Be the first.",
    you: "You",
    office: "Office",
    resident: "Resident",
    official: "Official",
    likesUnlike: " likes, unlike",
    likesLike: " likes, like",
    newComment: "New comment",
    writeComment: "Write a comment...",
    posting: "Posting...",
    post: "Post",
    signInToComment: "Sign in to comment",
    commentsTab: "Comments",
    reportsTab: "Reports",
    closePanel: "Close panel",
    back: "Back",
    reportsLoadFailed: "Could not load the reports.",
    loadingReports: "Loading reports...",
    noReports: "No reports to show.",
    reportPhotoOf: (number: number, title: string) =>
      `Photo ${number} of: ${title}`,
    contactInstitution: "Contact institution",
    recipientFailed: "Could not find a recipient.",
    findingRecipient: "Finding a suggested recipient...",
    recipientLoadFailed: "Could not load the suggested recipient.",
    tryAgain: "Try again",
    noInstitution: "No matching institution found.",
    suggestedRecipient:
      "Suggested recipient based on the report and location. Not assigned yet.",
    checkingSignIn: "Checking sign-in...",
    signInToFindRecipient: "Sign in to find a recipient",
  },
  catalog: {
    title: "Social Innovation Library",
    lede: "Proven models and innovations from the library of ROPS Kraków, the regional social policy centre. Get inspired and propose bringing one to your neighbourhood.",
    backToMap: "Go back to map",
    search: "Search",
    searchPlaceholder:
      "Search innovations (e.g. seniors, board, integration)...",
    categoryFilter: "Category",
    all: (total: number) => `All (${total})`,
    shown: (shown: number, total: number) => `${shown} of ${total} innovations`,
    loadFailed: "Could not load the innovation library.",
    loading: "Loading social innovations...",
    empty: "No innovations match the chosen criteria.",
    description: "What it is",
    problem: "Problem",
    targetGroup: "Target group",
    beneficiaries: "For whom",
    effectiveness: "Does it work",
    authors: "Authors",
    collapse: "Hide details",
    details: "Innovation details",
    source: "See on rops.krakow.pl",
    proposeOnMap: "Propose on the map",
    proposeTitle: "Go to the map and point out a location",
  },
  api: {
    requestFailed: (status: number) => `Request failed (${status}).`,
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
  filters: {
    label: "Filter",
    open: "Filter the pins on the map",
    heading: "Show on the map",
    kind: "Kind",
    status: "Status",
    kinds: {
      issue: "Fault reports",
      improvement: "Improvement ideas",
    } as Record<PinKind, string>,
    shown: (shown: number, total: number) => `${shown} of ${total} pins shown`,
    selectAll: "Show all",
    clear: "Hide all",
  },
  profile: {
    title: "Profile",
    section: "Section",
    tabs: {
      account: "Account",
      password: "Password",
      reports: "Reports",
    },
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
    switchTo: (name: string) => `Zmień język na ${name}`,
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
  reports: {
    title: "Zgłoszenia",
    lede: "Wszystkie sprawy z mapy na jednej liście, ze statusem i dyskusją pod każdą z nich. Konta urzędu i administratora zmieniają status i odpowiadają oficjalnymi komentarzami.",
    backToMap: "Wróć do mapy",
    signInToComment: "Zaloguj się, aby komentować",
    loading: "Wczytywanie spraw...",
    empty: "Brak spraw spełniających kryteria.",
    search: "Szukaj",
    searchPlaceholder: "Szukaj po tytule lub opisie...",
    statusFilter: "Status",
    allStatuses: "Wszystkie",
    shown: (shown: number, total: number) => `${shown} z ${plCases(total)}`,
    kinds: { issue: "Zgłoszenie usterki", improvement: "Pomysł na ulepszenie" },
    statuses: {
      created: "Utworzone",
      reported: "Zgłoszone",
      inprogress: "W trakcie",
      finished: "Zakończone",
    },
    setStatus: "Ustaw status",
    reportCount: (total: number) => plReports(total),
    remove: "Usuń sprawę",
    removeHint:
      "Zdejmuje pinezkę z mapy razem ze zgłoszeniami, zdjęciami i komentarzami.",
    confirmRemove: "Usuń bezpowrotnie",
    removing: "Usuwanie...",
    cancel: "Anuluj",
    showComments: "Pokaż komentarze",
    hideComments: "Ukryj komentarze",
    loadingComments: "Wczytywanie komentarzy...",
    noComments: "Nie ma jeszcze komentarzy.",
    official: "Oficjalny",
    office: "Urząd",
    resident: "Mieszkaniec",
    you: "Ty",
    deleteComment: "Usuń",
    composeLabel: "Nowy komentarz",
    composePlaceholder: "Napisz komentarz...",
    highlight: "Wyróżnij jako oficjalny",
    post: "Opublikuj",
    posting: "Publikowanie...",
    somethingWrong: "Coś poszło nie tak.",
    officialResponse: "Oficjalna odpowiedź",
    photoOf: (title: string) => `Zdjęcie sprawy „${title}”`,
    noPhoto: "Brak zdjęcia",
    proposePhoto: "Zaproponuj zdjęcie",
    proposePhotoMock:
      "Makieta: proponowanie zdjęcia do tej sprawy jeszcze nie działa.",
  },
  status: {
    created: "Utworzone",
    reported: "Zgłoszone",
    inprogress: "W trakcie",
    finished: "Zakończone",
    unknown: "Nieznany",
  },
  auth: {
    signIn: "Zaloguj się",
    createAccount: "Utwórz konto",
    register: "Zarejestruj się",
    mode: "Tryb",
    firstName: "Imię",
    lastName: "Nazwisko",
    email: "E-mail",
    phone: "Telefon",
    contactHint:
      "Podaj e-mail, numer telefonu lub oba. Każde z nich pozwala się zalogować.",
    contactRequired: "Podaj adres e-mail lub numer telefonu.",
    login: "E-mail lub telefon",
    password: "Hasło",
    passwordHint: (min: number) => `Co najmniej ${min} znaków.`,
    close: "Zamknij",
    pleaseWait: "Proszę czekać...",
    googleFailed: "Logowanie przez Google nie powiodło się.",
    somethingWrong: "Coś poszło nie tak.",
  },
  signOut: {
    title: "Wyloguj",
    question: "Czy na pewno chcesz się wylogować?",
    cancel: "Anuluj",
    confirm: "Wyloguj",
  },
  map: {
    label: "Mapa",
    canvasLabel:
      "Mapa. Przesuwaj strzałkami, a przybliżaj i oddalaj klawiszami plus i minus.",
    categoriesError: "Nie udało się wczytać kategorii zgłoszeń.",
    newPin: "Nowa pinezka",
    pinLabel: (
      kind: PinKind,
      number: number,
      status: string | null,
      reportCount: number,
      description: string,
    ) =>
      `Pinezka ${kind === "improvement" ? "ulepszenia" : "usterki"} ${number}${
        status ? `, ${status.toLowerCase()}` : ""
      }${reportCount > 1 ? `, ${plReports(reportCount)}` : ""}: ${description}`,
  },
  pin: {
    issueTab: "Usterka / zgłoszenie",
    initiativeTab: "Inicjatywa społeczna",
    newMarker: "Nowe zgłoszenie",
    description: "Opis",
    descriptionPlaceholder: "Co się tu dzieje?",
    image: "Zdjęcie",
    chosenImage: "Wybrane zdjęcie",
    noImage: "Brak zdjęcia",
    changeImage: "Zmień zdjęcie",
    chooseImage: "Wybierz zdjęcie",
    close: "Zamknij",
    cancel: "Anuluj",
    saving: "Zapisywanie...",
    addMarker: "Dodaj zgłoszenie",
    saveFailed: "Nie udało się zapisać zgłoszenia.",
    matchFound: (percent: number) =>
      `Znaleziono podobną innowację (${percent}% zbieżności)`,
    useProject: "Oprzyj się na tym projekcie",
    saveAsNew: "Zgłoś jako nowy pomysł",
    backToEdit: "Wróć do edycji",
    ideaLabel: "Twój pomysł na to miejsce",
    ideaPlaceholder:
      "Opisz swoją propozycję inicjatywy lub innowacji w tej lokalizacji...",
    checking: "Sprawdzam bazę...",
    sendInitiative: "Wyślij inicjatywę",
  },
  photoReport: {
    title: "Zgłoszenie ze zdjęciem",
    hint: "Zapiszemy je w miejscu, w którym jesteś.",
    photoAlt: "Właśnie zrobione zdjęcie",
    description: "Opis",
    descriptionPlaceholder: "Co chcesz zglosić?",
    discard: "Odrzuć zdjęcie",
    send: "Wyślij zgłoszenie",
    saving: "Zapisywanie...",
    saveFailed: "Nie udało się zapisać zgłoszenia ze zdjęciem.",
  },
  marker: {
    kinds: { issue: "Zgłoszenie usterki", improvement: "Pomysł na ulepszenie" },
    close: "Zamknij",
    photoOf: (title: string) => `Zdjęcie: ${title}`,
    reportPhoto: "Zdjęcie ze zgłoszenia",
    loading: "Wczytywanie...",
    noPhoto: "Brak zdjęcia",
    photos: "Zdjęcia",
    photoIndex: (number: number, total: number) =>
      `Zdjęcie ${number} z ${total}`,
    reportCount: (total: number) => plReports(total),
    report: "Zgłoszenie",
    loadingReport: "Wczytywanie zgłoszenia",
    loadFailed: "Nie udało się wczytać zgłoszenia.",
    likeFailed: "Nie udało się zapisać polubienia.",
    postFailed: "Nie udało się opublikować komentarza.",
    justNow: "przed chwilą",
    to: "Do",
    subject: "Temat",
    noEmail: "brak adresu e-mail w rejestrze",
    notAssigned: "jeszcze nieprzypisane",
    ropsLabel: "Innowacja ROPS",
    ropsLink: "Zobacz model innowacji na rops.krakow.pl",
    officialResponse: "Oficjalna odpowiedź",
    comments: (total: number) =>
      total === 0 ? "Komentarze" : plComments(total),
    noComments: "Nikt jeszcze nie zabrał głosu. Bądź pierwszy.",
    you: "Ty",
    office: "Urząd",
    resident: "Mieszkaniec",
    official: "Oficjalny",
    likesUnlike: " polubień, cofnij polubienie",
    likesLike: " polubień, polub",
    newComment: "Nowy komentarz",
    writeComment: "Napisz komentarz...",
    posting: "Publikowanie...",
    post: "Opublikuj",
    signInToComment: "Zaloguj się, aby komentować",
    commentsTab: "Komentarze",
    reportsTab: "Zgłoszenia",
    closePanel: "Zamknij panel",
    back: "Wstecz",
    reportsLoadFailed: "Nie udało się wczytać zgłoszeń.",
    loadingReports: "Wczytywanie zgłoszeń...",
    noReports: "Brak zgłoszeń do wyświetlenia.",
    reportPhotoOf: (number: number, title: string) =>
      `Zdjęcie ${number}: ${title}`,
    contactInstitution: "Skontaktuj się z instytucją",
    recipientFailed: "Nie udało się znaleźć adresata.",
    findingRecipient: "Szukanie sugerowanego adresata...",
    recipientLoadFailed: "Nie udało się wczytać sugerowanego adresata.",
    tryAgain: "Spróbuj ponownie",
    noInstitution: "Nie znaleziono pasującej instytucji.",
    suggestedRecipient:
      "Adresat sugerowany na podstawie zgłoszenia i lokalizacji. Jeszcze nieprzypisany.",
    checkingSignIn: "Sprawdzanie logowania...",
    signInToFindRecipient: "Zaloguj się, aby znaleźć adresata",
  },
  catalog: {
    title: "Biblioteka Innowacji Społecznych",
    lede: "Sprawdzone modele i innowacje z biblioteki ROPS Kraków. Zainspiruj się i zaproponuj ich realizację w swojej okolicy.",
    backToMap: "Wróć do mapy",
    search: "Szukaj",
    searchPlaceholder:
      "Szukaj innowacji (np. seniorzy, tablica, integracja)...",
    categoryFilter: "Kategoria",
    all: (total: number) => `Wszystkie (${total})`,
    shown: (shown: number, total: number) =>
      `${shown} z ${plInnovations(total)}`,
    loadFailed: "Nie udało się załadować biblioteki innowacji.",
    loading: "Ładowanie innowacji społecznych...",
    empty: "Nie znaleziono innowacji dla wybranych kryteriów.",
    description: "Na czym polega",
    problem: "Problem",
    targetGroup: "Grupa docelowa",
    beneficiaries: "Dla kogo",
    effectiveness: "Czy to działa",
    authors: "Autorzy",
    collapse: "Zwiń szczegóły",
    details: "Szczegóły innowacji",
    source: "Zobacz na rops.krakow.pl",
    proposeOnMap: "Zaproponuj na mapie",
    proposeTitle: "Przejdź na mapę i wskaż lokalizację",
  },
  api: {
    requestFailed: (status: number) => `Żądanie nie powiodło się (${status}).`,
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
  filters: {
    label: "Filtruj",
    open: "Filtruj pinezki na mapie",
    heading: "Pokaż na mapie",
    kind: "Rodzaj",
    status: "Status",
    kinds: {
      issue: "Usterki",
      improvement: "Pomysły na ulepszenia",
    } as Record<PinKind, string>,
    shown: (shown: number, total: number) =>
      `${shown} z ${total} pinezek na mapie`,
    selectAll: "Pokaż wszystkie",
    clear: "Ukryj wszystkie",
  },
  profile: {
    title: "Profil",
    section: "Sekcja",
    tabs: {
      account: "Konto",
      password: "Hasło",
      reports: "Zgłoszenia",
    },
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

/** Polish counts: 1 sprawa, 2-4 sprawy, 5+ spraw (with the teens). */
function plCases(n: number) {
  const last = n % 10;
  const tens = n % 100;
  if (n === 1) return "1 sprawa";
  if (last >= 2 && last <= 4 && (tens < 12 || tens > 14)) return `${n} sprawy`;
  return `${n} spraw`;
}

/** Polish counts: 1 komentarz, 2-4 komentarze, 5+ komentarzy (with the teens). */
function plComments(n: number) {
  const last = n % 10;
  const tens = n % 100;
  if (n === 1) return "1 komentarz";
  if (last >= 2 && last <= 4 && (tens < 12 || tens > 14))
    return `${n} komentarze`;
  return `${n} komentarzy`;
}

/** Polish counts: 1 innowacja, 2-4 innowacje, 5+ innowacji (with the teens). */
function plInnovations(n: number) {
  const last = n % 10;
  const tens = n % 100;
  if (n === 1) return "1 innowacja";
  if (last >= 2 && last <= 4 && (tens < 12 || tens > 14))
    return `${n} innowacje`;
  return `${n} innowacji`;
}

export const messages: Record<Locale, Messages> = { en, pl };
