import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, readdir, readlink, realpath, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { assertNoSymlinkComponents, safeRegularFile, sha256File, under } from "./contracts.js";
import { runPhase3, type Phase3RunResult, type Phase3WorkOrder } from "./phase3.js";
import type { SandboxOptions } from "./sandbox.js";

export type RunResult = Phase3RunResult;
export const run = runPhase3;
const execFileAsync = promisify(execFile);
export async function git(root: string, args: string[], signal?: AbortSignal): Promise<Buffer> {
  const result = await execFileAsync("/usr/bin/git", ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-C", root, ...args], {
    encoding: "buffer", maxBuffer: Infinity, signal, env: { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: "/dev/null", GIT_OPTIONAL_LOCKS: "0" },
  });
  return result.stdout;
}
function identity(hashes: Record<string, string>): string {
  return createHash("sha256").update(Object.keys(hashes).sort().map(path => path + "\0" + hashes[path]).join("\n")).digest("hex");
}
export async function contentIdentity(root: string, files: readonly string[], signal?: AbortSignal): Promise<string> {
  const hashes: Record<string, string> = {};
  for (const path of files) { if (signal?.aborted) throw new Error("CSE-PI operation cancelled"); hashes[path] = await sha256File(await safeRegularFile(root, path), signal); }
  if (signal?.aborted) throw new Error("CSE-PI operation cancelled");
  return identity(hashes);
}
export async function verifyIdentity(order: Phase3WorkOrder, root: string, signal?: AbortSignal): Promise<{ identity: string; files: string[] }> {
  const selected = new Set<string>();
  const walk = async (path: string): Promise<void> => {
    if (signal?.aborted) throw new Error("CSE-PI operation cancelled");
    await assertNoSymlinkComponents(root, path);
    const info = await lstat(under(root, path));
    if (info.isDirectory()) { for (const entry of await readdir(join(root, path))) await walk(path + "/" + entry); }
    else { await safeRegularFile(root, path); selected.add(path); }
  };
  for (const path of order.access.read_paths) await walk(path);
  const files = [...selected].sort();
  for (const path of files) if (order.access.forbidden_paths.some(forbidden => path === forbidden || path.startsWith(forbidden + "/"))) throw new Error("read scope intersects forbidden path: " + path);
  for (const file of order.context_files) {
    if (!selected.has(file.path)) throw new Error("context file is not within access.read_paths: " + file.path);
    if (await sha256File(await safeRegularFile(root, file.path), signal) !== file.sha256) throw new Error("stale context SHA-256: " + file.path);
  }
  const actual = await contentIdentity(root, files, signal);
  if (actual !== order.workspace.expected_identity) throw new Error("stale workspace content identity");
  return { identity: actual, files };
}
export async function worktreeOptions(order: Phase3WorkOrder, signal?: AbortSignal): Promise<SandboxOptions> {
  const root = await realpath(order.workspace.root);
  const commonGitDir = await realpath((await git(root, ["rev-parse", "--path-format=absolute", "--git-common-dir"], signal)).toString().trim());
  const dependencies: SandboxOptions["dependencies"][number][] = [];
  for (const path of order.workspace.dependency_paths ?? []) {
    const source = under(root, path); await assertNoSymlinkComponents(root, path);
    if (!(await lstat(source)).isDirectory()) throw new Error("dependency must be a directory: " + path);
    await git(root, ["check-ignore", "--quiet", "--", path], signal).catch(() => { throw new Error("dependency must be ignored by git: " + path); });
    if ((await git(root, ["ls-files", "-z", "--", path], signal)).length) throw new Error("dependency contains tracked files: " + path);
    dependencies.push({ source: await realpath(source), path });
  }
  return { commonGitDir, dependencies };
}
export async function removeWorktree(source: string, root: string): Promise<void> {
  // A cancelled add can leave an incomplete directory even after Git rolls back its registry.
  const registry = (await git(source, ["worktree", "list", "--porcelain"])).toString();
  if (!registry.split("\n").includes("worktree " + root)) { await rm(root, { recursive: true, force: true }); return; }
  // Cleanup must still run after cancellation/deadline, without pruning anyone else's worktrees.
  await execFileAsync("/usr/bin/git", ["-C", source, "worktree", "remove", "--force", root], { timeout: 30000 });
}
export type Change = { path: string; action: "created" | "modified" | "deleted"; before_sha256: string | null; after_sha256: string | null };
export async function retainCandidate(root: string, commit: string, output: string, checkScope: (paths: string[]) => void): Promise<{ changes: Change[]; diff_sha256: string }> {
  const tracked = (await git(root, ["diff", "--name-only", "-z", "--no-renames", commit, "--"])).toString().split("\0").filter(Boolean);
  const untracked = (await git(root, ["ls-files", "--others", "--exclude-standard", "-z"])).toString().split("\0").filter(Boolean);
  const pieces = [await git(root, ["diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", commit, "--"])];
  for (const path of untracked) {
    try { pieces.push(await git(root, ["diff", "--no-index", "--binary", "--", "/dev/null", path])); }
    catch (error) { const failure = error as { code?: number; stdout?: Buffer }; if (failure.code !== 1 || !failure.stdout) throw error; pieces.push(failure.stdout); }
  }
  const diff = Buffer.concat(pieces); await writeFile(join(output, "candidate.diff"), diff, { mode: 0o600 });
  const paths = [...new Set([...tracked, ...untracked])].sort(); checkScope(paths);
  const changes: Change[] = [];
  for (const path of paths) {
    let before: Buffer | null = null; let after: Buffer | null = null;
    if (!untracked.includes(path)) {
      try { before = await git(root, ["show", commit + ":" + path]); } catch { /* newly staged file */ }
    }
    const target = resolve(root, path);
    if (relative(root, target) === ".." || relative(root, target).startsWith("../") || target === root) throw new Error("candidate path escapes worktree: " + path);
    try {
      // Retain forbidden/administrative changes too, but never follow a symlink to host data.
      let ancestor = dirname(target);
      while (ancestor !== root) { if ((await lstat(ancestor)).isSymbolicLink()) throw new Error("candidate has symlink ancestor: " + path); ancestor = dirname(ancestor); }
      const info = await lstat(target);
      if (info.isSymbolicLink()) after = Buffer.from(await readlink(target));
      else { if (!info.isFile() || info.nlink !== 1) throw new Error("candidate is not a regular file: " + path); after = await readFile(target); }
    } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
    const hash = (value: Buffer | null) => value === null ? null : createHash("sha256").update(value).digest("hex");
    changes.push({ path, action: before === null ? "created" : after === null ? "deleted" : "modified", before_sha256: hash(before), after_sha256: hash(after) });
    if (after !== null) { const destination = join(output, "candidate", path); await mkdir(dirname(destination), { recursive: true }); await writeFile(destination, after, { mode: 0o600 }); }
  }
  return { changes, diff_sha256: createHash("sha256").update(diff).digest("hex") };
}
