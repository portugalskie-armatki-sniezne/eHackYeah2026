import { existsSync } from "node:fs";
import { resolve } from "node:path";

const root = import.meta.dir;
const python = resolve(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
let child: ReturnType<typeof Bun.spawn> | undefined;

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    child?.kill(signal);
  });
}

async function run(command: string[]) {
  child = Bun.spawn(command, {
    cwd: root,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  const code = await child.exited;
  child = undefined;
  if (code !== 0) throw new Error(`${command[0]} failed (exit ${code}).`);
}

try {
  switch (Bun.argv[2]) {
    case "setup": {
      if (!existsSync(python)) {
        const candidates = process.platform === "win32"
          ? [["py", "-3"], ["python3"], ["python"]]
          : [["python3"], ["python"]];
        const command = candidates.find(([executable]) => Bun.which(executable));
        if (!command) throw new Error("Install Python 3.10 or newer with venv support, then run bun run setup.");
        await run([...command, "-m", "venv", ".venv"]);
      }
      await run([python, "-m", "pip", "install", "-r", "requirements.txt"]);
      break;
    }
    case "dev":
      if (!existsSync(python)) throw new Error("Run bun run setup to install API dependencies first.");
      await run([python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload", "--reload-dir", "app"]);
      break;
    default:
      throw new Error("Use the API workspace setup or dev script.");
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : "API command failed.");
  process.exitCode = 1;
}
