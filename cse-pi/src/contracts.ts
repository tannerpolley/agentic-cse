import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { lstat, realpath } from "node:fs/promises";
import { isAbsolute, join, normalize, relative, resolve, sep } from "node:path";

export const SCHEMA_VERSION = 1;
const text = (value: unknown, name: string, min = 1, max = 8000): string => {
  if (typeof value !== "string" || value.length < min || value.length > max) throw new Error(`${name} must be a string of ${min}-${max} characters`);
  return value;
};
const array = (value: unknown, name: string, max = 128): unknown[] => {
  if (!Array.isArray(value) || value.length > max) throw new Error(`${name} must be an array of at most ${max} items`);
  return value;
};
const object = (value: unknown, name: string): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${name} must be an object`);
  return value as Record<string, unknown>;
};
const exact = (value: Record<string, unknown>, name: string, keys: readonly string[]): void => {
  for (const key of Object.keys(value)) if (!keys.includes(key)) throw new Error(`${name} has unknown field: ${key}`);
};
const strings = (value: unknown, name: string, max = 128) => array(value, name, max).map((item, i) => text(item, `${name}[${i}]`, 1, 8000));
const integer = (value: unknown, name: string, min: number, max: number) => {
  if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) throw new Error(`${name} must be an integer between ${min} and ${max}`);
  return value as number;
};

export type WorkOrder = {
  schema_version: 1; task_id: string; role: "investigate"; objective: string; scientific_question: string;
  workspace: { root: string; expected_identity: string }; context_files: { path: string; sha256: string; purpose: string }[];
  constraints: string[]; non_goals: string[]; access: { read_paths: string[]; write_paths: string[]; forbidden_paths: string[] };
  write_policy: "none"; network_policy: "none"; expected_artifacts: string[]; acceptance_criteria: string[]; validation: string[];
  scientific_checks: { id: string; kind: "json" | "convergence" | "plot_metadata"; path: string; sha256: string; checker_identity: string }[];
  parent_identity: string; budget: { wall_timeout_ms: number; model_turn_limit: number; command_timeout_ms: number; output_bytes: number };
  known_context?: string[]; worker?: { provider?: string; model?: string; effort?: "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max" };
};

export function parseWorkOrder(raw: unknown): WorkOrder {
  const v = object(raw, "work order");
  exact(v, "work order", ["schema_version", "task_id", "role", "objective", "scientific_question", "workspace", "context_files", "constraints", "non_goals", "access", "write_policy", "network_policy", "expected_artifacts", "acceptance_criteria", "validation", "scientific_checks", "parent_identity", "budget", "known_context", "worker"]);
  if (v.schema_version !== SCHEMA_VERSION) throw new Error("schema_version must be 1");
  if (v.role !== "investigate") throw new Error("role must be investigate");
  if (v.write_policy !== "none" || v.network_policy !== "none") throw new Error("only write_policy=none and network_policy=none are supported");
  const workspace = object(v.workspace, "workspace"); exact(workspace, "workspace", ["root", "expected_identity"]);
  const access = object(v.access, "access"); exact(access, "access", ["read_paths", "write_paths", "forbidden_paths"]);
  const normalizePaths = (value: unknown, name: string) => strings(value, name).map(path => { const normalized = normalize(path); if (normalized === "." || normalized.startsWith(`..${sep}`) || isAbsolute(normalized)) throw new Error(`${name} contains escaping path`); return normalized.replaceAll("\\", "/"); });
  const writePaths = normalizePaths(access.write_paths, "access.write_paths"); if (writePaths.length) throw new Error("write_policy=none requires access.write_paths to be empty");
  const context = array(v.context_files, "context_files").map((item, i) => { const f = object(item, `context_files[${i}]`); exact(f, `context_files[${i}]`, ["path", "sha256", "purpose"]); const sha256 = text(f.sha256, `context_files[${i}].sha256`, 64, 64); if (!/^[a-f0-9]{64}$/.test(sha256)) throw new Error(`context_files[${i}].sha256 must be lowercase SHA-256`); return { path: normalizePaths([text(f.path, `context_files[${i}].path`)], `context_files[${i}].path`)[0], sha256, purpose: text(f.purpose, `context_files[${i}].purpose`) }; });
  const checks = array(v.scientific_checks, "scientific_checks").map((item, i) => { const c = object(item, `scientific_checks[${i}]`); exact(c, `scientific_checks[${i}]`, ["id", "kind", "path", "sha256", "checker_identity"]); const kind = text(c.kind, `scientific_checks[${i}].kind`); if (!["json", "convergence", "plot_metadata"].includes(kind)) throw new Error(`scientific_checks[${i}].kind is unsupported`); const sha256 = text(c.sha256, `scientific_checks[${i}].sha256`, 64, 64); if (!/^[a-f0-9]{64}$/.test(sha256)) throw new Error(`scientific_checks[${i}].sha256 must be lowercase SHA-256`); return { id: text(c.id, `scientific_checks[${i}].id`, 1, 120), kind: kind as "json" | "convergence" | "plot_metadata", path: normalizePaths([text(c.path, `scientific_checks[${i}].path`)], `scientific_checks[${i}].path`)[0], sha256, checker_identity: text(c.checker_identity, `scientific_checks[${i}].checker_identity`, 1, 200) }; });
  const budget = object(v.budget, "budget"); exact(budget, "budget", ["wall_timeout_ms", "model_turn_limit", "command_timeout_ms", "output_bytes"]);
  let worker: { provider?: string; model?: string; effort?: "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max" } | undefined;
  if (v.worker !== undefined) { const w = object(v.worker, "worker"); exact(w, "worker", ["provider", "model", "effort"]); if (w.effort !== undefined && !["off", "minimal", "low", "medium", "high", "xhigh", "max"].includes(text(w.effort, "worker.effort", 1, 20))) throw new Error("worker.effort is unsupported"); worker = { provider: w.provider === undefined ? undefined : text(w.provider, "worker.provider", 1, 120), model: w.model === undefined ? undefined : text(w.model, "worker.model", 1, 200), effort: w.effort as typeof worker extends { effort?: infer E } ? E : never }; }
  const expectedIdentity = text(workspace.expected_identity, "workspace.expected_identity", 64, 64);
  if (!/^[a-f0-9]{64}$/.test(expectedIdentity)) throw new Error("workspace.expected_identity must be a lowercase SHA-256 content identity");
  return { schema_version: 1, task_id: text(v.task_id, "task_id", 1, 120), role: "investigate", objective: text(v.objective, "objective"), scientific_question: text(v.scientific_question, "scientific_question"), workspace: { root: text(workspace.root, "workspace.root"), expected_identity: expectedIdentity }, context_files: context, constraints: strings(v.constraints, "constraints"), non_goals: strings(v.non_goals, "non_goals"), access: { read_paths: normalizePaths(access.read_paths, "access.read_paths"), write_paths: [], forbidden_paths: normalizePaths(access.forbidden_paths, "access.forbidden_paths") }, write_policy: "none", network_policy: "none", expected_artifacts: strings(v.expected_artifacts, "expected_artifacts"), acceptance_criteria: strings(v.acceptance_criteria, "acceptance_criteria"), validation: strings(v.validation, "validation"), scientific_checks: checks, parent_identity: text(v.parent_identity, "parent_identity", 1, 400), budget: { wall_timeout_ms: integer(budget.wall_timeout_ms, "budget.wall_timeout_ms", 1000, 86_400_000), model_turn_limit: integer(budget.model_turn_limit, "budget.model_turn_limit", 1, 100), command_timeout_ms: integer(budget.command_timeout_ms, "budget.command_timeout_ms", 100, 3_600_000), output_bytes: integer(budget.output_bytes, "budget.output_bytes", 1024, 100_000_000) }, known_context: v.known_context === undefined ? undefined : strings(v.known_context, "known_context"), worker };
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
export async function sha256File(path: string, signal?: AbortSignal, maxBytes = Number.MAX_SAFE_INTEGER): Promise<string> {
  const hash = createHash("sha256"); let bytes = 0; const stream = createReadStream(path, { signal });
  for await (const chunk of stream) { bytes += chunk.length; if (bytes > maxBytes) throw new Error(`file exceeds ${maxBytes} byte limit: ${path}`); hash.update(chunk); }
  return hash.digest("hex");
}
