import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, readdir, readlink, realpath, rm, writeFile } from "node:fs/promises";
import { basename, dirname, join, relative, resolve } from "node:path";
import { assertNoSymlinkComponents, safeRegularFile, sha256File, under } from "./contracts.js";
import { runPhase3, type Phase3RunResult, type Phase3WorkOrder } from "./phase3.js";
import type { SandboxOptions } from "./sandbox.js";

export type RunResult = Phase3RunResult;
export const run = runPhase3;
const execFileAsync = promisify(execFile);
export async function git(root: string, args: string[], signal?: AbortSignal, input?: Buffer): Promise<Buffer> {
  const pending = execFileAsync("/usr/bin/git", ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "core.excludesFile=/dev/null", "-C", root, ...args], {
    encoding: "buffer", maxBuffer: Infinity, signal, env: { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: "/dev/null", GIT_OPTIONAL_LOCKS: "0" },
  });
  if (input) { pending.child.stdin?.on("error", () => {}); pending.child.stdin?.end(input); }
  return (await pending).stdout;
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
    if ((await git(root, ["--literal-pathspecs", "ls-files", "-z", "--", path], signal)).length) throw new Error("dependency contains tracked files: " + path);
    dependencies.push({ source: await realpath(source), path });
  }
  return { commonGitDir, dependencies };
}
export async function removeWorktree(source: string, root: string): Promise<void> {
  // GNU chmod -R does not follow encountered symlinks. Restore owner access before removal,
  // independently of the run's aborted signal, for working and verification worktrees alike.
  try { if (!(await lstat(root)).isSymbolicLink()) await execFileAsync("/usr/bin/chmod", ["-R", "u+rwX", "--", root], { timeout: 30000 }); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
  // A cancelled add can leave an incomplete directory even after Git rolls back its registry.
  const registry = (await git(source, ["worktree", "list", "--porcelain", "-z"])).toString();
  if (!registry.split("\0").includes("worktree " + root)) { await rm(root, { recursive: true, force: true }); return; }
  // Cleanup must still run after cancellation/deadline, without pruning anyone else's worktrees.
  await execFileAsync("/usr/bin/git", ["-C", source, "worktree", "remove", "--force", root], { timeout: 30000 });
}
export type Change = { path: string; action: "created" | "modified" | "deleted"; before_sha256: string | null; after_sha256: string | null };
type CapturedChange = Change & { content: Buffer | null; diff: Buffer };
export async function captureCandidate(root: string, commit: string): Promise<CapturedChange[]> {
  const tracked = (await git(root, ["diff", "--name-only", "-z", "--no-renames", commit, "--"])).toString().split("\0").filter(Boolean);
  // Do not trust worker-writable ignore rules: capture all untracked files, including ignored ones.
  const untracked = (await git(root, ["ls-files", "--others", "-z"])).toString().split("\0").filter(Boolean);
  const changes: CapturedChange[] = [];
  for (const path of [...new Set([...tracked, ...untracked])].sort()) {
    let before: Buffer | null = null; let after: Buffer | null = null; let diff: Buffer;
    if (!untracked.includes(path)) {
      try { before = await git(root, ["show", commit + ":" + path]); }
      catch (error) { if ((error as { code?: number }).code !== 128) throw error; }
    }
    const target = resolve(root, path);
    if (relative(root, target) === ".." || relative(root, target).startsWith("../") || target === root) throw new Error("candidate path escapes worktree: " + path);
    try {
      let ancestor = dirname(target);
      while (ancestor !== root) { if ((await lstat(ancestor)).isSymbolicLink()) throw new Error("candidate has symlink ancestor: " + path); ancestor = dirname(ancestor); }
      const info = await lstat(target);
      if (info.isSymbolicLink()) after = Buffer.from(await readlink(target));
      else { if (!info.isFile() || info.nlink !== 1) throw new Error("candidate is not a regular file: " + path); after = await readFile(target); }
    } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
    if (untracked.includes(path)) {
      try { diff = await git(root, ["diff", "--no-index", "--binary", "--no-ext-diff", "--no-textconv", "--", "/dev/null", path]); }
      catch (error) { const failure = error as { code?: number; stdout?: Buffer }; if (failure.code !== 1 || !failure.stdout) throw error; diff = failure.stdout; }
    } else diff = await git(root, ["--literal-pathspecs", "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", commit, "--", path]); // file names are not patterns
    const hash = (value: Buffer | null) => value === null ? null : createHash("sha256").update(value).digest("hex");
    changes.push({ path, action: before === null ? "created" : after === null ? "deleted" : "modified", before_sha256: hash(before), after_sha256: hash(after), content: after, diff });
  }
  return changes;
}
export async function retainCandidate(captured: CapturedChange[], frozenRoot: string, output: string, checkScope: (paths: string[]) => void) {
  // Only committed .gitignore rules may exclude new output. Discard matches from info/exclude
  // or user excludes, as well as negations. The fresh worktree has not received the candidate yet.
  const rules = new Set((await git(frozenRoot, ["ls-files", "-z"])).toString().split("\0").filter(path => basename(path) === ".gitignore"));
  const added = captured.filter(change => change.action === "created").map(change => change.path);
  let matches: Buffer = Buffer.alloc(0);
  if (added.length) {
    try { matches = await git(frozenRoot, ["check-ignore", "--no-index", "--verbose", "-z", "--stdin"], undefined, Buffer.from(added.join("\0") + "\0")); }
    catch (error) { const failure = error as { code?: number; stdout?: Buffer }; if (failure.code !== 1) throw error; matches = failure.stdout ?? Buffer.alloc(0); }
  }
  const fields = matches.toString().split("\0"); const ignored = new Set<string>();
  for (let index = 0; index + 3 < fields.length; index += 4) if (rules.has(fields[index]) && !fields[index + 2].startsWith("!")) ignored.add(fields[index + 3]);
  const kept = captured.filter(change => !ignored.has(change.path));
  const diff = Buffer.concat(kept.map(change => change.diff)); await writeFile(join(output, "candidate.diff"), diff, { mode: 0o600 });
  // Even an ignored .gitignore is a violation, although it is not part of the candidate.
  checkScope(captured.filter(change => !ignored.has(change.path) || basename(change.path) === ".gitignore").map(change => change.path));
  const changes: Change[] = [];
  for (const { content, diff: _diff, ...change } of kept) {
    changes.push(change);
    if (content !== null) { const destination = join(output, "candidate", change.path); await mkdir(dirname(destination), { recursive: true }); await writeFile(destination, content, { mode: 0o600 }); }
  }
  return { changes, excluded_ignored_output: [...ignored].sort(), diff_sha256: createHash("sha256").update(diff).digest("hex") };
}
