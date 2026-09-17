import { createReadStream, createWriteStream } from "node:fs";
import { lstat, mkdir, readdir, realpath, stat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { pipeline } from "node:stream/promises";
import { Transform } from "node:stream";
import { join, relative, resolve, sep } from "node:path";
import { assertNoSymlinkComponents, safeRegularFile, sha256File } from "./contracts.js";
import { runPhase3, type Phase3RunResult, type Phase3WorkOrder } from "./phase3.js";

export type RunResult = Phase3RunResult;
export type SnapshotOrder = Pick<Phase3WorkOrder, "workspace" | "access" | "context_files" | "budget">;
const MAX_SNAPSHOT_FILES = 2048;
const MAX_SNAPSHOT_DEPTH = 32;
const MAX_SNAPSHOT_DIRECTORIES = 4096;
const snapshotBytes = (order: SnapshotOrder): number => Math.min(128 * 1024 * 1024, Math.max(1024 * 1024, order.budget.output_bytes * 16));

function throwIfAborted(signal?: AbortSignal): void { if (signal?.aborted) throw new Error("CSE-PI operation cancelled"); }
function identity(entries: readonly string[]): string { return createHash("sha256").update([...entries].sort().join("\n")).digest("hex"); }

export async function contentIdentity(root: string, files: readonly string[], signal?: AbortSignal, maxBytes = Number.MAX_SAFE_INTEGER): Promise<string> {
  throwIfAborted(signal);
  const entries: string[] = []; let bytes = 0;
  for (const file of [...files].sort()) {
    throwIfAborted(signal); const checked = await safeRegularFile(root, file); const info = await stat(checked); bytes += info.size;
    if (bytes > maxBytes) throw new Error("snapshot bytes exceed Phase 1 cap");
    entries.push(file + "\0" + await sha256File(checked, signal, maxBytes - (bytes - info.size)));
  }
  return identity(entries);
}

type Traversal = { directories: number; files: number; bytes: number };
async function files(root: string, candidate: string, traversal: Traversal, maxBytes: number, signal?: AbortSignal): Promise<string[]> {
  throwIfAborted(signal); const depth = relative(root, resolve(root, candidate)).split(sep).filter(Boolean).length; if (depth > MAX_SNAPSHOT_DEPTH) throw new Error("snapshot depth exceeds Phase 1 cap");
  await assertNoSymlinkComponents(root, candidate);
  const start = await safeRegularOrDirectory(root, candidate); const info = await stat(start); throwIfAborted(signal);
  if (info.isFile()) { traversal.files += 1; if (traversal.files > MAX_SNAPSHOT_FILES) throw new Error("snapshot file count exceeds Phase 1 cap"); traversal.bytes += info.size; if (traversal.bytes > maxBytes) throw new Error("snapshot bytes exceed Phase 1 cap"); return [start]; }
  traversal.directories += 1; if (traversal.directories > MAX_SNAPSHOT_DIRECTORIES) throw new Error("snapshot directory count exceeds Phase 1 cap");
  const out: string[] = [];
  for (const entry of await readdir(start, { withFileTypes: true })) {
    throwIfAborted(signal);
    if (entry.name === ".git") throw new Error(".git administrative content cannot enter a snapshot");
    const child = join(start, entry.name); if (entry.isSymbolicLink() || !(entry.isFile() || entry.isDirectory())) throw new Error(`snapshot rejects symlink or special file: ${child}`);
    out.push(...await files(root, relative(root, child), traversal, maxBytes, signal));
  }
  return out;
}

async function safeRegularOrDirectory(root: string, candidate: string): Promise<string> {
  await assertNoSymlinkComponents(root, candidate);
  const out = resolve(root, candidate);
  try { return await safeRegularFile(root, candidate); }
  catch (error) {
    const info = await lstat(out); if (info.isSymbolicLink()) throw new Error(`snapshot rejects symlink: ${candidate}`); if (!info.isDirectory()) throw error;
    const actual = await realpath(out); if (!actual.startsWith(`${resolve(root)}/`) || actual.split("/").includes(".git")) throw new Error(`directory escapes workspace or is administrative: ${candidate}`);
    return out;
  }
}

async function copyRegularFile(source: string, destination: string, maxBytes: number, signal?: AbortSignal): Promise<number> {
  let bytes = 0;
  const limiter = new Transform({ transform(chunk, _encoding, callback) { bytes += chunk.length; if (bytes > maxBytes) callback(new Error("snapshot bytes exceed Phase 1 cap")); else { this.push(chunk); callback(); } } });
  await pipeline(createReadStream(source, { signal }), limiter, createWriteStream(destination, { flags: "wx", mode: 0o600 }), { signal });
  return bytes;
}

export async function snapshot(order: SnapshotOrder, resultDir: string, signal?: AbortSignal): Promise<{ root: string; identity: string; files: string[] }> {
  const maxSnapshotBytes = snapshotBytes(order); throwIfAborted(signal); const workspace = await realpath(order.workspace.root); throwIfAborted(signal); const selected = new Set<string>(); const traversal = { directories: 0, files: 0, bytes: 0 };
  for (const path of order.access.read_paths) {
    throwIfAborted(signal);
    for (const file of await files(workspace, path, traversal, maxSnapshotBytes, signal)) {
      throwIfAborted(signal); const rel = relative(workspace, file).replaceAll("\\", "/");
      if (rel.split("/").length > 32) throw new Error("snapshot depth exceeds Phase 1 cap");
      if (order.access.forbidden_paths.some(forbidden => rel === forbidden || rel.startsWith(`${forbidden}/`))) throw new Error(`allowlist intersects forbidden path: ${rel}`);
      if (selected.has(rel)) throw new Error(`snapshot collision: ${rel}`); selected.add(rel); if (selected.size > 2048) throw new Error("snapshot file count exceeds Phase 1 cap");
    }
  }
  const selectedFiles = [...selected].sort();
  let contextBytes = 0;
  for (const item of order.context_files) {
    throwIfAborted(signal); const file = await safeRegularFile(workspace, item.path); const info = await stat(file); contextBytes += info.size; if (contextBytes > maxSnapshotBytes) throw new Error("snapshot bytes exceed Phase 1 cap");
    if (!selected.has(relative(workspace, file).replaceAll("\\", "/"))) throw new Error(`context file is not within access.read_paths: ${item.path}`);
    if (await sha256File(file, signal, maxSnapshotBytes - (contextBytes - info.size)) !== item.sha256) throw new Error(`stale context SHA-256: ${item.path}`);
  }
  const sourceIdentity = await contentIdentity(workspace, selectedFiles, signal, maxSnapshotBytes); if (sourceIdentity !== order.workspace.expected_identity) throw new Error("stale workspace content identity");
  const root = join(resultDir, "input"); throwIfAborted(signal); await mkdir(root, { recursive: true }); throwIfAborted(signal); let bytes = 0; const copiedEntries: string[] = [];
  for (const rel of selectedFiles) {
    throwIfAborted(signal); const source = await safeRegularFile(workspace, rel); const info = await stat(source); if (bytes + info.size > maxSnapshotBytes) throw new Error("snapshot bytes exceed Phase 1 cap");
    const before = await sha256File(source, signal, info.size); throwIfAborted(signal); const destination = join(root, rel); await mkdir(resolve(destination, ".."), { recursive: true }); throwIfAborted(signal); const copiedBytes = await copyRegularFile(source, destination, info.size, signal); throwIfAborted(signal); const after = await sha256File(source, signal, info.size); const copied = await sha256File(destination, signal, copiedBytes);
    if (before !== after || before !== copied) throw new Error(`source changed during snapshot: ${rel}`); bytes += copiedBytes; copiedEntries.push(rel + "\0" + copied);
  }
  const copiedIdentity = identity(copiedEntries); if (copiedIdentity !== order.workspace.expected_identity) throw new Error("workspace content changed during snapshot");
  return { root, identity: copiedIdentity, files: selectedFiles };
}

export const run = runPhase3;
