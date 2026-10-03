import { createReportsApi, type ReportLocation } from "./reports";

// development-only bridge; replace test login with the signed-in user's session
// before connecting production forms. See README.md: Development Report Connection.
export const DEV_REPORTS_ENABLED = import.meta.env.DEV;
export const devReportsApi = createReportsApi("/api");

// public test credentials, used only by the local development flow.
const DEV_USER = {
  first_name: "Development",
  last_name: "Tester",
  email: "reports-dev@example.com",
  password: "local-report-test-only",
};

export async function getDevSession() {
  if (!DEV_REPORTS_ENABLED) {
    throw new Error("Test reports are only available in development mode.");
  }
  const login = () =>
    fetch("/api/auth/login", {
      method: "POST",
      body: new URLSearchParams({
        username: DEV_USER.email,
        password: DEV_USER.password,
      }),
    });
  let response = await login();
  if (response.status === 401) {
    const registration = await fetch("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(DEV_USER),
    });
    if (!registration.ok && registration.status !== 409) {
      throw new Error("Could not create the development test account.");
    }
    response = await login();
  }
  if (!response.ok) {
    throw new Error("Could not sign in to the development API.");
  }
  const { access_token: token } = (await response.json()) as {
    access_token: string;
  };
  const user = await fetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!user.ok) throw new Error("Could not load the development test account.");
  return { token, userId: ((await user.json()) as { id: string }).id };
}

export async function saveDevReport(
  description: string,
  location: ReportLocation,
  image: File | null,
) {
  const { token } = await getDevSession();
  const category = (await devReportsApi.categories()).find(
    (item) => item.name === "issue",
  );
  if (!category)
    throw new Error("The development database is missing the issue category.");
  return devReportsApi.create(
    {
      title: "Development test report",
      report_category_id: category.id,
      description,
      location,
      photos: image ? [image] : [],
    },
    token,
  );
}
