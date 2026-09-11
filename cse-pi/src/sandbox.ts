import { spawn } from "node:child_process";
import { access, chmod, lstat, mkdir, mkdtemp, readdir, realpath, rename, rm, writeFile } from "node:fs/promises";
import { closeSync, constants, openSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { dirname, join, relative, resolve, sep } from "node:path";

export type CommandEvidence = {
  command: string;
  exit_code: number | null;
  duration_ms: number;
  output_sha256: string;
  output_bytes: number;
  timed_out: boolean;
  output_limited: boolean;
  scratch_bytes: number;
  scratch_limited: boolean;
  workspace_bytes?: number;
  workspace_limited?: boolean;
  workspace_error?: string;
};
export type SandboxResult = { evidence: CommandEvidence; output: string; raw_output: Buffer };

export class CapabilityError extends Error {
  constructor(message: string) { super("CSE-PI capability error: " + message); }
}

const MAX_SCRATCH_FILES = 2048;
const MAX_SCRATCH_DEPTH = 32;
const MAX_BYTES = 128 * 1024 * 1024;
let sandboxReady = false;
const scratchLocks = new Map<string, Promise<void>>();

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new Error("CSE-PI operation cancelled");
}

type ScratchUsage = { bytes: number; limited: boolean };
type WritableScope = { path: string; kind: "file" | "directory" };
type WorkspaceEntry = { path: string; kind: "file" | "directory" };

function quote(value: string): string { return "'" + value.replaceAll("'", "'\"'\"'") + "'"; }
function isWithin(parent: string, candidate: string): boolean { return candidate === parent || candidate.startsWith(parent + sep); }

async function withScratchLock<T>(root: string, work: () => Promise<T>): Promise<T> {
  const key = resolve(root);
  const previous = scratchLocks.get(key) ?? Promise.resolve();
  let release!: () => void;
  const current = new Promise<void>(done => { release = done; });
  scratchLocks.set(key, current);
  await previous;
  try { return await work(); }
  finally {
    release();
    if (scratchLocks.get(key) === current) scratchLocks.delete(key);
  }
}

async function scratchUsage(root: string, maxBytes: number, signal?: AbortSignal): Promise<ScratchUsage> {
  let bytes = 0;
  let files = 0;
  let limited = false;
  const walk = async (directory: string, depth: number): Promise<void> => {
    throwIfAborted(signal);
    if (depth > MAX_SCRATCH_DEPTH) { limited = true; return; }
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      throwIfAborted(signal);
      const path = join(directory, entry.name);
      if (entry.isSymbolicLink() || (!entry.isFile() && !entry.isDirectory())) { limited = true; continue; }
      if (entry.isDirectory()) { await walk(path, depth + 1); continue; }
      files += 1;
      if (files > MAX_SCRATCH_FILES) limited = true;
      bytes += (await lstat(path)).size;
      if (bytes > maxBytes) limited = true;
    }
  };
  await walk(root, 0);
  return { bytes, limited };
}

async function extractScratchArchive(root: string, archive: Buffer, maxBytes: number, signal?: AbortSignal): Promise<ScratchUsage> {
  const parent = dirname(root);
  const importRoot = await mkdtemp(join(parent, ".cse-pi-scratch-import-"));
  const destination = join(importRoot, "contents");
  const archivePath = join(importRoot, "scratch.tar");
  await mkdir(destination, { mode: 0o700 });
  try {
    throwIfAborted(signal);
    await writeFile(archivePath, archive, { mode: 0o600 });
    const child = spawn("/usr/bin/tar", ["--extract", "--file", archivePath, "--directory", destination, "--no-same-owner", "--no-same-permissions", "--no-overwrite-dir"], { stdio: "ignore", detached: true });
    let settled = false;
    const kill = () => {
      if (!settled && child.pid) { try { process.kill(-child.pid, "SIGKILL"); } catch {} }
      try { child.kill("SIGKILL"); } catch {}
    };
    const abort = () => kill();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) kill();
    const code = await new Promise<number | null>(done => {
      child.once("error", () => done(null));
      child.once("close", done);
    }).finally(() => { settled = true; signal?.removeEventListener("abort", abort); });
    if (code !== 0) return { bytes: maxBytes + 1, limited: true };
    const usage = await scratchUsage(destination, maxBytes, signal);
    if (usage.limited) return usage;
    throwIfAborted(signal);
    const backup = join(parent, ".cse-pi-scratch-backup-" + randomUUID());
    await rename(root, backup);
    try {
      await rename(destination, root);
      await rm(backup, { recursive: true, force: true });
    } catch (error) {
      try { await rename(backup, root); } catch {}
      throw error;
    }
    return usage;
  } finally {
    await rm(importRoot, { recursive: true, force: true });
  }
}

async function prepareScratch(snapshot: string, scratch: string, maxBytes: number, signal?: AbortSignal): Promise<string> {
  throwIfAborted(signal);
  await mkdir(scratch, { recursive: true, mode: 0o700 });
  const scratchStat = await lstat(scratch);
  if (scratchStat.isSymbolicLink() || !scratchStat.isDirectory()) throw new Error("scratch must be a regular directory");
  await chmod(scratch, 0o700);
  const [snapshotRoot, scratchRoot] = await Promise.all([realpath(snapshot), realpath(scratch)]);
  if (isWithin(snapshotRoot, scratchRoot) || isWithin(scratchRoot, snapshotRoot)) throw new Error("scratch must be separate from read-only snapshot");
  const usage = await scratchUsage(scratchRoot, maxBytes, signal);
  if (usage.limited) throw new Error("scratch exceeds Phase 1 cap");
  return scratchRoot;
}

async function probeSandbox(timeoutMs: number, signal?: AbortSignal): Promise<void> {
  throwIfAborted(signal);
  const args = ["--die-with-parent", "--unshare-all", "--proc", "/proc", "--dev", "/dev", "--size", "1048576", "--tmpfs", "/scratch", "--size", "1048576", "--tmpfs", "/tmp", "--clearenv", "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin"];
  for (const path of ["/lib", "/lib64"]) {
    try { await access(path); args.push("--ro-bind", path, path); } catch { /* /lib64 is optional */ }
  }
  args.push("/bin/sh", "-c", "/usr/bin/tar --version >/dev/null");
  const child = spawn("/usr/bin/bwrap", args, { stdio: "ignore", detached: true, env: { PATH: "/usr/bin:/bin" } });
  let settled = false;
  const kill = () => {
    if (!settled && child.pid) { try { process.kill(-child.pid, "SIGKILL"); } catch {} }
    try { child.kill("SIGKILL"); } catch {}
  };
  const abort = () => kill();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) kill();
  const timer = setTimeout(kill, timeoutMs);
  const code = await new Promise<number | null>((done, reject) => {
    child.once("error", reject);
    child.once("close", done);
  }).finally(() => { settled = true; clearTimeout(timer); signal?.removeEventListener("abort", abort); });
  if (signal?.aborted) throw new Error("CSE-PI operation cancelled");
  if (code !== 0) throw new CapabilityError("Bubblewrap capability probe failed (exit " + (code ?? "spawn") + ")");
}

export async function requireSandbox(signal?: AbortSignal, timeoutMs = 2000): Promise<void> {
  if (sandboxReady) { throwIfAborted(signal); return; }
  try { await access("/usr/bin/bwrap", constants.X_OK); } catch { throw new CapabilityError("Bubblewrap (/usr/bin/bwrap) is required"); }
  try { await access("/usr/bin/tar", constants.X_OK); } catch { throw new CapabilityError("required scratch archive runtime missing: /usr/bin/tar"); }
  for (const path of ["/bin/sh", "/usr", "/lib", "/lib64"]) {
    try { await lstat(path); } catch { if (path !== "/lib64") throw new CapabilityError("required runtime mount missing: " + path); }
  }
  await probeSandbox(timeoutMs, signal);
  sandboxReady = true;
}

export type SandboxOptions = { writablePaths?: readonly string[]; workspaceBytes?: number; deletePath?: string };

async function collectWorkspaceEntries(root: string, signal?: AbortSignal): Promise<WorkspaceEntry[]> {
  const entries: WorkspaceEntry[] = [];
  let files = 0;
  let directories = 0;
  const walk = async (directory: string, prefix: string, depth: number): Promise<void> => {
    throwIfAborted(signal);
    if (depth > MAX_SCRATCH_DEPTH) throw new Error("workspace exceeds depth cap");
    directories += 1;
    if (directories > MAX_SCRATCH_FILES * 2) throw new Error("workspace exceeds directory cap");
    for (const entry of (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      throwIfAborted(signal);
      const path = join(directory, entry.name);
      const relativePath = prefix ? prefix + "/" + entry.name : entry.name;
      const info = await lstat(path);
      if (info.isSymbolicLink() || (!info.isFile() && !info.isDirectory())) throw new Error("workspace contains unsafe path: " + relativePath);
      if (info.isDirectory()) {
        entries.push({ path: relativePath, kind: "directory" });
        await walk(path, relativePath, depth + 1);
      } else {
        if (info.nlink !== 1) throw new Error("workspace contains hardlink: " + relativePath);
        files += 1;
        if (files > MAX_SCRATCH_FILES) throw new Error("workspace exceeds file cap");
        entries.push({ path: relativePath, kind: "file" });
      }
    }
  };
  const rootInfo = await lstat(root);
  if (rootInfo.isSymbolicLink() || !rootInfo.isDirectory()) throw new Error("workspace root is unsafe");
  await walk(root, "", 0);
  return entries;
}

async function validateWritableScopes(root: string, paths: readonly string[], signal?: AbortSignal): Promise<WritableScope[]> {
  const sorted = [...paths].sort();
  if (new Set(sorted).size !== sorted.length) throw new Error("duplicate writable workspace paths");
  if (sorted.includes(".")) throw new Error("root writable workspace scope is unsupported");
  if (sorted.some((path, index) => !path || path.includes("\\") || path.startsWith("/") || path.split("/").some(part => !part || part === "..") || (index > 0 && path.startsWith(sorted[index - 1] + "/")))) throw new Error("writable workspace paths must be non-overlapping relative paths");
  const scopes: WritableScope[] = [];
  for (const path of sorted) {
    throwIfAborted(signal);
    let info: Awaited<ReturnType<typeof lstat>>;
    try { info = await lstat(join(root, path)); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      const parent = parentPath(path);
      if (parent) {
        const parentInfo = await lstat(join(root, parent));
        if (parentInfo.isSymbolicLink() || !parentInfo.isDirectory()) throw new Error("unsafe writable workspace parent: " + parent);
      }
      scopes.push({ path, kind: "file" });
      continue;
    }
    if (info.isSymbolicLink() || (!info.isFile() && !info.isDirectory()) || (info.isFile() && info.nlink !== 1)) throw new Error("unsafe writable workspace path: " + path);
    scopes.push({ path, kind: info.isDirectory() ? "directory" : "file" });
  }
  return scopes;
}

function scopeContains(scope: WritableScope, path: string): boolean {
  return scope.kind === "directory" ? path === scope.path || path.startsWith(scope.path + "/") : path === scope.path;
}

function parentPath(path: string): string {
  const index = path.lastIndexOf("/");
  return index < 0 ? "" : path.slice(0, index);
}

type WorkspaceMountPlan = { args: string[]; fileScopes: WritableScope[] };

function stagedWorkspaceMounts(snapshot: string, scopes: readonly WritableScope[], entries: readonly WorkspaceEntry[], workspaceBytes: number, excludedFilePath?: string): WorkspaceMountPlan {
  const directories = new Set<string>();
  for (const entry of entries) if (entry.kind === "directory") directories.add(entry.path);
  for (const entry of entries) {
    let parent = parentPath(entry.path);
    while (parent) { directories.add(parent); parent = parentPath(parent); }
  }
  for (const scope of scopes) {
    let parent = parentPath(scope.path);
    while (parent) { directories.add(parent); parent = parentPath(parent); }
  }
  const args = ["--size", String(workspaceBytes), "--tmpfs", "/workspace", "--ro-bind", snapshot, "/cse-source"];
  for (const path of [...directories].sort((a, b) => a.split("/").length - b.split("/").length || a.localeCompare(b))) args.push("--dir", "/workspace/" + path);
  for (const entry of entries) {
    if (entry.kind !== "file" || scopes.some(scope => scopeContains(scope, entry.path))) continue;
    args.push("--ro-bind", join(snapshot, entry.path), "/workspace/" + entry.path);
  }
  for (const scope of scopes.filter(item => item.kind === "directory")) args.push("--size", String(Math.max(1024, Math.floor(workspaceBytes / scopes.length))), "--tmpfs", "/workspace/" + scope.path);
  const fileScopes = scopes.filter(item => item.kind === "file" && item.path !== excludedFilePath);
  for (let index = 0; index < fileScopes.length; index += 1) args.push("--bind-data", String(5 + index), "/workspace/" + fileScopes[index].path);
  if (scopes.length && !(excludedFilePath && !parentPath(excludedFilePath))) args.push("--remount-ro", "/workspace");
  return { args, fileScopes };
}

function workspaceInitScript(scopes: readonly WritableScope[]): string {
  return scopes.map(scope => {
    const source = "/cse-source/" + scope.path;
    const target = "/workspace/" + scope.path;
    return scope.kind === "directory"
      ? "cp -a -- " + quote(source + "/.") + " " + quote(target + "/") + " || exit 125"
      : ":";
  }).join("; ");
}

function deleteMountScopes(scopes: readonly WritableScope[], path: string): WritableScope[] {
  const parent = parentPath(path);
  if (!parent || scopes.some(scope => scope.kind === "directory" && scopeContains(scope, parent))) return [...scopes];
  return [...scopes, { path: parent, kind: "directory" }];
}

function workspaceDeleteInitScript(path: string): string {
  return "mkdir -p -- " + quote("/workspace/" + (parentPath(path) || ".")) + " || exit 125; cp -a -- " + quote("/cse-source/" + path) + " " + quote("/workspace/" + path) + " || exit 125";
}

function workspaceExportScript(scopes: readonly WritableScope[]): string {
  const lines = ["rm -rf -- /scratch/.workspace-export", "mkdir -p -- /scratch/.workspace-export/workspace /scratch/.workspace-export/deleted", "workspace_export_status=0"];
  scopes.forEach((scope, index) => {
    const source = "/workspace/" + scope.path;
    const destination = "/scratch/.workspace-export/workspace/" + scope.path;
    const parent = parentPath(scope.path);
    const destinationParent = "/scratch/.workspace-export/workspace/" + (parent || ".");
    lines.push("if [ -d " + quote(source) + " ]; then mkdir -p -- " + quote(destination) + " || workspace_export_status=125; cp -a -- " + quote(source + "/.") + " " + quote(destination + "/") + " || workspace_export_status=125; elif [ -f " + quote(source) + " ]; then mkdir -p -- " + quote(destinationParent) + " || workspace_export_status=125; cp -a -- " + quote(source) + " " + quote(destination) + " || workspace_export_status=125; else mkdir -p -- /scratch/.workspace-export/deleted || workspace_export_status=125; : > /scratch/.workspace-export/deleted/" + index + " || workspace_export_status=125; fi");
  });
  lines.push("if [ \"$workspace_export_status\" -ne 0 ]; then exit 125; fi");
  return lines.join("; ");
}

async function workspaceUsage(root: string, scopes: readonly WritableScope[], maxBytes: number, signal?: AbortSignal): Promise<ScratchUsage> {
  let bytes = 0;
  let files = 0;
  let limited = false;
  const visited = new Set<string>();
  const walk = async (path: string, depth: number): Promise<void> => {
    throwIfAborted(signal);
    if (depth > MAX_SCRATCH_DEPTH) { limited = true; return; }
    const info = await lstat(path);
    if (info.isSymbolicLink() || (!info.isFile() && !info.isDirectory()) || (info.isFile() && info.nlink !== 1)) { limited = true; return; }
    if (info.isFile()) { files += 1; bytes += info.size; if (files > MAX_SCRATCH_FILES || bytes > maxBytes) limited = true; return; }
    for (const entry of await readdir(path, { withFileTypes: true })) await walk(join(path, entry.name), depth + 1);
  };
  for (const scope of scopes) {
    if (visited.has(scope.path)) continue;
    visited.add(scope.path);
    try { await walk(join(root, scope.path), 0); }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
  }
  return { bytes, limited };
}

async function safeHostTarget(root: string, path: string, allowMissing: boolean): Promise<{ target: string; info: Awaited<ReturnType<typeof lstat>> | null }> {
  const rootPath = resolve(root);
  const target = resolve(rootPath, path);
  if (!isWithin(rootPath, target)) throw new Error("scoped workspace path escapes root");
  let current = rootPath;
  for (const part of relative(rootPath, target).split(sep).filter(Boolean).slice(0, -1)) {
    current = join(current, part);
    const info = await lstat(current);
    if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("scoped workspace path has unsafe ancestor");
  }
  try {
    const info = await lstat(target);
    if (info.isSymbolicLink() || (!info.isFile() && !info.isDirectory()) || (info.isFile() && info.nlink !== 1)) throw new Error("scoped workspace target is unsafe");
    return { target, info };
  } catch (error) {
    if (!allowMissing || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    return { target, info: null };
  }
}

async function validateExportTree(root: string, maximumBytes: number, expected: "file" | "directory", signal?: AbortSignal): Promise<void> {
  const info = await lstat(root);
  if (info.isSymbolicLink() || (expected === "file" ? !info.isFile() : !info.isDirectory()) || (info.isFile() && info.nlink !== 1)) throw new Error("sandbox workspace export has the wrong type");
  if (expected === "file") { if (info.size > maximumBytes) throw new Error("sandbox workspace export exceeds its aggregate limit"); return; }
  const usage = await scratchUsage(root, maximumBytes, signal);
  if (usage.limited) throw new Error("sandbox workspace export exceeds its aggregate limit");
}

async function applyWorkspaceExport(root: string, scratch: string, scopes: readonly WritableScope[], maximumBytes: number, signal?: AbortSignal): Promise<void> {
  const exportRoot = join(scratch, ".workspace-export");
  const workspace = join(exportRoot, "workspace");
  const deleted = join(exportRoot, "deleted");
  const plans: Array<{ scope: WritableScope; target: string; staged?: string; remove: boolean }> = [];
  for (let index = 0; index < scopes.length; index += 1) {
    const scope = scopes[index];
    const target = (await safeHostTarget(root, scope.path, true)).target;
    let marker = false;
    try { const info = await lstat(join(deleted, String(index))); marker = info.isFile() && info.nlink === 1; } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
    if (marker) {
      plans.push({ scope, target, remove: true });
      continue;
    }
    const staged = join(workspace, scope.path);
    await validateExportTree(staged, maximumBytes, scope.kind, signal);
    const targetInfo = (await safeHostTarget(root, scope.path, true)).info;
    if (targetInfo && ((scope.kind === "file" && !targetInfo.isFile()) || (scope.kind === "directory" && !targetInfo.isDirectory()))) throw new Error("sandbox workspace scope changed file/directory type");
    plans.push({ scope, target, staged, remove: false });
  }
  for (const plan of plans) {
    if (plan.remove) {
      const targetInfo = (await safeHostTarget(root, plan.scope.path, true)).info;
      if (targetInfo) await rm(plan.target, { recursive: plan.scope.kind === "directory", force: true });
      continue;
    }
    if (plan.scope.kind === "file") {
      await rename(plan.staged!, plan.target);
      continue;
    }
    const targetInfo = (await safeHostTarget(root, plan.scope.path, true)).info;
    if (!targetInfo) {
      await rename(plan.staged!, plan.target);
      continue;
    }
    const backup = plan.target + ".cse-pi-workspace-backup-" + randomUUID();
    await rename(plan.target, backup);
    try {
      await rename(plan.staged!, plan.target);
      await rm(backup, { recursive: true, force: true });
    } catch (error) {
      try { await rename(backup, plan.target); } catch {}
      throw error;
    }
  }
  await rm(exportRoot, { recursive: true, force: true });
}

export async function runSandbox(command: string, snapshot: string, scratch: string, timeoutMs: number, maxBytes: number, signal?: AbortSignal, options: SandboxOptions = {}): Promise<SandboxResult> {
  return withScratchLock(scratch, () => runSandboxLocked(command, snapshot, scratch, timeoutMs, maxBytes, signal, options));
}

async function runSandboxLocked(command: string, snapshot: string, scratch: string, timeoutMs: number, maxBytes: number, signal?: AbortSignal, options: SandboxOptions = {}): Promise<SandboxResult> {
  throwIfAborted(signal);
  const writablePaths = options.writablePaths ?? [];
  if (options.workspaceBytes !== undefined && (!Number.isInteger(options.workspaceBytes) || options.workspaceBytes < 1024)) throw new Error("workspaceBytes must be at least 1024");
  if (command.length > 16_000) throw new Error("command exceeds 16000 characters");
  const snapshotRoot = await realpath(snapshot);
  const workspaceBytes = options.workspaceBytes ?? Math.min(MAX_BYTES, Math.max(1024 * 1024, maxBytes * 16));
  const scopes = await validateWritableScopes(snapshotRoot, writablePaths, signal);
  const deletePath = options.deletePath;
  if (deletePath !== undefined) {
    if (!deletePath || deletePath.includes("\\") || deletePath.startsWith("/") || deletePath.split("/").some(part => !part || part === "." || part === "..")) throw new Error("deletePath must be a relative non-escaping path");
    if (!scopes.some(scope => scopeContains(scope, deletePath))) throw new Error("deletePath is outside the writable scope");
    const target = await safeHostTarget(snapshotRoot, deletePath, false);
    if (!target.info?.isFile() || target.info.nlink !== 1) throw new Error("deletePath must name an unlinked regular file");
    if (command !== "rm -- " + quote("/workspace/" + deletePath)) throw new Error("deletePath requires the fixed native delete command");
  }
  const staged = scopes.length > 0;
  const mountScopes = deletePath ? deleteMountScopes(scopes, deletePath) : scopes;
  if (staged && mountScopes.length > Math.floor(workspaceBytes / 1024)) throw new Error("workspaceBytes is too small for the writable scope count");
  const scratchBytes = Math.min(MAX_BYTES, Math.max(1024 * 1024, maxBytes * 16, staged ? workspaceBytes + 1024 * 1024 : 0));
  const scratchRoot = await prepareScratch(snapshotRoot, scratch, scratchBytes, signal);
  const initialScratch = await scratchUsage(scratchRoot, scratchBytes, signal);
  const mountPlan = staged ? stagedWorkspaceMounts(snapshotRoot, mountScopes, await collectWorkspaceEntries(snapshotRoot, signal), workspaceBytes, deletePath) : { args: ["--ro-bind", snapshotRoot, "/workspace"], fileScopes: [] };
  const scopeQuota = mountScopes.length ? Math.max(1024, Math.floor(workspaceBytes / mountScopes.length)) : workspaceBytes;
  const fileLimitBlocks = mountPlan.fileScopes.length ? Math.max(1, Math.floor(scopeQuota / 512)) : 0;
  const commandRunner = staged && fileLimitBlocks ? "(ulimit -f " + fileLimitBlocks + " 2>/dev/null || exit 125; /bin/sh -c \"$1\" 4>&-) || command_status=$?" : "/bin/sh -c \"$1\" 4>&- || command_status=$?";
  const wrapperParts = ["set +e", "cp -a -- /scratch-seed/. /scratch/ 2>/dev/null || exit 125", staged ? workspaceInitScript(mountScopes) : ":", deletePath ? workspaceDeleteInitScript(deletePath) : ":", "command_status=0", commandRunner, staged ? workspaceExportScript(scopes) : ":", "export_status=0", "tar -C /scratch --format=ustar --create --file=- . 1>&4 2>/dev/null || export_status=$?", "if [ \"$export_status\" -ne 0 ]; then exit 125; fi", "exit \"$command_status\""];
  const wrapper = wrapperParts.join("; ");
  const args = ["--die-with-parent", "--unshare-all", "--proc", "/proc", "--dev", "/dev", "--dir", "/home", "--dir", "/scratch-seed", ...mountPlan.args, "--ro-bind", scratchRoot, "/scratch-seed", "--size", String(scratchBytes), "--tmpfs", "/scratch", "--size", String(scratchBytes), "--tmpfs", "/tmp", "--chdir", "/workspace", "--clearenv", "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/home", "--setenv", "LANG", "C.UTF-8"];
  for (const path of ["/usr", "/bin", "/lib", "/lib64"]) {
    try { await access(path); args.push("--ro-bind", path, path); } catch { /* /lib64 is optional */ }
  }
  throwIfAborted(signal);
  const started = performance.now();
  let timedOut = false;
  let outputLimited = false;
  let archiveLimited = false;
  const chunks: Buffer[] = [];
  const archiveChunks: Buffer[] = [];
  let outputBytes = 0;
  let archiveBytes = 0;
  const archiveLimit = scratchBytes + MAX_SCRATCH_FILES * 1024 + 1024 * 1024;
  const fileDescriptors: number[] = [];
  for (const scope of mountPlan.fileScopes) {
    try { fileDescriptors.push(openSync(join(snapshotRoot, scope.path), "r")); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") fileDescriptors.push(openSync("/dev/null", "r")); else throw error; }
  }
  let child: ReturnType<typeof spawn>;
  try {
    child = spawn("/usr/bin/bwrap", ["--args", "3", "/bin/sh", "-c", wrapper, "cse-pi", command], { stdio: ["ignore", "pipe", "pipe", "pipe", "pipe", ...fileDescriptors], detached: true, env: { PATH: "/usr/bin:/bin", LANG: "C.UTF-8", HOME: "/nonexistent" } });
  } finally {
    for (const descriptor of fileDescriptors) closeSync(descriptor);
  }
  const kill = () => {
    if (child.pid) { try { process.kill(-child.pid, "SIGKILL"); } catch {} }
    try { child.kill("SIGKILL"); } catch {}
  };
  const abort = () => kill();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) kill();
  const append = (part: Buffer) => {
    const remaining = maxBytes - outputBytes;
    if (remaining > 0) { const copy = part.subarray(0, remaining); chunks.push(copy); outputBytes += copy.length; }
    if (outputBytes >= maxBytes) { outputLimited = true; kill(); }
  };
  const appendArchive = (part: Buffer) => {
    const remaining = archiveLimit - archiveBytes;
    if (remaining > 0) { const copy = part.subarray(0, remaining); archiveChunks.push(copy); archiveBytes += copy.length; }
    if (archiveBytes >= archiveLimit) { archiveLimited = true; kill(); }
  };
  child.stdout!.on("data", append);
  child.stderr!.on("data", append);
  child.stdio[4]?.on("data", appendArchive);
  const argumentPipe = child.stdio[3];
  if (argumentPipe && "end" in argumentPipe) argumentPipe.end(Buffer.from(args.join("\0"), "utf8"));
  const timer = setTimeout(() => { timedOut = true; kill(); }, timeoutMs);
  const exitCode = await new Promise<number | null>((done, reject) => {
    child.once("error", reject);
    child.once("close", code => done(code));
  }).finally(() => { clearTimeout(timer); signal?.removeEventListener("abort", abort); });
  const rawOutput = Buffer.concat(chunks);
  let usage: ScratchUsage = { bytes: scratchBytes + 1, limited: true };
  if (!timedOut && !outputLimited && !archiveLimited && !signal?.aborted && archiveChunks.length > 0) {
    try { usage = await extractScratchArchive(scratchRoot, Buffer.concat(archiveChunks), scratchBytes, signal); }
    catch { usage = { bytes: scratchBytes + 1, limited: true }; }
  }
  let workspaceBytesUsed: number | undefined;
  let workspaceLimited = false;
  let initialWorkspaceBytes = 0;
  let workspaceError: string | undefined;
  if (staged) {
    initialWorkspaceBytes = (await workspaceUsage(snapshotRoot, scopes, workspaceBytes, signal)).bytes;
    if (!timedOut && !outputLimited && !archiveLimited && !signal?.aborted && !usage.limited) {
      try { await applyWorkspaceExport(snapshotRoot, scratchRoot, scopes, workspaceBytes, signal); }
      catch (error) { workspaceLimited = true; workspaceError = error instanceof Error ? error.message : String(error); }
    } else {
      workspaceLimited = true;
      workspaceError = "sandbox did not retain a complete workspace export";
    }
    try {
      const after = await workspaceUsage(snapshotRoot, scopes, workspaceBytes, signal);
      workspaceBytesUsed = after.bytes;
      workspaceLimited = workspaceLimited || after.limited || (exitCode !== 0 && after.bytes >= workspaceBytes && after.bytes > initialWorkspaceBytes);
    } catch (error) {
      workspaceLimited = true;
      workspaceError ??= error instanceof Error ? error.message : String(error);
    }
  }
  const scratchQuotaExhausted = exitCode !== 0 && usage.bytes >= scratchBytes && usage.bytes > initialScratch.bytes;
  return {
    evidence: {
      command,
      exit_code: exitCode,
      duration_ms: Math.round(performance.now() - started),
      output_sha256: createHash("sha256").update(rawOutput).digest("hex"),
      output_bytes: rawOutput.length,
      timed_out: timedOut,
      output_limited: outputLimited,
      scratch_bytes: usage.bytes,
      scratch_limited: usage.limited || scratchQuotaExhausted,
      ...(staged ? { workspace_bytes: workspaceBytesUsed ?? workspaceBytes + 1, workspace_limited: workspaceLimited, ...(workspaceError ? { workspace_error: workspaceError } : {}) } : {}),
    },
    output: rawOutput.toString("utf8"),
    raw_output: rawOutput,
  };
}
