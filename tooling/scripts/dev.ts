import { constants, copyFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dir, "../..");
const envFile = resolve(root, ".env");
const apps = ["web", "api"] as const;
type App = (typeof apps)[number];
const children = new Set<ReturnType<typeof Bun.spawn>>();
let stopped = false;

function stop() {
  stopped = true;
  for (const child of children) child.kill("SIGTERM");
}

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    stop();
    process.exit(signal === "SIGINT" ? 130 : 143);
  });
}

async function run(command: string[], cwd = root) {
  if (stopped) throw new Error("Development processes have been stopped.");
  const child = Bun.spawn(command, {
    cwd,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  children.add(child);
  try {
    const code = await child.exited;
    if (code !== 0) throw new Error(`${command[0]} failed (exit ${code}).`);
  } finally {
    children.delete(child);
  }
}

async function hasScript(app: App, script: string) {
  const manifest = await Bun.file(resolve(root, "apps", app, "package.json")).json();
  return typeof manifest.scripts?.[script] === "string" && manifest.scripts[script].trim() !== "";
}

async function runScript(app: App, script: string) {
  const envArgs = existsSync(envFile) ? ["--env-file", envFile] : [];
  await run(
    [process.execPath, "run", "--no-orphans", ...envArgs, script],
    resolve(root, "apps", app),
  );
}

async function setup() {
  await run([process.execPath, "install"]);
  try {
    copyFileSync(resolve(root, ".env.example"), envFile, constants.COPYFILE_EXCL);
    console.log("Created .env from .env.example. Review its values before starting the API.");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
  }
  for (const app of apps) {
    if (await hasScript(app, "setup")) await runScript(app, "setup");
    else console.log(`[${app}] No setup script configured yet.`);
  }
}

async function startDatabase() {
  if (!Bun.which("docker")) throw new Error("Install Docker with Compose and start Docker before running the database.");
  const compose = ["docker", "compose"];
  await run([...compose, "up", "-d", "db-seeder"]);
  await run([...compose, "wait", "db-seeder"]);
}

async function start(app: App) {
  const implemented = await hasScript(app, "dev");
  if (app === "api") {
    if (implemented && !existsSync(envFile)) throw new Error("Run bun run setup to create .env first.");
    await startDatabase();
  }
  if (!implemented) {
    console.log(`[${app}] Not implemented yet. Add a dev script to apps/${app}/package.json.`);
    return;
  }
  console.log(`[${app}] Starting development server.`);
  await runScript(app, "dev");
}

try {
  switch (Bun.argv[2]) {
    case "setup":
      await setup();
      break;
    case "all":
      await setup();
      await Promise.all(apps.map(start));
      break;
    case "web":
    case "api":
      await start(Bun.argv[2] as App);
      break;
    case "db":
      await startDatabase();
      break;
    default:
      throw new Error("Use bun run setup, all, web, db, or api.");
  }
} catch (error) {
  stop();
  console.error(error instanceof Error ? error.message : "Development command failed.");
  process.exitCode = 1;
}
