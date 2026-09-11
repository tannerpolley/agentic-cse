import { createReadStream, createWriteStream } from "node:fs";
import { access, lstat, mkdir, readdir, realpath, stat, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { pipeline } from "node:stream/promises";
import { Transform } from "node:stream";
import { basename, join, relative, resolve, sep } from "node:path";
import { DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager, createAgentSession, readStoredCredential } from "@earendil-works/pi-coding-agent";
import { assertNoSymlinkComponents, parseWorkOrder, safeRegularFile, sha256File, type WorkOrder } from "./contracts.js";
import { cseExtensionWithResult, safeCommandTool } from "./cse-extension.js";
import { ResultLifecycle, runOneTurn, tokenUsage } from "./lifecycle.js";
import { runCheck } from "./checks.js";
import { requireSandbox } from "./sandbox.js";
import { PHASE3_ROLES, runPhase3, type Phase3Hooks, type Phase3RunResult } from "./phase3.js";

export type RunResult = { schema_version: 1; run_id: string; status: "completed" | "preflight" | "blocked" | "failed" | "timed_out" | "cancelled" | "needs_parent_input"; result_path: string; result_sha256?: string } | Phase3RunResult;
type CheckResult = Awaited<ReturnType<typeof runCheck>>;
export type SnapshotOrder = Pick<WorkOrder, "workspace" | "access" | "context_files" | "budget">;
type EffectiveModel = { provider: string; model: string; effort: string };
const json = (value: unknown) => JSON.stringify(value, null, 2);
const compact = (value: unknown) => JSON.stringify(value);
const MAX_SNAPSHOT_FILES = 2048;
const MAX_SNAPSHOT_DEPTH = 32;
const MAX_SNAPSHOT_DIRECTORIES = 4096;
const snapshotBytes = (order: SnapshotOrder): number => Math.min(128 * 1024 * 1024, Math.max(1024 * 1024, order.budget.output_bytes * 16));

function throwIfAborted(signal?: AbortSignal): void { if (signal?.aborted) throw new Error("CSE-PI operation cancelled"); }
function identity(entries: readonly string[]): string { return createHash("sha256").update([...entries].sort().join("\n")).digest("hex"); }

export async function contentIdentity(root: string, files: readonly string[], signal?: AbortSignal, maxBytes = Number.MAX_SAFE_INTEGER): Promise<string> {
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

function effectiveModel(order: WorkOrder): EffectiveModel {
  const requested = { provider: order.worker?.provider ?? process.env.CSE_PI_PROVIDER ?? "openai-codex", model: order.worker?.model ?? process.env.CSE_PI_MODEL ?? "gpt-5.6-luna", effort: order.worker?.effort ?? process.env.CSE_PI_EFFORT ?? "high" };
  const efforts: Record<string, string[]> = { "gpt-5.6-luna": ["off", "minimal", "low", "medium", "high", "xhigh", "max"], "gpt-5.6-terra": ["off", "minimal", "low", "medium", "high", "xhigh", "max"], "gpt-5.6-sol": ["off", "minimal", "low", "medium", "high", "xhigh", "max"] };
  if (requested.provider !== "openai-codex" || !efforts[requested.model]?.includes(requested.effort)) throw new Error("CSE-PI capability error: unsupported provider/model/effort policy");
  return requested;
}

export function buildWorkerPrompt(order: WorkOrder, checks: readonly CheckResult[]): string {
  return ["You are the bounded CSE-Pi investigate worker. Read only the supplied snapshot and use only the safe command/check tools.", "The following assignment is authoritative; do not modify the source workspace. Finish with exactly one cse_submit_result call.", JSON.stringify({ task_id: order.task_id, objective: order.objective, scientific_question: order.scientific_question, constraints: order.constraints, non_goals: order.non_goals, context_files: order.context_files, access: order.access, expected_artifacts: order.expected_artifacts, acceptance_criteria: order.acceptance_criteria, validation: order.validation, scientific_checks: checks, known_context: order.known_context ?? [], parent_identity: order.parent_identity })].join("\n");
}

function writeEvent(events: string[], type: string, detail: unknown): void { events.push(JSON.stringify({ at: new Date().toISOString(), type, detail })); }
function boundedEvents(events: string[], maxBytes: number): string { const full = `${events.join("\n")}\n`; if (Buffer.byteLength(full) <= maxBytes) return full; const essential = [...events.slice(0, 3), JSON.stringify({ type: "events_truncated", retained: ["validated", "snapshotted", "sandbox_ready"] }), events.at(-1) ?? ""].filter(Boolean).join("\n") + "\n"; return Buffer.byteLength(essential) <= maxBytes ? essential : `${events[0] ?? ""}\n`; }

export async function run(orderRaw: unknown, resultDir: string, noInference = false, signal?: AbortSignal, hooks: Phase3Hooks = {}): Promise<RunResult> {
  if (typeof orderRaw === "object" && orderRaw !== null && PHASE3_ROLES.includes((orderRaw as { role?: string }).role as never)) {
    return runPhase3(orderRaw, resultDir, noInference, signal, hooks);
  }
  const order = parseWorkOrder(orderRaw); const runId = randomUUID(); const events: string[] = []; const started = performance.now(); const timeoutController = new AbortController(); let timedOut = false;
  const timeout = setTimeout(() => { timedOut = true; timeoutController.abort(); }, order.budget.wall_timeout_ms); const relay = () => timeoutController.abort(); signal?.addEventListener("abort", relay, { once: true }); if (signal?.aborted) timeoutController.abort(); const activeSignal = timeoutController.signal; const remaining = () => Math.max(1, Math.floor(order.budget.wall_timeout_ms - (performance.now() - started)));
  let status: RunResult["status"] = "failed"; const requested = { provider: order.worker?.provider ?? process.env.CSE_PI_PROVIDER ?? "openai-codex", model: order.worker?.model ?? process.env.CSE_PI_MODEL ?? "gpt-5.6-luna", effort: order.worker?.effort ?? process.env.CSE_PI_EFFORT ?? "high" }; let body: Record<string, unknown> = { schema_version: 1, run_id: runId, task_id: order.task_id, parent_identity: order.parent_identity, status, requested_model: { ...requested, provisional: !order.worker }, resolved_model: null, observed_model: null, runtime: { node: process.version, pi: "0.84.2" }, usage: null, retries: null, termination: null, model_authored: null, supervisor: { commands: [], checks: [], runtime_events: [], actual_changes: [], retained_evidence: [], source_before_after_equal: null } };
  let resultDirReady = false;
  try {
    const workspace = await realpath(order.workspace.root); if (basename(workspace) === ".git") throw new Error("workspace root cannot be .git");
    const resultParent = await existingParent(resolve(resultDir, "..")); if (resolve(resultDir) === workspace || resolve(resultDir).startsWith(`${workspace}/`) || resultParent === workspace || resultParent.startsWith(`${workspace}/`)) throw new Error("result directory must be outside workspace"); if (await exists(resultDir)) throw new Error("result directory must not already exist");
    await mkdir(resultDir, { recursive: false, mode: 0o700 }); resultDirReady = true; const validated = effectiveModel(order); requested.provider = validated.provider; requested.model = validated.model; requested.effort = validated.effort; writeEvent(events, "validated", { task_id: order.task_id, model: requested });
    const input = await snapshot(order, resultDir, activeSignal); const sourceBefore = await contentIdentity(workspace, input.files, activeSignal, snapshotBytes(order)); body.snapshot_identity = input.identity; body.snapshot_files = input.files; body.supervisor = { ...(body.supervisor as object), retained_evidence: ["input/", "events.jsonl", "scratch/", "command-evidence/"], source_before_after_equal: null }; writeEvent(events, "snapshotted", { identity: input.identity, files: input.files.length });
    await requireSandbox(activeSignal, Math.min(remaining(), 2000)); writeEvent(events, "sandbox_ready", { executable: "/usr/bin/bwrap" });
    const checks = await Promise.all(order.scientific_checks.map(async check => { throwIfAborted(activeSignal); const host = await safeRegularFile(workspace, check.path); const path = join(input.root, relative(workspace, host)); return runCheck({ ...check, path }, input.root, join(resultDir, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), order.budget.output_bytes, activeSignal); }));
    (body.supervisor as Record<string, unknown>).checks = checks; if (checks.some(check => !check.ok)) throw new Error("scientific check failed");
    if (noInference) { status = "preflight"; body.termination = "no_inference_preflight"; }
    else {
      throwIfAborted(activeSignal); const agentDir = process.env.CSE_PI_AGENT_DIR || join(process.env.HOME || "/nonexistent", ".pi", "agent"); const authPath = join(agentDir, "auth.json"); try { await access(authPath, constants.R_OK); } catch { throw new Error("CSE-PI capability error: read-only supported Pi auth is unavailable"); }
      if (!readStoredCredential(requested.provider, authPath)) throw new Error("CSE-PI capability error: supported subscription auth is unavailable"); const runtime = await ModelRuntime.create({ authPath, modelsPath: join(agentDir, "models.json"), refreshOnCreate: false, allowModelNetwork: false }); throwIfAborted(activeSignal);
      const model = runtime.getModel(requested.provider, requested.model); if (!model || !runtime.hasConfiguredAuth(requested.provider)) throw new Error(`CSE-PI capability error: supported subscription auth/model unavailable for ${requested.provider}/${requested.model}`);
      const lifecycle = new ResultLifecycle(); let submission: unknown = null; const loader = new DefaultResourceLoader({ cwd: input.root, agentDir: resultDir, noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true, extensionFactories: [cseExtensionWithResult(lifecycle, value => { submission = value; })], systemPrompt: "CSE-Pi trusted supervisor session." }); await loader.reload();
      const commands: unknown[] = []; const runtimeEvents: Record<string, unknown>[] = []; const { session } = await createAgentSession({ cwd: input.root, agentDir: resultDir, modelRuntime: runtime, model, thinkingLevel: requested.effort as any, noTools: "builtin", excludeTools: ["read", "bash", "edit", "write", "grep", "find", "ls"], customTools: [safeCommandTool(input.root, join(resultDir, "scratch"), Math.min(order.budget.command_timeout_ms, remaining()), order.budget.output_bytes, commands, join(resultDir, "command-evidence"))], resourceLoader: loader, sessionManager: SessionManager.inMemory(), settingsManager: SettingsManager.inMemory() });
      try {
        session.setActiveToolsByName(["cse_submit_result", "cse_run_command"]); if (!session.getActiveToolNames().includes("cse_submit_result") || !session.getActiveToolNames().includes("cse_run_command")) throw new Error("CSE Pi SDK integration did not register safe tools"); (body.supervisor as Record<string, unknown>).commands = commands; (body.supervisor as Record<string, unknown>).runtime_events = runtimeEvents;
        if (session.thinkingLevel !== requested.effort) throw new Error(`CSE-PI capability error: requested effort ${requested.effort} resolved to ${session.thinkingLevel}`); body.resolved_model = requested; body.observed_model = { provider: model.provider, model: model.id, effort: session.thinkingLevel };
        const terminal = await runOneTurn(session, buildWorkerPrompt(order, checks), lifecycle, { wall_timeout_ms: remaining(), model_turn_limit: order.budget.model_turn_limit }, activeSignal, event => { if (runtimeEvents.length < 256) runtimeEvents.push(event); writeEvent(events, "runtime", event); }); status = terminal === "turn_limit_exceeded" ? "failed" : terminal; body.model_authored = submission; body.termination = terminal; body.usage = tokenUsage(session.getSessionStats()); body.retries = session.retryAttempt; writeEvent(events, "terminal", { status, structured_submission: Boolean(submission) });
      } finally { session.dispose(); }
    }
    await hooks.beforeFinalIntegrity?.(); const sourceAfter = await contentIdentity(workspace, input.files, activeSignal, snapshotBytes(order)); const supervisor = body.supervisor as Record<string, unknown>; supervisor.source_before_after_equal = sourceBefore === sourceAfter; supervisor.actual_changes = sourceBefore === sourceAfter ? [] : ["permitted input content changed during run"]; if (sourceBefore !== sourceAfter) { status = "failed"; body.error = "workspace content integrity changed during run"; body.termination = "integrity_violation"; writeEvent(events, "integrity_violation", { before: sourceBefore, after: sourceAfter }); }
  } catch (error) {
    body.error = error instanceof Error ? error.message : String(error); writeEvent(events, "failed", body.error); if (timedOut) { status = "timed_out"; body.termination = "wall_timeout"; } else if (activeSignal.aborted || signal?.aborted) { status = "cancelled"; body.termination = "cancelled"; } else { const priorStatus = status; if (priorStatus !== "failed") (body.supervisor as Record<string, unknown>).source_before_after_equal = false; status = "failed"; body.termination = priorStatus === "failed" ? body.termination ?? "failed" : "integrity_check_failed"; }
  } finally { clearTimeout(timeout); signal?.removeEventListener("abort", relay); }
  if (!resultDirReady) throw new Error(String(body.error ?? "run could not create result directory"));
  body.status = status; await writeFile(join(resultDir, "events.jsonl"), boundedEvents(events, order.budget.output_bytes), "utf8"); let rendered = json(body);
  if (Buffer.byteLength(rendered) > order.budget.output_bytes) { status = "failed"; body = { schema_version: 1, run_id: runId, task_id: order.task_id, parent_identity: order.parent_identity, status, requested_model: requested, snapshot_identity: body.snapshot_identity ?? null, supervisor: { retained_evidence: ["input/", "events.jsonl", "scratch/", "command-evidence/"] }, error: "result exceeded output byte budget", usage: body.usage ?? null, retries: body.retries ?? null }; rendered = compact(body); }
  const resultPath = join(resultDir, "result.json"); await writeFile(resultPath, rendered, "utf8"); return { schema_version: 1, run_id: runId, status, result_path: resultPath, result_sha256: await sha256File(resultPath) };
}

async function exists(path: string): Promise<boolean> { try { await stat(path); return true; } catch { return false; } }
async function existingParent(path: string): Promise<string> { let current = path; while (!(await exists(current))) { const parent = resolve(current, ".."); if (parent === current) throw new Error("no existing result directory parent"); current = parent; } return realpath(current); }
