import { afterEach, expect, test } from "bun:test";
import { chmodSync, copyFileSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";

const fixtures: string[] = [];

afterEach(() => {
  for (const fixture of fixtures.splice(0)) rmSync(fixture, { recursive: true, force: true });
});

async function fixture() {
  const root = mkdtempSync(join(tmpdir(), "ehackyeah-dev-"));
  fixtures.push(root);
  for (const directory of ["tooling/scripts", "apps/web", "apps/api", "bin"]) {
    mkdirSync(join(root, directory), { recursive: true });
  }
  copyFileSync(join(import.meta.dir, "dev.ts"), join(root, "tooling/scripts/dev.ts"));
  await Bun.write(join(root, ".env.example"), "POSTGRES_PORT=5432\n");
  await Bun.write(join(root, "package.json"), JSON.stringify({ private: true, workspaces: ["apps/*"] }));
  for (const app of ["web", "api"]) await manifest(root, app, {});
  return root;
}

async function manifest(root: string, app: string, scripts: Record<string, string>) {
  await Bun.write(join(root, "apps", app, "package.json"), JSON.stringify({ name: app, private: true, scripts }));
}

async function command(root: string, name: string) {
  const child = Bun.spawn([process.execPath, "run", "--no-orphans", "--no-env-file", "tooling/scripts/dev.ts", name], {
    cwd: root,
    env: { ...process.env, PATH: `${join(root, "bin")}${delimiter}${process.env.PATH}` },
    stdout: "pipe",
    stderr: "pipe",
  });
  const [code, stdout, stderr] = await Promise.all([
    child.exited,
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
  ]);
  return { code, stdout, stderr };
}

async function fakeDocker(root: string, code = 0) {
  const executable = join(root, "bin/docker");
  await Bun.write(executable, `#!/usr/bin/env bun
import { appendFileSync } from "node:fs";
appendFileSync("calls.log", JSON.stringify(process.argv.slice(2)) + "\\n");
process.exit(${code});
`);
  chmodSync(executable, 0o755);
}

test("setup installs workspaces, creates configuration, preserves existing values, and runs app setup", async () => {
  const root = await fixture();
  await Bun.write(join(root, "package.json"), JSON.stringify({
    private: true,
    workspaces: ["apps/*"],
    devDependencies: { web: "workspace:*" },
  }));
  expect((await command(root, "setup")).code).toBe(0);
  expect(await Bun.file(join(root, "bun.lock")).exists()).toBe(true);
  expect(await Bun.file(join(root, "node_modules/web/package.json")).exists()).toBe(true);
  expect(await Bun.file(join(root, ".env")).text()).toBe("POSTGRES_PORT=5432\n");
  await Bun.write(join(root, ".env"), "LOCAL_VALUE=preserved\n");
  await manifest(root, "api", { setup: "bun run setup.ts" });
  await Bun.write(join(root, "apps/api/setup.ts"), `Bun.resolveSync("web/package.json", import.meta.dir);
await Bun.write("setup-result", process.env.LOCAL_VALUE ?? "missing");
`);
  expect((await command(root, "setup")).code).toBe(0);
  expect(await Bun.file(join(root, ".env")).text()).toBe("LOCAL_VALUE=preserved\n");
  expect(await Bun.file(join(root, "apps/api/setup-result")).text()).toBe("preserved");
});

test("dependency installation failure stops setup and all before app setup or startup", async () => {
  for (const name of ["setup", "all"]) {
    const root = await fixture();
    await Bun.write(join(root, "apps/web/package.json"), JSON.stringify({
      name: "web",
      private: true,
      dependencies: { missing: "file:../../missing" },
    }));
    await manifest(root, "api", { setup: "bun run setup.ts", dev: "bun run dev.ts" });
    await Bun.write(join(root, "apps/api/setup.ts"), 'await Bun.write("setup-result", "yes");');
    await Bun.write(join(root, "apps/api/dev.ts"), 'await Bun.write("started", "yes");');
    const result = await command(root, name);
    expect(result.code).toBe(1);
    expect(result.stderr).toContain("failed (exit 1).");
    expect(await Bun.file(join(root, ".env")).exists()).toBe(false);
    expect(await Bun.file(join(root, "apps/api/setup-result")).exists()).toBe(false);
    expect(await Bun.file(join(root, "apps/api/started")).exists()).toBe(false);
  }
});

test("unimplemented web does not start Docker", async () => {
  const root = await fixture();
  await fakeDocker(root);
  const result = await command(root, "web");
  expect(result.code).toBe(0);
  expect(result.stdout).toContain("[web] Not implemented yet.");
  expect(await Bun.file(join(root, "calls.log")).exists()).toBe(false);
});

test.skipIf(process.platform === "win32")("database and unimplemented API start database services without .env", async () => {
  for (const name of ["db", "api"]) {
    const root = await fixture();
    await fakeDocker(root);
    const result = await command(root, name);
    expect(result.code).toBe(0);
    const calls = (await Bun.file(join(root, "calls.log")).text()).trim().split("\n").map((call) => JSON.parse(call));
    expect(calls).toEqual([
      ["compose", "up", "-d", "db-seeder"],
      ["compose", "wait", "db-seeder"],
    ]);
    expect(await Bun.file(join(root, ".env")).exists()).toBe(false);
    if (name === "api") expect(result.stdout).toContain("[api] Not implemented yet.");
  }
});

test.skipIf(process.platform === "win32")("all installs the workspaces and starts the database for the unimplemented API", async () => {
  const root = await fixture();
  await fakeDocker(root);
  const result = await command(root, "all");
  expect(result.code).toBe(0);
  expect(await Bun.file(join(root, "bun.lock")).exists()).toBe(true);
  expect(await Bun.file(join(root, ".env")).exists()).toBe(true);
  expect(result.stdout).toContain("[web] Not implemented yet.");
  expect(result.stdout).toContain("[api] Not implemented yet.");
  const calls = (await Bun.file(join(root, "calls.log")).text()).trim().split("\n").map((call) => JSON.parse(call));
  expect(calls).toEqual([
    ["compose", "up", "-d", "db-seeder"],
    ["compose", "wait", "db-seeder"],
  ]);
});

test.skipIf(process.platform === "win32")("database command propagates startup and seed failures", async () => {
  for (const failure of ["up", "wait"]) {
    const root = await fixture();
    const executable = join(root, "bin/docker");
    await Bun.write(executable, `#!/usr/bin/env bun
process.exit(process.argv[3] === "${failure}" ? 1 : 0);
`);
    chmodSync(executable, 0o755);
    const result = await command(root, "db");
    expect(result.code).toBe(1);
    expect(result.stderr).toContain("docker failed (exit 1).");
  }
});

test.skipIf(process.platform === "win32")("all runs API setup and starts both implemented applications with root environment values", async () => {
  const root = await fixture();
  await fakeDocker(root);
  await Bun.write(join(root, ".env"), "LOCAL_VALUE=preserved\n");
  await manifest(root, "web", { dev: "bun run dev.ts" });
  await manifest(root, "api", { setup: "bun run setup.ts", dev: "bun run dev.ts" });
  await Bun.write(join(root, "apps/api/setup.ts"), 'await Bun.write("setup-result", process.env.LOCAL_VALUE ?? "missing");');
  await Bun.write(join(root, "apps/web/dev.ts"), 'await Bun.write("started", process.env.LOCAL_VALUE ?? "missing");');
  await Bun.write(join(root, "apps/api/dev.ts"), `import { appendFileSync } from "node:fs";
if (await Bun.file("setup-result").text() !== "preserved") process.exit(1);
appendFileSync("../../calls.log", "api\\n");
await Bun.write("started", process.env.LOCAL_VALUE ?? "missing");
`);
  const result = await command(root, "all");
  expect(result.code).toBe(0);
  for (const app of ["web", "api"]) {
    expect(await Bun.file(join(root, "apps", app, "started")).text()).toBe("preserved");
  }
  const calls = (await Bun.file(join(root, "calls.log")).text()).trim().split("\n");
  expect(JSON.parse(calls[0])).toEqual(["compose", "up", "-d", "db-seeder"]);
  expect(JSON.parse(calls[1])).toEqual(["compose", "wait", "db-seeder"]);
  expect(calls[2]).toBe("api");
});

test.skipIf(process.platform === "win32")("API starts the database and seed services before its dev script", async () => {
  const root = await fixture();
  await fakeDocker(root);
  await manifest(root, "api", { dev: "bun run dev.ts" });
  await Bun.write(join(root, "apps/api/dev.ts"), 'import { appendFileSync } from "node:fs"; appendFileSync("../../calls.log", "api\\n");');
  await command(root, "setup");
  expect((await command(root, "api")).code).toBe(0);
  const calls = (await Bun.file(join(root, "calls.log")).text()).trim().split("\n");
  expect(JSON.parse(calls[0])).toEqual(["compose", "up", "-d", "db-seeder"]);
  expect(JSON.parse(calls[1])).toEqual(["compose", "wait", "db-seeder"]);
  expect(calls[2]).toBe("api");
});

test.skipIf(process.platform === "win32")("database failure prevents API startup and returns a failure", async () => {
  const root = await fixture();
  await fakeDocker(root, 1);
  await manifest(root, "api", { dev: "bun run dev.ts" });
  await Bun.write(join(root, "apps/api/dev.ts"), 'await Bun.write("started", "yes");');
  await command(root, "setup");
  const result = await command(root, "api");
  expect(result.code).toBe(1);
  expect(result.stderr).toContain("docker failed (exit 1).");
  expect(await Bun.file(join(root, "apps/api/started")).exists()).toBe(false);
});

test("web runs independently and propagates development server failures", async () => {
  const root = await fixture();
  await fakeDocker(root);
  await manifest(root, "web", { dev: "bun run dev.ts" });
  await Bun.write(join(root, "apps/web/dev.ts"), "process.exit(1);");
  expect((await command(root, "web")).code).toBe(1);
  expect(await Bun.file(join(root, "calls.log")).exists()).toBe(false);
});

test.skipIf(process.platform === "win32")("all stops the running web process when API startup fails", async () => {
  const root = await fixture();
  await manifest(root, "web", { dev: "bun run dev.ts" });
  await manifest(root, "api", { dev: "bun run dev.ts" });
  await Bun.write(join(root, "apps/web/dev.ts"), 'await Bun.write("pid", String(process.pid)); setInterval(() => {}, 1000);');
  const executable = join(root, "bin/docker");
  await Bun.write(executable, `#!/usr/bin/env bun
for (let attempt = 0; attempt < 200; attempt++) {
  if (await Bun.file("apps/web/pid").exists()) process.exit(1);
  await Bun.sleep(10);
}
process.exit(1);
`);
  chmodSync(executable, 0o755);
  const result = await command(root, "all");
  expect(result.code).toBe(1);
  const pid = Number(await Bun.file(join(root, "apps/web/pid")).text());
  let running = true;
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      process.kill(pid, 0);
    } catch {
      running = false;
      break;
    }
    await Bun.sleep(10);
  }
  if (running) process.kill(pid, "SIGKILL");
  expect(running).toBe(false);
});
