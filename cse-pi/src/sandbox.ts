import { spawn } from "node:child_process";
import { access, readdir, readlink, realpath } from "node:fs/promises";
import { constants } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";

export type CommandEvidence = {
  command: string;
  exit_code: number | null;
  duration_ms: number;
  output_sha256: string;
  output_bytes: number;
  timed_out: boolean;
  output_limited: boolean;
};
export type SandboxResult = { evidence: CommandEvidence; output: string; raw_output: Buffer };
export type SandboxOptions = { commonGitDir: string; dependencies: readonly { source: string; path: string }[] };
export class CapabilityError extends Error {
  constructor(message: string) { super("CSE-PI capability error: " + message); }
}
let sandboxReady = false;

function runtimeMounts(): string[] {
  return ["--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib", "/lib", "--ro-bind-try", "/lib64", "/lib64"];
}
export async function requireSandbox(signal?: AbortSignal, timeoutMs = 2000): Promise<void> {
  if (signal?.aborted) throw new Error("CSE-PI operation cancelled");
  if (sandboxReady) return;
  try { await access("/usr/bin/bwrap", constants.X_OK); } catch { throw new CapabilityError("Bubblewrap (/usr/bin/bwrap) is required"); }
  const result = await execute(["--unshare-all", "--die-with-parent", "--clearenv", ...runtimeMounts(), "/bin/sh", "-c", "true"], "true", timeoutMs, 1024, signal);
  if (signal?.aborted) throw new Error("CSE-PI operation cancelled");
  if (result.evidence.exit_code !== 0) throw new CapabilityError("Bubblewrap capability probe failed: " + result.output);
  sandboxReady = true;
}

export async function runSandbox(command: string, worktree: string, timeoutMs: number, maxBytes: number, signal: AbortSignal | undefined, options: SandboxOptions): Promise<SandboxResult> {
  if (signal?.aborted) throw new Error("CSE-PI operation cancelled");
  if (!command || command.length > 16000) throw new Error("command must contain 1–16000 characters");
  const root = await realpath(worktree);
  const args = ["--unshare-all", "--die-with-parent", "--clearenv", "--proc", "/proc", "--dev", "/dev", ...runtimeMounts(), "--tmpfs", "/tmp", "--tmpfs", "/home",
    "--bind", root, root, "--ro-bind", options.commonGitDir, options.commonGitDir, "--ro-bind", join(root, ".git"), join(root, ".git")];
  for (const dependency of options.dependencies) {
    const target = join(root, dependency.path);
    // A synthetic directory supplies cache mount points even when the source has none.
    // Preserve dependency symlinks; bind package contents read-only without copying them.
    const caches = [".vite", ".vite-temp"];
    args.push("--tmpfs", target);
    for (const entry of await readdir(dependency.source, { withFileTypes: true })) {
      if (caches.includes(entry.name)) continue;
      const source = join(dependency.source, entry.name); const destination = join(target, entry.name);
      args.push(...(entry.isSymbolicLink() ? ["--symlink", await readlink(source), destination] : ["--ro-bind", source, destination]));
    }
    for (const cache of caches) args.push("--dir", join(target, cache));
    args.push("--remount-ro", target);
    for (const cache of caches) args.push("--tmpfs", join(target, cache));
  }
  args.push("--chdir", root,
    "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/home", "--setenv", "TMPDIR", "/tmp", "--setenv", "XDG_CACHE_HOME", "/tmp/cache", "--setenv", "LANG", "C.UTF-8",
    "--setenv", "GIT_CONFIG_NOSYSTEM", "1", "--setenv", "GIT_CONFIG_GLOBAL", "/dev/null",
    "/bin/sh", "-c", command);
  return execute(args, command, timeoutMs, maxBytes, signal);
}

async function execute(args: string[], command: string, timeoutMs: number, maxBytes: number, signal?: AbortSignal): Promise<SandboxResult> {
  const started = performance.now();
  const commandIndex = args.lastIndexOf("/bin/sh");
  const child = spawn("/usr/bin/bwrap", ["--args", "3", ...args.slice(commandIndex)], { stdio: ["ignore", "pipe", "pipe", "pipe"], detached: true, env: { PATH: "/usr/bin:/bin", LANG: "C.UTF-8" } });
  let timedOut = false; let outputLimited = false; let outputBytes = 0;
  const chunks: Buffer[] = [];
  const kill = () => { if (child.pid) { try { process.kill(-child.pid, "SIGKILL"); } catch {} } try { child.kill("SIGKILL"); } catch {} };
  const append = (part: Buffer) => {
    const remaining = maxBytes - outputBytes;
    if (remaining > 0) { const copy = part.subarray(0, remaining); chunks.push(copy); outputBytes += copy.length; }
    if (part.length > remaining) { outputLimited = true; kill(); }
  };
  child.stdout!.on("data", append); child.stderr!.on("data", append);
  const argumentPipe = child.stdio[3];
  if (argumentPipe && "end" in argumentPipe) { argumentPipe.on("error", () => {}); argumentPipe.end(Buffer.from(args.slice(0, commandIndex).join("\0"))); }
  const abort = () => kill(); signal?.addEventListener("abort", abort, { once: true }); if (signal?.aborted) kill();
  const timer = setTimeout(() => { timedOut = true; kill(); }, timeoutMs);
  const exitCode = await new Promise<number | null>((done, reject) => { child.once("error", reject); child.once("close", done); })
    .finally(() => { clearTimeout(timer); signal?.removeEventListener("abort", abort); });
  const rawOutput = Buffer.concat(chunks);
  return { evidence: { command, exit_code: exitCode, duration_ms: Math.round(performance.now() - started), output_sha256: createHash("sha256").update(rawOutput).digest("hex"), output_bytes: rawOutput.length, timed_out: timedOut, output_limited: outputLimited }, output: rawOutput.toString("utf8"), raw_output: rawOutput };
}
