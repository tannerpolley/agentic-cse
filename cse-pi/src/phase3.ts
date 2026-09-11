import { constants } from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash, randomUUID } from "node:crypto";
import { access, copyFile, mkdir, readdir, lstat, realpath, rm, writeFile, readFile } from "node:fs/promises";
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

export const PHASE3_SCHEMA_VERSION = 2;
export const PHASE3_ROLES = ["implement", "analyze", "review"] as const;
export type Phase3Role = (typeof PHASE3_ROLES)[number];
export type Phase3Status = "completed" | "preflight" | "blocked" | "failed" | "timed_out" | "cancelled" | "needs_parent_input";
export type Phase3RunResult = { schema_version: 2; run_id: string; status: Phase3Status; result_path: string; result_sha256?: string };

type Phase3Model = { provider: string; model: string; effort: string };
type Phase3Path = { path: string; sha256: string; purpose: string };
export type Phase3OutputCheck = { id: string; kind: Check["kind"]; path: string; checker_identity: string };
export type Phase3WriteScope = { path: string; kind: "file" | "directory" };
type Phase3Check = Check & { checker_identity: string };
export type Phase3WorkOrder = {
  schema_version: 2;
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
  write_policy: "candidate" | "analysis" | "none";
  network_policy: "none";
  expected_artifacts: string[];
  acceptance_criteria: string[];
  validation: string[];
  scientific_checks: Phase3Check[];
  analysis_checks: Phase3OutputCheck[];
  parent_identity: string;
  budget: { wall_timeout_ms: number; model_turn_limit: number; command_timeout_ms: number; output_bytes: number };
  worker?: { provider?: string; model?: string; effort?: string };
  specification: { text: string; required_changes: string[]; forbidden_changes: string[]; permitted_paths: string[] };
  output_paths: string[];
  review_inputs: string[];
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
const MODEL_EFFORTS: Record<string, string[]> = { "gpt-6-astra": EFFORTS, "gpt-5.6-sol": EFFORTS, "gpt-5.6-terra": EFFORTS, "gpt-5.6-luna": EFFORTS };
const ROLE_DEFAULTS: Record<Phase3Role, Phase3Model> = {
  implement: { provider: "openai-codex", model: "gpt-5.6-luna", effort: "high" },
  analyze: { provider: "openai-codex", model: "gpt-5.6-terra", effort: "high" },
  review: { provider: "openai-codex", model: "gpt-5.6-sol", effort: "high" },
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
  if (!writePaths.length) {
    if (value !== undefined && (!Array.isArray(value) || value.length)) throw new Error("write_scopes must be empty outside implement");
    return [];
  }
  if (!Array.isArray(value)) throw new Error("implement requires explicit write_scopes");
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
function parseOutputChecks(value: unknown): Phase3OutputCheck[] {
  if (!Array.isArray(value) || value.length > 128) throw new Error("analysis_checks must be an array");
  return value.map((raw, index) => {
    const check = object(raw, "analysis_checks[" + index + "]");
    if (Object.keys(check).some(key => !["id", "kind", "path", "checker_identity"].includes(key))) throw new Error("analysis check has an unknown field");
    const kind = text(check.kind, "analysis_checks[" + index + "].kind", 40);
    if (!["json", "convergence", "plot_metadata"].includes(kind)) throw new Error("analysis check kind is unsupported");
    return { id: text(check.id, "analysis_checks[" + index + "].id", 120), kind: kind as Check["kind"], path: normalizedPath(check.path, "analysis_checks[" + index + "].path"), checker_identity: text(check.checker_identity ?? "cse-pi-phase3", "analysis_checks[" + index + "].checker_identity", 200) };
  });
}

export function parsePhase3WorkOrder(raw: unknown): Phase3WorkOrder {
  const value = object(raw, "Phase-3 work order");
  const fields = ["schema_version", "task_id", "role", "objective", "scientific_question", "workspace", "context_files", "known_context", "constraints", "non_goals", "access", "write_policy", "network_policy", "expected_artifacts", "acceptance_criteria", "validation", "scientific_checks", "analysis_checks", "parent_identity", "budget", "worker", "specification", "output_paths", "review_inputs"];
  if (Object.keys(value).some(key => !fields.includes(key))) throw new Error("Phase-3 work order has an unknown field");
  if (value.schema_version !== PHASE3_SCHEMA_VERSION) throw new Error("Phase-3 schema_version must be 2");
  if (!PHASE3_ROLES.includes(value.role as Phase3Role)) throw new Error("Phase-3 role is unsupported");
  const role = value.role as Phase3Role;
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
  if (!(["candidate", "analysis", "none"] as unknown[]).includes(writePolicy)) throw new Error("write_policy is unsupported");
  if (value.network_policy !== "none") throw new Error("only network_policy=none is supported");
  if (role === "implement" && (writePolicy !== "candidate" || !access.write_paths.length)) throw new Error("implement requires candidate write_paths");
  if (role === "analyze" && (writePolicy !== "analysis" || access.write_paths.length)) throw new Error("analyze may write only analysis outputs");
  if (role === "review" && (writePolicy !== "none" || access.write_paths.length)) throw new Error("review is read-only");
  const budgetValue = object(value.budget, "budget");
  if (Object.keys(budgetValue).some(key => !["wall_timeout_ms", "model_turn_limit", "command_timeout_ms", "output_bytes"].includes(key))) throw new Error("budget has an unknown field");
  const budget = { wall_timeout_ms: integer(budgetValue.wall_timeout_ms, "budget.wall_timeout_ms", 1000, 86_400_000), model_turn_limit: integer(budgetValue.model_turn_limit, "budget.model_turn_limit", 1, 100), command_timeout_ms: integer(budgetValue.command_timeout_ms, "budget.command_timeout_ms", 100, 3_600_000), output_bytes: integer(budgetValue.output_bytes, "budget.output_bytes", 1024, 100_000_000) };
  const rawSpec = value.specification === undefined ? {} : object(value.specification, "specification");
  if (Object.keys(rawSpec).some(key => !["text", "required_changes", "forbidden_changes", "permitted_paths"].includes(key))) throw new Error("specification has an unknown field");
  const specification = { text: text(rawSpec.text ?? value.objective, "specification.text"), required_changes: strings(rawSpec.required_changes ?? [], "specification.required_changes"), forbidden_changes: strings(rawSpec.forbidden_changes ?? [], "specification.forbidden_changes"), permitted_paths: pathList(rawSpec.permitted_paths ?? access.write_paths, "specification.permitted_paths") };
  if (role === "implement" && specification.permitted_paths.some(path => !access.write_paths.some(allowed => path === allowed || path.startsWith(allowed + "/")))) throw new Error("specification.permitted_paths exceeds write scope");
  const outputPaths = pathList(value.output_paths ?? [], "output_paths");
  if (role === "analyze" && !outputPaths.length) throw new Error("analyze requires output_paths");
  if (role !== "analyze" && outputPaths.length) throw new Error(role + " cannot declare output_paths");
  const analysisChecks = parseOutputChecks(value.analysis_checks ?? []);
  if (role !== "analyze" && analysisChecks.length) throw new Error("only analyze may declare analysis_checks");
  if (analysisChecks.some(check => !outputPaths.includes(check.path))) throw new Error("analysis_checks must target exact output_paths");
  const reviewInputs = pathList(value.review_inputs ?? [], "review_inputs");
  if (reviewInputs.some(path => !access.read_paths.some(allowed => path === allowed || path.startsWith(allowed + "/")))) throw new Error("review_inputs must be within access.read_paths");
  return { schema_version: 2, task_id: text(value.task_id, "task_id", 120), role, objective: text(value.objective, "objective"), scientific_question: text(value.scientific_question, "scientific_question"), workspace: { root, expected_identity: expectedIdentity }, context_files: contextFiles, known_context: strings(value.known_context ?? [], "known_context"), constraints: strings(value.constraints ?? [], "constraints"), non_goals: strings(value.non_goals ?? [], "non_goals"), access, write_policy: writePolicy as Phase3WorkOrder["write_policy"], network_policy: "none", expected_artifacts: strings(value.expected_artifacts ?? [], "expected_artifacts"), acceptance_criteria: strings(value.acceptance_criteria ?? [], "acceptance_criteria"), validation: strings(value.validation ?? [], "validation"), scientific_checks: parseChecks(value.scientific_checks ?? []), analysis_checks: analysisChecks, parent_identity: text(value.parent_identity, "parent_identity", 400), budget, worker: parseWorker(value.worker), specification, output_paths: outputPaths, review_inputs: reviewInputs };
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
async function prepareAnalysisWorkspace(inputRoot: string, resultDir: string, files: readonly string[], outputPaths: readonly string[], signal?: AbortSignal): Promise<{ root: string; placeholders: string[] }> {
  const root = join(resultDir, "analysis-workspace"); await mkdir(root, { recursive: true, mode: 0o700 }); await copyFiles(inputRoot, root, files, signal); const analysis = join(root, "analysis"); await mkdir(analysis, { recursive: true, mode: 0o700 });
  const placeholders: string[] = [];
  for (const path of outputPaths) { const target = join(analysis, path); try { const info = await lstat(target); if (info.isSymbolicLink() || !info.isFile() || info.nlink !== 1) throw new Error("analysis output path must be an exact regular file: " + path); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; await mkdir(dirname(target), { recursive: true, mode: 0o700 }); await writeFile(target, "", { flag: "wx", mode: 0o600 }); placeholders.push(path); } }
  return { root, placeholders };
}

async function scanTree(root: string, maxBytes: number, signal?: AbortSignal): Promise<Tree> {
  const hashes: Record<string, string> = {}; let bytes = 0; let files = 0; let directories = 0;
  const walk = async (directory: string, prefix: string, depth: number): Promise<void> => {
    throwIfAborted(signal); if (depth > MAX_DEPTH) throw new Error("retained tree depth exceeds Phase 3 cap"); directories += 1; if (directories > MAX_DIRECTORIES) throw new Error("retained tree exceeds directory cap");
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

function finite(value: unknown): boolean { if (typeof value === "number") return Number.isFinite(value); if (Array.isArray(value)) return value.every(finite); if (isObject(value)) return Object.values(value).every(finite); return true; }
async function validateJsonOutput(path: string, maxBytes: number): Promise<void> { const info = await lstat(path); if (!info.isFile() || info.size > maxBytes) throw new Error("analysis JSON output is not a bounded regular file"); let value: unknown; try { value = JSON.parse(await readFile(path, "utf8")); } catch { throw new Error("analysis JSON output is malformed"); } if (!finite(value)) throw new Error("analysis JSON output contains non-finite values"); }

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
  const rule = order.role === "implement" ? "Use cse_write_candidate and cse_delete_candidate for source changes; the source checkout is never writable. The parent must inspect the candidate." : order.role === "analyze" ? "Use cse_write_analysis or bounded commands for declared analysis outputs only; source edits are prohibited. Do not treat convergence or a JSON shape as physical validation." : "Perform a fresh read-only review and return prioritized findings with evidence, impact, confidence, and blocking status.";
  return ["You are the bounded CSE-Pi " + order.role + " worker.", rule, "The frozen work order is authoritative; do not expand scope.", "Use /workspace for the assigned snapshot or isolated candidate and /scratch for bounded scratch; host paths are not a worker interface.", JSON.stringify({ task_id: order.task_id, role: order.role, objective: order.objective, scientific_question: order.scientific_question, specification: order.specification, constraints: order.constraints, non_goals: order.non_goals, context_files: order.context_files, access: order.access, expected_artifacts: order.expected_artifacts, acceptance_criteria: order.acceptance_criteria, validation: order.validation, scientific_checks: order.scientific_checks, analysis_checks: order.analysis_checks, output_paths: order.output_paths, review_inputs: order.review_inputs, known_context: order.known_context, parent_identity: order.parent_identity }), order.role === "review" ? "Submit exactly one terminating cse_submit_review call; the parent independently adjudicates it." : "Submit exactly one terminating cse_submit_result call after the role work is complete."].join("\n");
}

function submissionTool(lifecycle: ResultLifecycle, submitted: (value: Record<string, unknown>) => void) {
  return defineTool({ name: "cse_submit_result", label: "Submit CSE result", description: "Terminate with a structured CSE result.", parameters: Type.Object({ outcome: Type.Union([Type.Literal("accepted"), Type.Literal("inconclusive"), Type.Literal("blocked"), Type.Literal("needs_parent_input")]), facts: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), assumptions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 32 }), findings: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), evidence: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), limitations: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), deviations: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), questions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), recommended_parent_action: Type.String({ minLength: 1, maxLength: 2000 }) }), executionMode: "sequential", async execute(_id, params) { submitted(params as Record<string, unknown>); lifecycle.submit(params.outcome); return { content: [{ type: "text", text: JSON.stringify(params) }], details: params, terminate: true }; } });
}
function reviewTool(lifecycle: ResultLifecycle, submitted: (value: Record<string, unknown>) => void) {
  return defineTool({ name: "cse_submit_review", label: "Submit CSE review", description: "Terminate with prioritized independent review findings.", parameters: Type.Object({ outcome: Type.Union([Type.Literal("accepted"), Type.Literal("inconclusive"), Type.Literal("blocked"), Type.Literal("needs_parent_input")]), summary: Type.String({ minLength: 1, maxLength: 4000 }), findings: Type.Array(Type.Object({ id: Type.String({ minLength: 1, maxLength: 120 }), severity: Type.Union([Type.Literal("critical"), Type.Literal("high"), Type.Literal("medium"), Type.Literal("low")]), blocking: Type.Boolean(), category: Type.String({ minLength: 1, maxLength: 120 }), file: Type.String({ minLength: 1, maxLength: 4000 }), line: Type.Optional(Type.Integer({ minimum: 1 })), evidence: Type.String({ minLength: 1, maxLength: 4000 }), impact: Type.String({ minLength: 1, maxLength: 4000 }), confidence: Type.Union([Type.Literal("high"), Type.Literal("medium"), Type.Literal("low")]), recommended_action: Type.String({ minLength: 1, maxLength: 4000 }) }), { maxItems: 64 }), limitations: Type.Array(Type.String({ minLength: 1 }), { maxItems: 32 }), recommended_parent_action: Type.String({ minLength: 1, maxLength: 2000 }) }), executionMode: "sequential", async execute(_id, params) { submitted(params as Record<string, unknown>); lifecycle.submit(params.outcome); return { content: [{ type: "text", text: JSON.stringify(params) }], details: params, terminate: true }; } });
}

async function existingParent(path: string): Promise<string> { let current = resolve(path); while (true) { try { return await realpath(current); } catch { const parent = resolve(current, ".."); if (parent === current) throw new Error("result directory has no existing parent"); current = parent; } } }

export async function runPhase3(raw: unknown, resultDir: string, noInference = false, signal?: AbortSignal, hooks: Phase3Hooks = {}): Promise<Phase3RunResult> {
  const order = parsePhase3WorkOrder(raw); const runId = randomUUID(); const started = performance.now(); const timeoutController = new AbortController(); let timedOut = false; const timeout = setTimeout(() => { timedOut = true; timeoutController.abort(); }, order.budget.wall_timeout_ms); const relay = () => timeoutController.abort(); signal?.addEventListener("abort", relay, { once: true }); if (signal?.aborted) timeoutController.abort(); const activeSignal = timeoutController.signal;
  let status: Phase3Status = "failed"; let resultReady = false; let selectedModel = requestedModel(order); let phase1: typeof import("./worker.js") | undefined; let snapshotData: Snapshot | undefined; let candidateData: { root: string; placeholders: Placeholder[] } | null = null; let analysisData: { root: string; placeholders: string[] } | null = null; const touched = new Set<string>(); const events: string[] = []; const commandEvidence: unknown[] = []; const runtimeEvents: Record<string, unknown>[] = []; const submitted: { value: Record<string, unknown> | null } = { value: null };
  const body: Record<string, unknown> = { schema_version: 2, run_id: runId, task_id: order.task_id, role: order.role, parent_identity: order.parent_identity, status, requested_model: { ...selectedModel, source: order.worker ? "work_order" : "environment_or_role_default" }, resolved_model: selectedModel, role_profile: { role: order.role, default_model: ROLE_DEFAULTS[order.role], requested_source: order.worker ? "work_order" : "environment_or_role_default" }, observed_model: null, runtime: { node: process.version, role_defaults: ROLE_DEFAULTS[order.role] }, termination: null, model_authored: null, role_result: null, snapshot_identity: null, snapshot_files: [], supervisor: { commands: [], checks: [], runtime_events: [], retained_evidence: ["input/", "events.jsonl", "scratch/", "command-evidence/"], source_before_after_equal: null, actual_changes: [] } };
  const maxOutput = order.budget.output_bytes; const remaining = () => Math.max(1, Math.floor(order.budget.wall_timeout_ms - (performance.now() - started)));
  try {
    const workspace = await realpath(order.workspace.root); const output = resolve(resultDir); const parent = await existingParent(dirname(output)); if (within(workspace, output) || within(workspace, parent)) throw new Error("result directory must be outside source workspace"); await mkdir(output, { recursive: false, mode: 0o700 }); resultReady = true;
    selectedModel = resolveModel(order); body.requested_model = { ...selectedModel, source: order.worker ? "work_order" : "environment_or_role_default" }; body.resolved_model = selectedModel;
    phase1 = await import("./worker.js"); const retained = await phase1.snapshot(order, output, activeSignal); const inputTree = await scanTree(retained.root, Math.min(MAX_BYTES, order.budget.output_bytes * 16), activeSignal); if (identity(inputTree.hashes) !== retained.identity) throw new Error("retained snapshot identity is stale"); snapshotData = { sourceRoot: workspace, inputRoot: retained.root, files: retained.files, hashes: inputTree.hashes, identity: retained.identity }; body.snapshot_identity = snapshotData.identity; body.snapshot_files = snapshotData.files;
    const sourceBefore = snapshotData.identity; candidateData = order.role === "implement" ? await cloneCandidate(snapshotData.inputRoot, output, snapshotData.files, order.access.write_scopes, activeSignal) : null; analysisData = order.role === "analyze" ? await prepareAnalysisWorkspace(snapshotData.inputRoot, output, snapshotData.files, order.output_paths, activeSignal) : null;
    if (candidateData) body.supervisor = { ...(body.supervisor as Record<string, unknown>), retained_evidence: ["input/", "candidate/", "candidate.diff", "events.jsonl", "scratch/", "command-evidence/"] }; if (analysisData) body.supervisor = { ...(body.supervisor as Record<string, unknown>), retained_evidence: ["input/", "analysis/", "events.jsonl", "scratch/", "command-evidence/"] };
    await requireSandbox(activeSignal, Math.min(remaining(), 2000)); events.push(JSON.stringify({ type: "validated", role: order.role, task_id: order.task_id, requested_model: selectedModel }));
    const checks = await Promise.all(order.scientific_checks.map(async check => { const hostPath = await safeRegularFile(workspace, check.path); return runCheck({ ...check, path: join(snapshotData!.inputRoot, relative(workspace, hostPath)) }, snapshotData!.inputRoot, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), maxOutput, activeSignal); })); (body.supervisor as Record<string, unknown>).checks = checks; if (checks.some(check => !check.ok)) throw new Error("scientific check failed");
    if (noInference) { status = "preflight"; body.termination = "no_inference_preflight"; } else {
      const lifecycle = new ResultLifecycle(); const modelRoot = candidateData?.root ?? analysisData?.root ?? snapshotData.inputRoot; const writeTools: unknown[] = [];
      if (candidateData) {
        writeTools.push(defineTool({ name: "cse_write_candidate", label: "Write candidate file", description: "Write one explicitly permitted candidate file through Bubblewrap.", parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 4000 }), content: Type.String({ maxLength: maxOutput }) }), executionMode: "sequential", async execute(_id, params) { const path = normalizedPath(params.path, "candidate path"); await runScopedWrite(candidateData!.root, path, params.content, order.access.write_paths, maxOutput, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), activeSignal, commandEvidence, join(output, "command-evidence")); touched.add(path); return { content: [{ type: "text", text: "wrote " + path }], details: { path } }; } }));
        writeTools.push(defineTool({ name: "cse_delete_candidate", label: "Delete candidate file", description: "Delete one explicitly permitted candidate file through Bubblewrap.", parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 4000 }) }), executionMode: "sequential", async execute(_id, params) { const path = normalizedPath(params.path, "candidate path"); await runScopedWrite(candidateData!.root, path, null, order.access.write_paths, maxOutput, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), activeSignal, commandEvidence, join(output, "command-evidence")); touched.add(path); return { content: [{ type: "text", text: "deleted " + path }], details: { path } }; } }));
      }
      if (analysisData) {
        writeTools.push(defineTool({ name: "cse_write_analysis", label: "Write analysis output", description: "Write one assigned analysis output through Bubblewrap.", parameters: Type.Object({ path: Type.String({ minLength: 1, maxLength: 4000 }), content: Type.String({ maxLength: maxOutput }) }), executionMode: "sequential", async execute(_id, params) { const path = normalizedPath(params.path, "analysis output path"); if (!order.output_paths.includes(path)) throw new Error("analysis output is not an exact assigned file: " + path); await runScopedWrite(analysisData!.root, "analysis/" + path, params.content, order.output_paths.map(item => "analysis/" + item), maxOutput, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), activeSignal, commandEvidence, join(output, "command-evidence")); touched.add("analysis/" + path); return { content: [{ type: "text", text: "wrote analysis/" + path }], details: { path: "analysis/" + path } }; } }));
      }
      const genericSubmit = submissionTool(lifecycle, value => { submitted.value = value; }); const reviewSubmit = order.role === "review" ? reviewTool(lifecycle, value => { submitted.value = value; }) : null; const writableCommandPaths = analysisData ? order.output_paths.map(path => "analysis/" + path) : []; const commandTool = safeCommandTool(modelRoot, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), maxOutput, commandEvidence, join(output, "command-evidence"), analysisData ? { writablePaths: writableCommandPaths, workspaceBytes: maxOutput } : {}); const tools = [commandTool, ...writeTools, ...(reviewSubmit ? [reviewSubmit] : [genericSubmit])]; const prompt = rolePrompt(order);
      let session: Phase3Session; if (hooks.createSession) session = await hooks.createSession({ role: order.role, model: selectedModel, prompt, tools }); else { const agentDir = process.env.CSE_PI_AGENT_DIR || join(process.env.HOME || "/nonexistent", ".pi", "agent"); const authPath = join(agentDir, "auth.json"); await access(authPath, constants.R_OK).catch(() => { throw new Error("CSE-PI capability error: supported Pi auth is unavailable"); }); if (!readStoredCredential(selectedModel.provider, authPath)) throw new Error("CSE-PI capability error: supported subscription auth is unavailable"); const runtime = await ModelRuntime.create({ authPath, modelsPath: join(agentDir, "models.json"), refreshOnCreate: false, allowModelNetwork: false }); const model = runtime.getModel(selectedModel.provider, selectedModel.model); if (!model || !runtime.hasConfiguredAuth(selectedModel.provider)) throw new Error("CSE-PI capability error: supported model is unavailable"); const loader = new DefaultResourceLoader({ cwd: modelRoot, agentDir: output, noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true, systemPrompt: "CSE-Pi Phase 3 bounded worker." }); await loader.reload(); const result = await createAgentSession({ cwd: modelRoot, agentDir: output, modelRuntime: runtime, model, thinkingLevel: selectedModel.effort as never, noTools: "builtin", excludeTools: ["read", "bash", "edit", "write", "grep", "find", "ls"], customTools: tools as never, resourceLoader: loader, sessionManager: SessionManager.inMemory(), settingsManager: SettingsManager.inMemory() }); session = result.session as unknown as Phase3Session; }
      let terminal: Awaited<ReturnType<typeof runOneTurn>> = "failed"; let disposeError: string | null = null; try { const names = tools.map(tool => (tool as { name: string }).name); session.setActiveToolsByName(names); if (!names.every(name => session.getActiveToolNames().includes(name))) throw new Error("CSE-PI Phase 3 tool registration failed"); body.observed_model = { provider: selectedModel.provider, model: selectedModel.model, effort: session.thinkingLevel ?? null }; if (session.thinkingLevel !== selectedModel.effort) throw new Error("observed effort mismatch: requested " + selectedModel.effort + ", observed " + (session.thinkingLevel ?? "missing")); terminal = await runOneTurn(session, prompt, lifecycle, order.budget, activeSignal, event => runtimeEvents.push(event)); body.termination = terminal; } finally { (body.supervisor as Record<string, unknown>).commands = commandEvidence; (body.supervisor as Record<string, unknown>).runtime_events = runtimeEvents; body.model_authored = submitted.value; if (session.getSessionStats) body.usage = tokenUsage(session.getSessionStats()); body.retries = session.retryAttempt ?? null; try { await session.dispose(); } catch (error) { disposeError = error instanceof Error ? error.message : String(error); body.dispose_error = disposeError; } }
      if (disposeError) throw new Error("CSE-PI session disposal failed: " + disposeError); if (terminal === "completed") status = "completed"; else if (terminal === "blocked") status = "blocked"; else if (terminal === "needs_parent_input") status = "needs_parent_input"; else if (terminal === "timed_out") status = "timed_out"; else if (terminal === "cancelled") status = "cancelled"; else status = "failed";
      if (status === "completed" && !submitted.value) throw new Error("Phase 3 worker did not submit a structured result");
      if (candidateData) { await removeEmptyPlaceholders(candidateData.root, candidateData.placeholders, touched); const afterTree = await scanTree(candidateData.root, Math.min(MAX_BYTES, order.budget.output_bytes * 16), activeSignal); const actualChanges: Change[] = []; for (const path of [...new Set([...Object.keys(snapshotData.hashes), ...Object.keys(afterTree.hashes)])].sort()) if (snapshotData.hashes[path] !== afterTree.hashes[path]) { if (!permitted(path, order.access.write_paths)) throw new Error("candidate changed outside frozen scope: " + path); actualChanges.push({ path, action: snapshotData.hashes[path] === undefined ? "created" : afterTree.hashes[path] === undefined ? "deleted" : "modified", before_sha256: snapshotData.hashes[path] ?? null, after_sha256: afterTree.hashes[path] ?? null }); } const diff = await renderDiff(snapshotData.inputRoot, candidateData.root, actualChanges, maxOutput, activeSignal); await writeFile(join(output, "candidate.diff"), diff, { mode: 0o600 }); body.candidate_identity = identity(afterTree.hashes); body.candidate_files = Object.keys(afterTree.hashes).sort(); body.candidate_changes = actualChanges; body.diff_sha256 = createHash("sha256").update(diff).digest("hex"); body.role_result = { outcome: outcomeFor(status, submitted.value), files_changed: actualChanges, validation_results: commandEvidence, candidate_identity: identity(afterTree.hashes) }; }
       if (analysisData) { await removeEmptyPlaceholders(join(analysisData.root, "analysis"), analysisData.placeholders, touched, "analysis/"); const analysisTree = await scanTree(join(analysisData.root, "analysis"), Math.min(MAX_BYTES, order.budget.output_bytes * 16), activeSignal); const outputHashes = analysisTree.hashes; for (const path of Object.keys(outputHashes)) if (path.endsWith(".json")) await validateJsonOutput(join(analysisData.root, "analysis", path), maxOutput); const outputChecks = await Promise.all(order.analysis_checks.map(async check => { const fullPath = join(analysisData!.root, "analysis", check.path); const actual = await sha256File(fullPath, activeSignal, maxOutput); return runCheck({ id: check.id, kind: check.kind, path: fullPath, sha256: actual, checker_identity: check.checker_identity }, analysisData!.root, join(output, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), maxOutput, activeSignal); })); body.analysis_checks = outputChecks.map((check, index) => ({ ...check, path: "analysis/" + order.analysis_checks[index].path })); if (outputChecks.some(check => !check.ok)) throw new Error("analysis scientific check failed"); const outputFiles = Object.keys(outputHashes).map(path => "analysis/" + path); await mkdir(join(output, "analysis"), { recursive: true, mode: 0o700 }); await copyFiles(analysisData.root, output, outputFiles, activeSignal); body.analysis_outputs = outputFiles.map(path => ({ path, sha256: outputHashes[path.replace(/^analysis\//, "")] })); if (status === "completed" && !outputFiles.length) throw new Error("completed analyze worker retained no machine-readable output"); body.role_result = { outcome: outcomeFor(status, submitted.value), outputs: body.analysis_outputs, validation_results: commandEvidence, analysis_checks: body.analysis_checks, scientific_boundaries: ["solver convergence is not code verification", "code verification is not physical validation"] }; }
      if (order.role === "review") { const findings = submitted.value?.findings; if (status === "completed" && !Array.isArray(findings)) throw new Error("review submission is missing findings"); body.review_findings = Array.isArray(findings) ? findings : []; body.role_result = { outcome: outcomeFor(status, submitted.value), findings: body.review_findings, blocking: (body.review_findings as Array<Record<string, unknown>>).some(finding => finding.blocking === true) }; }
    }
    await hooks.beforeFinalIntegrity?.(); const sourceAfter = await phase1!.contentIdentity(snapshotData.sourceRoot, snapshotData.files, activeSignal, Math.min(MAX_BYTES, order.budget.output_bytes * 16)); const supervisor = body.supervisor as Record<string, unknown>; supervisor.source_before_after_equal = sourceBefore === sourceAfter; supervisor.actual_changes = sourceBefore === sourceAfter ? [] : ["assigned source content changed during Phase 3 run"]; if (sourceBefore !== sourceAfter) { status = "failed"; body.termination = "integrity_check_failed"; body.error = "source workspace content changed during Phase 3 run"; } if (!body.termination) body.termination = status === "completed" ? "structured_submission" : status;
  } catch (error) { body.error = error instanceof Error ? error.message : String(error); (body.supervisor as Record<string, unknown>).commands = commandEvidence; (body.supervisor as Record<string, unknown>).runtime_events = runtimeEvents; if (timedOut) { status = "timed_out"; body.termination = "wall_timeout"; } else if (activeSignal.aborted || signal?.aborted) { status = "cancelled"; body.termination = "cancelled"; } else { status = "failed"; body.termination = body.termination ?? "failed"; } } finally { clearTimeout(timeout); signal?.removeEventListener("abort", relay); }
  if (!resultReady) throw new Error(String(body.error ?? "Phase 3 run could not create result directory")); body.status = status; events.push(JSON.stringify({ type: "terminal", status })); await writeFile(join(resolve(resultDir), "events.jsonl"), boundedEvents(events, maxOutput), { mode: 0o600 });
  let rendered = JSON.stringify(body, null, 2); if (Buffer.byteLength(rendered) > maxOutput) { status = "failed"; body.status = status; body.error = "result exceeded output byte budget"; rendered = JSON.stringify({ schema_version: 2, run_id: runId, task_id: order.task_id, role: order.role, parent_identity: order.parent_identity, status, requested_model: selectedModel, snapshot_identity: body.snapshot_identity, supervisor: body.supervisor, error: body.error }); } const resultPath = join(resolve(resultDir), "result.json"); await writeFile(resultPath, rendered, { mode: 0o600 }); return { schema_version: 2, run_id: runId, status, result_path: resultPath, result_sha256: await sha256File(resultPath) };
}
