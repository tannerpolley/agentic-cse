import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { lstat, realpath } from "node:fs/promises";
import { basename, isAbsolute, join, relative, resolve, sep } from "node:path";
import type { Phase3WorkOrder } from "./phase3.js";

export function writablePath(order: Pick<Phase3WorkOrder, "access" | "workspace">, path: string): boolean {
  try { under(order.workspace.root, path); } catch { return false; }
  const contains = (scope: string) => path === scope || path.startsWith(scope + "/");
  return basename(path) !== ".gitignore" && order.access.write_scopes.some(scope => scope.kind === "directory" ? contains(scope.path) : path === scope.path)
    && !order.access.forbidden_paths.some(contains) && !(order.workspace.dependency_paths ?? []).some(contains);
}

export function under(root: string, path: string): string {
  if (!isAbsolute(root)) throw new Error("workspace.root must be absolute");
  if (isAbsolute(path)) throw new Error(`workspace path must be relative: ${path}`);
  const out = resolve(root, path); const rel = relative(root, out);
  if (rel === "" || rel === "." || rel.startsWith(`..${sep}`) || rel === ".." || isAbsolute(rel)) throw new Error(`path escapes workspace or names its root: ${path}`);
  if (rel.split(sep).some(part => [".git", ".pi", ".codex", ".ssh", ".docker", ".aws"].includes(part))) throw new Error(`administrative or secret control content is forbidden: ${path}`);
  return out;
}
export async function assertNoSymlinkComponents(root: string, path: string): Promise<void> {
  const out = under(root, path);
  const rel = relative(resolve(root), out);
  let current = resolve(root);
  for (const component of rel.split(sep)) {
    current = join(current, component);
    if ((await lstat(current)).isSymbolicLink()) throw new Error(`symlink path component is forbidden: ${path}`);
  }
}
export async function safeRegularFile(root: string, path: string): Promise<string> {
  const out = under(root, path); await assertNoSymlinkComponents(root, path); const stat = await lstat(out); if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink > 1) throw new Error(`only unlinked regular non-symlink files are allowed: ${path}`);
  const resolved = await realpath(out); if (relative(resolve(root), resolved).startsWith("..")) throw new Error(`resolved path escapes workspace: ${path}`); return out;
}
export async function sha256File(path: string, signal?: AbortSignal): Promise<string> {
  const hash = createHash("sha256"); const stream = createReadStream(path, { signal });
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest("hex");
}
