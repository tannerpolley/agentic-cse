import { constants } from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash, randomUUID } from "node:crypto";
import { access, copyFile, mkdir, readdir, lstat, realpath, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import {
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
  SettingsManager,
  createAgentSession,
  defineTool,
  readStoredCredential,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { runCheck, shellQuote, type Check } from "./checks.js";
import { safeRegularFile, sha256File } from "./contracts.js";
import { ResultLifecycle, runOneTurn, tokenUsage, type Runner } from "./lifecycle.js";
import { requireSandbox, runSandbox, type SandboxResult } from "./sandbox.js";
import { safeCommandTool } from "./cse-extension.js";

export const PHASE3_SCHEMA_VERSION = 3;
export const PHASE3_ROLES = ["build"] as const;
export type Phase3Role = (typeof PHASE3_ROLES)[number];
export type Phase3Status = "completed" | "preflight" | "blocked" | "failed" | "timed_out" | "cancelled" | "needs_parent_input";
export type Phase3RunResult = { schema_version: 3; run_id: string; status: Phase3Status; result_path: string; result_sha256?: string };

type Phase3Model = { provider: string; model: string; effort: string };
type Phase3Path = { path: string; sha256: string; purpose: string };
export type Phase3WriteScope = { path: string; kind: "file" | "directory" };
type Phase3Check = Check & { checker_identity: string };
export type Phase3WorkOrder = {
  schema_version: 3;
  task_id: string;
  role: Phase3Role;
  objective: string;
  scientific_question: string;
  workspace: { root: string; expected_identity: string };
  context_files: Phase3Path[];
  known_context: string[];
  constraints: string[];
  non_goals: string[];
  access: { read_paths: string[]; write_paths: string[]; write_scopes: Phase3WriteScope[]; forbidden_paths: string[] };
  write_policy: "candidate";
  network_policy: "none";
  expected_artifacts: string[];
  acceptance_criteria: string[];
  validation: string[];
  scientific_checks: Phase3Check[];
  parent_identity: string;
  budget: { wall_timeout_ms: number; model_turn_limit: number; command_timeout_ms: number; output_bytes: number };
  worker?: { provider?: string; model?: string; effort?: string };
  specification: { text: string; required_changes: string[]; forbidden_changes: string[]; permitted_paths: string[] };
};

export type Phase3Hooks = {
  beforeFinalIntegrity?: () => void | Promise<void>;
  createSession?: (config: { role: Phase3Role; model: Phase3Model; prompt: string; tools: readonly unknown[] }) => Promise<Phase3Session>;
};
export type Phase3Session = Runner & {
  setActiveToolsByName(names: string[]): void;
  getActiveToolNames(): string[];
  thinkingLevel?: string;
  getSessionStats?: () => unknown;
  retryAttempt?: number;
  dispose(): void | Promise<void>;
};

type Snapshot = { sourceRoot: string; inputRoot: string; files: string[]; hashes: Record<string, string>; identity: string };
type Change = { path: string; action: "created" | "modified" | "deleted"; before_sha256: string | null; after_sha256: string | null };
type Placeholder = { path: string; kind: "file" | "directory" };
type Tree = { hashes: Record<string, string>; bytes: number; files: number; directories: number };
const execFileAsync = promisify(execFile);
const MAX_FILES = 2048;
const MAX_DIRECTORIES = 4096;
const MAX_DEPTH = 32;
const MAX_BYTES = 128 * 1024 * 1024;
const EFFORTS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"];
const MODEL_EFFORTS: Record<string, string[]> = { "gpt-6-astra": EFFORTS, "gpt-6.1-sol": EFFORTS, "gpt-5.6-sol": EFFORTS, "gpt-5.6-terra": EFFORTS, "gpt-5.6-luna": EFFORTS };
const ROLE_DEFAULTS: Record<Phase3Role, Phase3Model> = {
  build: { provider: "openai-codex", model: "gpt-5.6-luna", effort: "high" },
};

function isObject(value: unknown): value is Record<string, unknown> { return Boolean(value) && typeof value === "object" && !Array.isArray(value); }
function object(value: unknown, name: string): Record<string, unknown> { if (!isObject(value)) throw new Error(name + " must be an object"); return value; }
function text(value: unknown, name: string, max = 8000): string { if (typeof value !== "string" || value.length < 1 || value.length > max) throw new Error(name + " must be a non-empty string of at most " + max + " characters"); return value; }
function strings(value: unknown, name: string, max = 128): string[] { if (!Array.isArray(value) || value.length > max) throw new Error(name + " must be an array"); return value.map((item, index) => text(item, name + "[" + index + "]")); }
function normalizedPath(value: unknown, name: string): string {
  const raw = text(value, name, 4000).replaceAll("\\", "/");
  const parts = raw.split("/").filter(Boolean);
  if (!parts.length || raw.startsWith("/") || parts.includes(".") || parts.includes("..")) throw new Error(name + " must be a relative non-escaping path");
  if (parts.some(part => [".git", ".pi", ".codex", ".ssh", ".aws", ".docker"].includes(part))) throw new Error(name + " contains administrative or secret content");
  return parts.join("/");
}
function pathList(value: unknown, name: string): string[] { const result = strings(value, name).map((item, index) => normalizedPath(item, name + "[" + index + "]")); if (new Set(result).size !== result.length) throw new Error(name + " contains duplicate paths"); return result; }
function parseWriteScopes(value: unknown, writePaths: readonly string[]): Phase3WriteScope[] {
  if (!writePaths.length) throw new Error("build requires candidate write_paths");
  if (!Array.isArray(value)) throw new Error("build requires explicit write_scopes");
  const scopes = value.map((raw, index) => {
    const scope = object(raw, "access.write_scopes[" + index + "]");
    if (Object.keys(scope).some(key => !["path", "kind"].includes(key))) throw new Error("write scope has an unknown field");
    const kind = text(scope.kind, "access.write_scopes[" + index + "].kind", 20);
    if (kind !== "file" && kind !== "directory") throw new Error("write scope kind is unsupported");
    return { path: normalizedPath(scope.path, "access.write_scopes[" + index + "].path"), kind: kind as Phase3WriteScope["kind"] };
  });
  if (new Set(scopes.map(scope => scope.path)).size !== scopes.length || scopes.length !== writePaths.length || scopes.some(scope => !writePaths.includes(scope.path))) throw new Error("write_scopes must exactly describe write_paths");
  return scopes;
}
function hash(value: unknown, name: string): string { const result = text(value, name, 64); if (!/^[a-f0-9]{64}$/.test(result)) throw new Error(name + " must be lowercase SHA-256"); return result; }
function integer(value: unknown, name: string, min: number, max: number): number { if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) throw new Error(name + " must be an integer between " + min + " and " + max); return value as number; }

function parseWorker(value: unknown): Phase3WorkOrder["worker"] | undefined {
  if (value === undefined) return undefined;
  const worker = object(value, "worker");
  if (Object.keys(worker).some(key => !["provider", "model", "effort"].includes(key))) throw new Error("worker has an unknown field");
  const result: Phase3WorkOrder["worker"] = {};
  if (worker.provider !== undefined) result.provider = text(worker.provider, "worker.provider", 200);
  if (worker.model !== undefined) result.model = text(worker.model, "worker.model", 200);
  if (worker.effort !== undefined) { result.effort = text(worker.effort, "worker.effort", 20); if (!EFFORTS.includes(result.effort)) throw new Error("worker.effort is unsupported"); }
  return result;
}
function parseChecks(value: unknown): Phase3Check[] {
  if (!Array.isArray(value) || value.length > 128) throw new Error("scientific_checks must be an array");
  return value.map((raw, index) => {
    const check = object(raw, "scientific_checks[" + index + "]");
    if (Object.keys(check).some(key => !["id", "kind", "path", "sha256", "checker_identity"].includes(key))) throw new Error("scientific check has an unknown field");
    const kind = text(check.kind, "scientific_checks[" + index + "].kind", 40);
    if (!["json", "convergence", "plot_metadata"].includes(kind)) throw new Error("scientific check kind is unsupported");
    return { id: text(check.id, "scientific_checks[" + index + "].id", 120), kind: kind as Check["kind"], path: normalizedPath(check.path, "scientific_checks[" + index + "].path"), sha256: hash(check.sha256, "scientific_checks[" + index + "].sha256"), checker_identity: text(check.checker_identity ?? "cse-pi-phase3", "scientific_checks[" + index + "].checker_identity", 200) };
  });
}
export function parsePhase3WorkOrder(raw: unknown): Phase3WorkOrder {
  const value = object(raw, "CSE-Pi work order");
  const fields = ["schema_version", "task_id", "role", "objective", "scientific_question", "workspace", "context_files", "known_context", "constraints", "non_goals", "access", "write_policy", "network_policy", "expected_artifacts", "acceptance_criteria", "validation", "scientific_checks", "parent_identity", "budget", "worker", "specification"];
  if (Object.keys(value).some(key => !fields.includes(key))) throw new Error("CSE-Pi work order has an unknown field");
  if (value.schema_version !== PHASE3_SCHEMA_VERSION) throw new Error("CSE-Pi schema_version must be 3");
  if (value.role !== "build") throw new Error("CSE-Pi only supports role=build");
  const role: Phase3Role = "build";
  const workspace = object(value.workspace, "workspace");
  if (Object.keys(workspace).some(key => !["root", "expected_identity"].includes(key))) throw new Error("workspace has an unknown field");
  const root = text(workspace.root, "workspace.root", 4096);
  if (!root.startsWith("/")) throw new Error("workspace.root must be absolute");
  const expectedIdentity = hash(workspace.expected_identity, "workspace.expected_identity");
  if (!Array.isArray(value.context_files) || value.context_files.length > MAX_FILES) throw new Error("context_files must be an array");
  const contextFiles = value.context_files.map((rawFile, index) => { const file = object(rawFile, "context_files[" + index + "]"); if (Object.keys(file).some(key => !["path", "sha256", "purpose"].includes(key))) throw new Error("context file has an unknown field"); return { path: normalizedPath(file.path, "context_files[" + index + "].path"), sha256: hash(file.sha256, "context_files[" + index + "].sha256"), purpose: text(file.purpose, "context_files[" + index + "].purpose") }; });
  if (new Set(contextFiles.map(file => file.path)).size !== contextFiles.length) throw new Error("context_files contains duplicate paths");
  const accessValue = object(value.access, "access");
  if (Object.keys(accessValue).some(key => !["read_paths", "write_paths", "write_scopes", "forbidden_paths"].includes(key))) throw new Error("access has an unknown field");
  const accessPaths = { read_paths: pathList(accessValue.read_paths ?? [], "access.read_paths"), write_paths: pathList(accessValue.write_paths ?? [], "access.write_paths"), forbidden_paths: pathList(accessValue.forbidden_paths ?? [], "access.forbidden_paths") };
  const access = { ...accessPaths, write_scopes: parseWriteScopes(accessValue.write_scopes, accessPaths.write_paths) };
  const writePolicy = value.write_policy;
  if (writePolicy !== "candidate") throw new Error("build requires write_policy=candidate");
  if (value.network_policy !== "none") throw new Error("only network_policy=none is supported");
  const budgetValue = object(value.budget, "budget");
  if (Object.keys(budgetValue).some(key => !["wall_timeout_ms", "model_turn_limit", "command_timeout_ms", "output_bytes"].includes(key))) throw new Error("budget has an unknown field");
  const budget = { wall_timeout_ms: integer(budgetValue.wall_timeout_ms, "budget.wall_timeout_ms", 1000, 86_400_000), model_turn_limit: integer(budgetValue.model_turn_limit, "budget.model_turn_limit", 1, 100), command_timeout_ms: integer(budgetValue.command_timeout_ms, "budget.command_timeout_ms", 100, 3_600_000), output_bytes: integer(budgetValue.output_bytes, "budget.output_bytes", 1024, 100_000_000) };
  const rawSpec = value.specification === undefined ? {} : object(value.specification, "specification");
  if (Object.keys(rawSpec).some(key => !["text", "required_changes", "forbidden_changes", "permitted_paths"].includes(key))) throw new Error("specification has an unknown field");
  const specification = { text: text(rawSpec.text ?? value.objective, "specification.text"), required_changes: strings(rawSpec.required_changes ?? [], "specification.required_changes"), forbidden_changes: strings(rawSpec.forbidden_changes ?? [], "specification.forbidden_changes"), permitted_paths: pathList(rawSpec.permitted_paths ?? access.write_paths, "specification.permitted_paths") };
  if (specification.permitted_paths.some(path => !access.write_paths.some(allowed => path === allowed || path.startsWith(allowed + "/")))) throw new Error("specification.permitted_paths exceeds write scope");
  return { schema_version: 3, task_id: text(value.task_id, "task_id", 120), role, objective: text(value.objective, "objective"), scientific_question: text(value.scientific_question, "scientific_question"), workspace: { root, expected_identity: expectedIdentity }, context_files: contextFiles, known_context: strings(value.known_context ?? [], "known_context"), constraints: strings(value.constraints ?? [], "constraints"), non_goals: strings(value.non_goals ?? [], "non_goals"), access, write_policy: writePolicy, network_policy: "none", expected_artifacts: strings(value.expected_artifacts ?? [], "expected_artifacts"), acceptance_criteria: strings(value.acceptance_criteria ?? [], "acceptance_criteria"), validation: strings(value.validation ?? [], "validation"), scientific_checks: parseChecks(value.scientific_checks ?? []), parent_identity: text(value.parent_identity, "parent_identity", 400), budget, worker: parseWorker(value.worker), specification };
}

function identity(hashes: Record<string, string>): string { return createHash("sha256").update(Object.keys(hashes).sort().map(path => path + "\0" + hashes[path]).join("\n")).digest("hex"); }
function requestedModel(order: Phase3WorkOrder): Phase3Model { const defaults = ROLE_DEFAULTS[order.role]; const prefix = "CSE_PI_" + order.role.toUpperCase(); return { provider: order.worker?.provider ?? process.env[prefix + "_PROVIDER"] ?? process.env.CSE_PI_PROVIDER ?? defaults.provider, model: order.worker?.model ?? process.env[prefix + "_MODEL"] ?? process.env.CSE_PI_MODEL ?? defaults.model, effort: order.worker?.effort ?? process.env[prefix + "_EFFORT"] ?? process.env.CSE_PI_EFFORT ?? defaults.effort }; }
function resolveModel(order: Phase3WorkOrder): Phase3Model { const requested = requestedModel(order); if (requested.provider !== "openai-codex" || !MODEL_EFFORTS[requested.model]?.includes(requested.effort)) throw new Error("unsupported " + order.role + " provider/model/effort: " + requested.provider + "/" + requested.model + "/" + requested.effort); return requested; }
function throwIfAborted(signal?: AbortSignal): void { if (signal?.aborted) throw new Error("CSE-PI operation cancelled"); }
function within(root: string, candidate: string): boolean { return candidate === root || candidate.startsWith(root + sep); }

async function copyFiles(sourceRoot: string, destinationRoot: string, files: readonly string[], signal?: AbortSignal): Promise<void> {
  for (const path of files) { throwIfAborted(signal); const source = await safeRegularFile(sourceRoot, path); const destination = join(destinationRoot, path); await mkdir(dirname(destination), { recursive: true, mode: 0o700 }); await copyFile(source, destination, constants.COPYFILE_EXCL); }
}
async function cloneCandidate(inputRoot: string, resultDir: string, files: readonly string[], scopes: readonly Phase3WriteScope[], signal?: AbortSignal): Promise<{ root: string; placeholders: Placeholder[] }> {
  const root = join(resultDir, "candidate"); await mkdir(root, { recursive: true, mode: 0o700 }); await copyFiles(inputRoot, root, files, signal);
  const placeholders: Placeholder[] = [];
  for (const scope of scopes) { const target = join(root, scope.path); try { const info = await lstat(target); if (info.isSymbolicLink() || (scope.kind === "file" ? !info.isFile() || info.nlink !== 1 : !info.isDirectory())) throw new Error("candidate write scope changed type: " + scope.path); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; if (scope.kind === "directory") await mkdir(target, { recursive: true, mode: 0o700 }); else { await mkdir(dirname(target), { recursive: true, mode: 0o700 }); await writeFile(target, "", { flag: "wx", mode: 0o600 }); } placeholders.push(scope); } }
  return { root, placeholders };
}
async function scanTree(root: string, maxBytes: number, signal?: AbortSignal): Promise<Tree> {
  const hashes: Record<string, string> = {}; let bytes = 0; let files = 0; let directories = 0;
  const walk = async (directory: string, prefix: string, depth: number): Promise<void> => {
    throwIfAborted(signal); if (depth > MAX_DEPTH) throw new Error("retained tree depth exceeds CSE-Pi cap"); directories += 1; if (directories > MAX_DIRECTORIES) throw new Error("retained tree exceeds directory cap");
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      if (entry.name === ".git" || entry.name.startsWith(".cse-pi-")) throw new Error("retained tree contains administrative or temporary content");
      const path = join(directory, entry.name); const relativePath = prefix ? prefix + "/" + entry.name : entry.name;
      if (entry.isSymbolicLink() || (!entry.isFile() && !entry.isDirectory())) throw new Error("retained tree contains unsafe path: " + relativePath);
      if (entry.isDirectory()) await walk(path, relativePath, depth + 1);
      else { const info = await lstat(path); if (info.nlink !== 1) throw new Error("retained tree contains hardlink: " + relativePath); files += 1; bytes += info.size; if (files > MAX_FILES || bytes > maxBytes) throw new Error("retained tree exceeds byte/file cap"); hashes[relativePath] = await sha256File(path, signal, maxBytes); }
    }
  };
  const info = await lstat(root); if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("retained tree root is unsafe"); await walk(root, "", 0); return { hashes, bytes, files, directories };
}
async function removeEmptyPlaceholders(root: string, paths: readonly (string | Placeholder)[], touched: ReadonlySet<string>, prefix = ""): Promise<void> { for (const item of paths) { const path = typeof item === "string" ? item : item.path; const kind = typeof item === "string" ? "file" : item.kind; const key = prefix + path; if (touched.has(key)) continue; const target = join(root, path); try { const info = await lstat(target); if (kind === "file" && info.isFile() && info.size === 0) await rm(target, { force: true }); else if (kind === "directory" && info.isDirectory() && (await readdir(target)).length === 0) await rm(target, { recursive: true, force: true }); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; } } }

function permitted(path: string, paths: readonly string[]): boolean { return paths.some(allowed => path === allowed || path.startsWith(allowed + "/")); }
async function safeTarget(root: string, path: string, allowMissing: boolean): Promise<string> {
  const target = resolve(root, path); if (!within(resolve(root), target)) throw new Error("scoped path escapes isolated workspace");
  const parts = relative(resolve(root), target).split(sep).filter(Boolean); let current = resolve(root);
  for (const part of parts.slice(0, -1)) { current = join(current, part); try { const info = await lstat(current); if (info.isSymbolicLink() || !info.isDirectory()) throw new Error("scoped path has unsafe ancestor"); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT" || !allowMissing) throw error; } }
  try { const info = await lstat(target); if (info.isSymbolicLink() || (!info.isFile() && !info.isDirectory()) || (info.isFile() && info.nlink !== 1)) throw new Error("scoped target is unsafe"); } catch (error) { if (!allowMissing || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
  return target;
}
async function retainCommandEvidence(result: SandboxResult, evidence: unknown[], root: string): Promise<void> { const name = "command-" + evidence.length + ".out"; await mkdir(root, { recursive: true, mode: 0o700 }); await writeFile(join(root, name), result.raw_output, { flag: "wx", mode: 0o600 }); evidence.push({ ...result.evidence, output_path: "command-evidence/" + name }); }
async function writableMount(root: string, path: string, allowed: readonly string[]): Promise<string> { const candidates = allowed.filter(item => path.startsWith(item + "/")).sort((a, b) => b.length - a.length); for (const item of candidates) { try { const info = await lstat(join(root, item)); if (info.isDirectory()) return item; } catch {} } return path; }
async function runScopedWrite(root: string, path: string, content: string | null, allowedPaths: readonly string[], maxBytes: number, scratch: string, timeoutMs: number, signal: AbortSignal, evidence: unknown[], evidenceRoot: string): Promise<void> {
  if (!permitted(path, allowedPaths)) throw new Error("scoped write is outside frozen scope: " + path);
  const target = await safeTarget(root, path, content !== null); const dataBytes = content === null ? 0 : Buffer.byteLength(content); if (dataBytes > maxBytes) throw new Error("scoped write exceeds output budget");
  try { const info = await lstat(target); if (content !== null && !info.isFile()) throw new Error("scoped write target must be a regular file"); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
  await mkdir(scratch, { recursive: true, mode: 0o700 }); const payload = join(scratch, ".phase3-write-payload"); if (content !== null) await writeFile(payload, content, { flag: "w", mode: 0o600 });
  try { const mount = await writableMount(root, path, allowedPaths); const command = content === null ? "rm -- " + shellQuote("/workspace/" + path) : "cat -- /scratch/.phase3-write-payload > " + shellQuote("/workspace/" + path); const result = await runSandbox(command, root, scratch, timeoutMs, maxBytes, signal, { writablePaths: [mount], workspaceBytes: maxBytes, ...(content === null ? { deletePath: path } : {}) }); await retainCommandEvidence(result, evidence, evidenceRoot); if (result.evidence.exit_code !== 0 || result.evidence.output_limited || result.evidence.scratch_limited || result.evidence.workspace_limited === true) throw new Error("Bubblewrap denied scoped " + (content === null ? "delete" : "write")); } finally { await rm(payload, { force: true }); }
  try { const info = await lstat(target); if (content === null) throw new Error("scoped delete did not remove target"); if (!info.isFile() || info.nlink !== 1) throw new Error("scoped write did not retain a regular file"); } catch (error) { if (content !== null || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
}

function outcomeFor(status: Phase3Status, submission: Record<string, unknown> | null): string | null { if (typeof submission?.outcome === "string") return submission.outcome; if (status === "blocked") return "blocked"; if (status === "needs_parent_input") return "needs_parent_input"; return null; }
function boundedEvents(events: readonly string[], maxBytes: number): string { const full = events.join("\n") + "\n"; if (Buffer.byteLength(full) <= maxBytes) return full; const short = (events.slice(0, 3).concat([JSON.stringify({ type: "events_truncated" }), events.at(-1) ?? ""])).join("\n") + "\n"; return Buffer.byteLength(short) <= maxBytes ? short : (events[0] ?? "") + "\n"; }

async function renderDiff(inputRoot: string, candidateRoot: string, entries: readonly Change[], maxBytes: number, signal?: AbortSignal): Promise<string> {
  const pieces: Buffer[] = []; let total = 0;
  for (const entry of entries) {
    throwIfAborted(signal); const before = entry.action === "created" ? "/dev/null" : join(inputRoot, entry.path); const after = entry.action === "deleted" ? "/dev/null" : join(candidateRoot, entry.path);
    let output: Buffer;
    try { const result = await execFileAsync("/usr/bin/diff", ["--label", "a/" + entry.path, "--label", "b/" + entry.path, "-u", before, after], { encoding: "buffer", maxBuffer: Math.max(1024, maxBytes - total) }); output = Buffer.from(result.stdout as Buffer); }
     catch (error) { const failure = error as { code?: number; stdout?: Buffer | string; stderr?: Buffer | string }; if (failure.code !== 1) throw new Error("diff failed for " + entry.path); output = Buffer.isBuffer(failure.stdout) ? failure.stdout : Buffer.from(failure.stdout ?? ""); }
    const binary = output.toString("utf8").includes("Binary files"); const rendered = binary ? Buffer.from("Binary change: " + entry.action + " " + entry.path + " before=" + (entry.before_sha256 ?? "none") + " after=" + (entry.after_sha256 ?? "none") + "\n") : output.length ? output : Buffer.from("--- a/" + entry.path + "\n+++ b/" + entry.path + "\n@@ -0,0 +0,0 @@\n"); total += rendered.length; if (total > maxBytes) throw new Error("candidate diff exceeds output budget"); pieces.push(rendered);
  }
  return Buffer.concat(pieces).toString("utf8");
}

function rolePrompt(order: Phase3WorkOrder): string {
  return ["You are the bounded CSE-Pi build worker.", "Use cse_write_candidate and cse_delete_candidate for source changes; the source checkout is never writable. The parent must inspect the candidate.", "The frozen work order is authoritative; do not expand scope.", "Use /workspace for the assigned isolated candidate and /scratch for bounded scratch; host paths are not a worker interface.", JSON.stringify({ task_id: order.task_id, role: order.role, objective: order.objective, scientific_question: order.scientific_question, specification: order.specification, constraints: order.constraints, non_goals: order.non_goals, context_files: order.context_files, access: order.access, expected_artifacts: order.expected_artifacts, acceptance_criteria: order.acceptance_criteria, validation: order.validation, scientific_checks: order.scientific_checks, known_context: order.known_context, parent_identity: order.parent_identity }), "Submit exactly one terminating cse_submit_result call after the build work is complete."].join("\n");
}

function submissionTool(lifecycle: ResultLifecycle, submitted: (value: Record<string, unknown>) => void) {
  return defineTool({ name: "cse_submit_result", label: "Submit CSE result", description: "Terminate with a structured CSE result.", parameters: Type.Object({ outcome: Type.Union([Type.Literal("accepted"), Type.Literal("inconclusive"), Type.Literal("blocked"), Type.Literal("needs_parent_input")]), facts: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), assumptions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 32 }), findings: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), evidence: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), limitations: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), deviations: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), questions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), recommended_parent_action: Type.String({ minLength: 1, maxLength: 2000 }) }), executionMode: "sequential", async execute(_id, params) { submitted(params as Record<string, unknown>); lifecycle.submit(params.outcome); return { content: [{ type: "text", text: JSON.stringify(params) }], details: params, terminate: true }; } });
}
async function existingParent(path: string): Promise<string> { let current = resolve(path); while (true) { try { return await realpath(current); } catch { const parent = resolve(current, ".."); if (parent === current) throw new Error("result directory has no existing parent"); current = parent; } } }

export async function runPhase3(raw: unknown, resultDir: string, noInference = false, signal?: AbortSignal, hooks: Phase3Hooks = {}): Promise<Phase3RunResult> {
  const order = parsePhase3WorkOrder(raw); const runId = randomUUID(); const started = performance.now(); const timeoutController = new AbortController(); let timedOut = false; const timeout = setTimeout(() => { timedOut = true; timeoutController.abort(); }, order.budget.wall_timeout_ms); const relay = () => timeoutController.abort(); signal?.addEventListener("abort", relay, { once: true }); if (signal?.aborted) timeoutController.abort(); const activeSignal = timeoutController.signal;
  let status: Phase3Status = "failed"; let resultReady = false; let checkingFinalIntegrity = false; let selectedModel = requestedModel(order); let phase1: typeof import("./worker.js") | undefined; let snapshotData: Snapshot | undefined; const touched = new Set<string>(); const events: string[] = []; const commandEvidence: unknown[] = []; const runtimeEvents: Record<string, unknown>[] = []; const submitted: { value: Record<string, unknown> | null } = { value: null };
  const body: Record<string, unknown> = { schema_version: 3, run_id: runId, task_id: order.task_id, role: order.role, parent_identity: order.parent_identity, status, requested_model: { ...selectedModel, source: order.worker ? "work_order" : "environment_or_role_default" }, resolved_model: selectedModel, role_profile: { role: order.role, default_model: ROLE_DEFAULTS[order.role], requested_source: order.worker ? "work_order" : "environment_or_role_default" }, observed_model: null, runtime: { node: process.version, role_defaults: ROLE_DEFAULTS[order.role] }, termination: null, model_authored: null, role_result: null, snapshot_identity: null, snapshot_files: [], supervisor: { commands: [], checks: [], runtime_events: [], retained_evidence: ["input/", "events.jsonl", "scratch/", "command-evidence/"], source_before_after_equal: null, actual_changes: [] } };
  const maxOutput = order.budget.output_bytes; const remaining = () => Math.max(1, Math.floor(order.budget.wall_timeout_ms - (performance.now() - started)));
  try {
    const workspace = await realpath(order.workspace.root); const output = resolve(resultDir); const parent = await existingParent(dirname(output)); if (within(workspace, output) || within(workspace, parent)) throw new Error("result directory must be outside source workspace"); await mkdir(output, { recursive: false, mode: 0o700 }); resultReady = true;
    selectedModel = resolveModel(order); body.requested_model = { ...selectedModel, source: order.worker ? "work_order" : "environment_or_role_default" }; body.resolved_model = selectedModel;
    phase1 = await import("./worker.js"); const retained = await phase1.snapshot(order, output, activeSignal); const inputTree = await scanTree(retained.root, Math.min(MAX_BYTES, order.budget.output_bytes * 16), activeSignal); if (identity(inputTree.hashes) !== retained.identity) throw new Error("retained snapshot identity is stale"); snapshotData = { sourceRoot: workspace, inputRoot: retained.root, files: retained.files, hashes: inputTree.hashes, identity: retained.identity }; body.snapshot_identity = snapshotData.identity; body.snapshot_files = snapshotData.files;
    const sourceBefore = snapshotData.identity; const candidateData = await cloneCandidate(snapshotData.inputRoot, output, snapshotData.files, order.access.write_scopes, activeSignal);
    body.supervisor = { ...(body.supervisor as Record<string, unknown>), retained_evidence: ["input/", "candidate/", "candidate.diff", "events.jsonl", "scratch/", "command-evidence/"] };
    await requireSandbox(activeSignal, Math.min(remaining(), 2000)); events.push(JSON.stringify({ type: "validated", role: order.role, task_id: order.task_id, requested_model: selectedModel }));
    const checks = await Promise.all(order.scientific_checks.map(async check => { const hostPath = await safeRegularFile(workspace, check.path); return runCheck({ ...check, path: join(snapshotData!.inputRoot, relative(workspace, hostPath)) }, snapshotData!.inputRoot, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), maxOutput, activeSignal); })); (body.supervisor as Record<string, unknown>).checks = checks; if (checks.some(check => !check.ok)) throw new Error("scientific check failed");
    if (noInference) { status = "preflight"; body.termination = "no_inference_preflight"; } else {
      const lifecycle = new ResultLifecycle(); const modelRoot = candidateData.root; const writeTools: unknown[] = [];
      writeTools.push(defineTool({ name: "cse_write_candidate", label: "Write candidate file", description: "Write one explicitly permitted candidate file through Bubblewrap.", parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 4000 }), content: Type.String({ maxLength: maxOutput }) }), executionMode: "sequential", async execute(_id, params) { const path = normalizedPath(params.path, "candidate path"); await runScopedWrite(candidateData.root, path, params.content, order.access.write_paths, maxOutput, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), activeSignal, commandEvidence, join(output, "command-evidence")); touched.add(path); return { content: [{ type: "text", text: "wrote " + path }], details: { path } }; } }));
      writeTools.push(defineTool({ name: "cse_delete_candidate", label: "Delete candidate file", description: "Delete one explicitly permitted candidate file through Bubblewrap.", parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 4000 }) }), executionMode: "sequential", async execute(_id, params) { const path = normalizedPath(params.path, "candidate path"); await runScopedWrite(candidateData.root, path, null, order.access.write_paths, maxOutput, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), activeSignal, commandEvidence, join(output, "command-evidence")); touched.add(path); return { content: [{ type: "text", text: "deleted " + path }], details: { path } }; } }));
      const genericSubmit = submissionTool(lifecycle, value => { submitted.value = value; }); const commandTool = safeCommandTool(modelRoot, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), maxOutput, commandEvidence, join(output, "command-evidence")); const tools = [commandTool, ...writeTools, genericSubmit]; const prompt = rolePrompt(order);
      let session: Phase3Session; if (hooks.createSession) session = await hooks.createSession({ role: order.role, model: selectedModel, prompt, tools }); else { const agentDir = process.env.CSE_PI_AGENT_DIR || join(process.env.HOME || "/nonexistent", ".pi", "agent"); const authPath = join(agentDir, "auth.json"); await access(authPath, constants.R_OK).catch(() => { throw new Error("CSE-PI capability error: supported Pi auth is unavailable"); }); if (!readStoredCredential(selectedModel.provider, authPath)) throw new Error("CSE-PI capability error: supported subscription auth is unavailable"); const runtime = await ModelRuntime.create({ authPath, modelsPath: join(agentDir, "models.json"), allowModelNetwork: false }); const model = runtime.getModel(selectedModel.provider, selectedModel.model); if (!model || !runtime.hasConfiguredAuth(selectedModel.provider)) throw new Error("CSE-PI capability error: supported model is unavailable"); const loader = new DefaultResourceLoader({ cwd: modelRoot, agentDir: output, noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true, systemPrompt: "CSE-Pi bounded worker." }); await loader.reload(); const result = await createAgentSession({ cwd: modelRoot, agentDir: output, modelRuntime: runtime, model, thinkingLevel: selectedModel.effort as never, noTools: "builtin", excludeTools: ["read", "bash", "edit", "write", "grep", "find", "ls"], customTools: tools as never, resourceLoader: loader, sessionManager: SessionManager.inMemory(), settingsManager: SettingsManager.inMemory() }); session = result.session as unknown as Phase3Session; }
      let terminal: Awaited<ReturnType<typeof runOneTurn>> = "failed"; let disposeError: string | null = null; try { const names = tools.map(tool => (tool as { name: string }).name); session.setActiveToolsByName(names); if (!names.every(name => session.getActiveToolNames().includes(name))) throw new Error("CSE-Pi tool registration failed"); body.observed_model = { provider: selectedModel.provider, model: selectedModel.model, effort: session.thinkingLevel ?? null }; if (session.thinkingLevel !== selectedModel.effort) throw new Error("observed effort mismatch: requested " + selectedModel.effort + ", observed " + (session.thinkingLevel ?? "missing")); terminal = await runOneTurn(session, prompt, lifecycle, order.budget, activeSignal, event => { if (runtimeEvents.length < 256) runtimeEvents.push(event); }); body.termination = terminal; } finally { (body.supervisor as Record<string, unknown>).commands = commandEvidence; (body.supervisor as Record<string, unknown>).runtime_events = runtimeEvents; body.model_authored = submitted.value; if (session.getSessionStats) body.usage = tokenUsage(session.getSessionStats()); body.retries = session.retryAttempt ?? null; try { await session.dispose(); } catch (error) { disposeError = error instanceof Error ? error.message : String(error); body.dispose_error = disposeError; } }
      if (disposeError) throw new Error("CSE-PI session disposal failed: " + disposeError); if (terminal === "completed") status = "completed"; else if (terminal === "blocked") status = "blocked"; else if (terminal === "needs_parent_input") status = "needs_parent_input"; else if (terminal === "timed_out") status = "timed_out"; else if (terminal === "cancelled") status = "cancelled"; else status = "failed";
      if (status === "completed" && !submitted.value) throw new Error("CSE-Pi worker did not submit a structured result");
    }
    await removeEmptyPlaceholders(candidateData.root, candidateData.placeholders, touched); const afterTree = await scanTree(candidateData.root, Math.min(MAX_BYTES, order.budget.output_bytes * 16), activeSignal); const actualChanges: Change[] = []; for (const path of [...new Set([...Object.keys(snapshotData.hashes), ...Object.keys(afterTree.hashes)])].sort()) if (snapshotData.hashes[path] !== afterTree.hashes[path]) { if (!permitted(path, order.access.write_paths)) throw new Error("candidate changed outside frozen scope: " + path); actualChanges.push({ path, action: snapshotData.hashes[path] === undefined ? "created" : afterTree.hashes[path] === undefined ? "deleted" : "modified", before_sha256: snapshotData.hashes[path] ?? null, after_sha256: afterTree.hashes[path] ?? null }); } const diff = await renderDiff(snapshotData.inputRoot, candidateData.root, actualChanges, maxOutput, activeSignal); await writeFile(join(output, "candidate.diff"), diff, { mode: 0o600 }); body.candidate_identity = identity(afterTree.hashes); body.candidate_files = Object.keys(afterTree.hashes).sort(); body.candidate_changes = actualChanges; body.diff_sha256 = createHash("sha256").update(diff).digest("hex"); body.role_result = { outcome: outcomeFor(status, submitted.value), files_changed: actualChanges, validation_results: commandEvidence, candidate_identity: identity(afterTree.hashes) };
    checkingFinalIntegrity = true; await hooks.beforeFinalIntegrity?.(); const sourceAfter = await phase1!.contentIdentity(snapshotData.sourceRoot, snapshotData.files, activeSignal, Math.min(MAX_BYTES, order.budget.output_bytes * 16)); const supervisor = body.supervisor as Record<string, unknown>; supervisor.source_before_after_equal = sourceBefore === sourceAfter; supervisor.actual_changes = sourceBefore === sourceAfter ? [] : ["assigned source content changed during CSE-Pi run"]; if (sourceBefore !== sourceAfter) { status = "failed"; body.termination = "integrity_check_failed"; body.error = "source workspace content changed during CSE-Pi run"; } if (!body.termination) body.termination = status === "completed" ? "structured_submission" : status; checkingFinalIntegrity = false;
  } catch (error) { body.error = error instanceof Error ? error.message : String(error); (body.supervisor as Record<string, unknown>).commands = commandEvidence; (body.supervisor as Record<string, unknown>).runtime_events = runtimeEvents; if (checkingFinalIntegrity) { status = "failed"; body.termination = "integrity_check_failed"; } else if (timedOut) { status = "timed_out"; body.termination = "wall_timeout"; } else if (activeSignal.aborted || signal?.aborted) { status = "cancelled"; body.termination = "cancelled"; } else { status = "failed"; body.termination = body.termination ?? "failed"; } } finally { clearTimeout(timeout); signal?.removeEventListener("abort", relay); }
  if (!resultReady) throw new Error(String(body.error ?? "CSE-Pi run could not create result directory")); body.status = status; events.push(JSON.stringify({ type: "terminal", status })); await writeFile(join(resolve(resultDir), "events.jsonl"), boundedEvents(events, maxOutput), { mode: 0o600 });
  let rendered = JSON.stringify(body, null, 2);
  if (Buffer.byteLength(rendered) > maxOutput) {
    status = "failed"; body.status = status; body.error = "result exceeded output byte budget";
    rendered = JSON.stringify({ schema_version: 3, run_id: runId, task_id: order.task_id, role: order.role, parent_identity: order.parent_identity, status, termination: body.termination, supervisor: { retained_evidence: ["events.jsonl"] }, error: body.error });
    if (Buffer.byteLength(rendered) > maxOutput) throw new Error("minimum result exceeds output byte budget");
  }
  const resultPath = join(resolve(resultDir), "result.json"); await writeFile(resultPath, rendered, { mode: 0o600 }); return { schema_version: 3, run_id: runId, status, result_path: resultPath, result_sha256: await sha256File(resultPath) };
}
