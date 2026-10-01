import { constants } from "node:fs";
import { randomUUID } from "node:crypto";
import { access, mkdir, realpath, writeFile } from "node:fs/promises";
import { dirname, join, resolve, sep } from "node:path";
import { DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager, createAgentSession, defineTool, readStoredCredential } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { runCheck, type Check } from "./checks.js";
import { sha256File } from "./contracts.js";
import { ResultLifecycle, runOneTurn, tokenUsage, type Runner } from "./lifecycle.js";
import { requireSandbox, type SandboxResult } from "./sandbox.js";
import { cseSubmitTool, safeCommandTool, writeTools } from "./cse-extension.js";
import { git, removeWorktree, retainCandidate, verifyIdentity, worktreeOptions } from "./worker.js";

export const PHASE3_SCHEMA_VERSION = 3;
export const PHASE3_ROLES = ["build"] as const;
export type Phase3Role = (typeof PHASE3_ROLES)[number];
export type Phase3Status = "completed" | "preflight" | "blocked" | "failed" | "timed_out" | "cancelled" | "needs_parent_input";
export type Phase3RunResult = { schema_version: 3; run_id: string; status: Phase3Status; result_path: string; result_sha256?: string };
type Phase3Model = { provider: string; model: string; effort: string };
type Phase3Path = { path: string; sha256: string; purpose: string };
export type Phase3WriteScope = { path: string; kind: "file" | "directory" };
export type Phase3WorkOrder = {
  schema_version: 3; task_id: string; role: Phase3Role; objective: string; scientific_question: string;
  workspace: { root: string; commit: string; expected_identity: string; dependency_paths?: string[] };
  context_files: Phase3Path[]; known_context: string[]; constraints: string[]; non_goals: string[];
  access: { read_paths: string[]; write_paths: string[]; write_scopes: Phase3WriteScope[]; forbidden_paths: string[] };
  write_policy: "candidate"; network_policy: "none"; expected_artifacts: string[]; acceptance_criteria: string[]; validation: string[];
  scientific_checks: Check[]; parent_identity: string;
  budget: { wall_timeout_ms: number; model_turn_limit: number; command_timeout_ms: number; output_bytes: number };
  worker?: { provider?: string; model?: string; effort?: string };
  specification: { text: string; required_changes: string[]; forbidden_changes: string[]; permitted_paths: string[] };
};
export type Phase3Hooks = {
  beforeFinalIntegrity?: () => void | Promise<void>;
  createSession?: (config: { role: Phase3Role; model: Phase3Model; prompt: string; tools: readonly unknown[] }) => Promise<Phase3Session>;
};
export type Phase3Session = Runner & {
  setActiveToolsByName(names: string[]): void; getActiveToolNames(): string[]; thinkingLevel?: string;
  getSessionStats?: () => unknown; retryAttempt?: number; dispose(): void | Promise<void>;
};
const EFFORTS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"];
const MODELS = ["gpt-6-astra", "gpt-6.1-sol", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"];
const DEFAULT_MODEL: Phase3Model = { provider: "openai-codex", model: "gpt-5.6-luna", effort: "high" };
function object(value: unknown, name: string, fields: string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(name + " must be an object");
  if (Object.keys(value).some(key => !fields.includes(key))) throw new Error(name + " has an unknown field");
  return value as Record<string, unknown>;
}
function text(value: unknown, name: string, max = 8000): string {
  if (typeof value !== "string" || !value.length || value.length > max) throw new Error(name + " must be a non-empty string of at most " + max + " characters");
  return value;
}
function strings(value: unknown, name: string, max = 128): string[] {
  if (!Array.isArray(value) || value.length > max) throw new Error(name + " must be an array");
  return value.map((item, index) => text(item, name + "[" + index + "]"));
}
function path(value: unknown, name: string): string {
  const raw = text(value, name, 4000).replaceAll("\\", "/"); const parts = raw.split("/").filter(Boolean);
  if (!parts.length || raw.startsWith("/") || parts.includes(".") || parts.includes("..")) throw new Error(name + " must be a relative non-escaping path");
  if (parts.some(part => [".git", ".pi", ".codex", ".ssh", ".aws", ".docker"].includes(part))) throw new Error(name + " contains administrative or secret content");
  return parts.join("/");
}
function paths(value: unknown, name: string): string[] {
  const result = strings(value, name).map(item => path(item, name));
  if (new Set(result).size !== result.length) throw new Error(name + " contains duplicate paths"); return result;
}
function hash(value: unknown, name: string): string { const result = text(value, name, 64); if (!/^[a-f0-9]{64}$/.test(result)) throw new Error(name + " must be lowercase SHA-256"); return result; }
function integer(value: unknown, name: string, min: number, max: number): number {
  if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) throw new Error(name + " must be an integer between " + min + " and " + max); return value as number;
}
function parseChecks(value: unknown): Check[] {
  if (!Array.isArray(value) || value.length > 128) throw new Error("scientific_checks must be an array");
  const checks = value.map((raw): Check => {
    const command = raw?.kind === "command";
    const check = object(raw, "scientific check", command ? ["id", "kind", "command", "timeout_ms"] : ["id", "kind", "path", "sha256", "checker_identity"]);
    const id = text(check.id, "check.id", 120);
    if (command) return { id, kind: "command", command: text(check.command, "check.command", 16000), ...(check.timeout_ms === undefined ? {} : { timeout_ms: integer(check.timeout_ms, "check.timeout_ms", 100, 3_600_000) }) };
    if (!["json", "convergence", "plot_metadata"].includes(String(check.kind))) throw new Error("scientific check kind is unsupported");
    return { id, kind: check.kind as "json" | "convergence" | "plot_metadata", path: path(check.path, "check.path"), sha256: hash(check.sha256, "check.sha256"), checker_identity: text(check.checker_identity ?? "cse-pi-phase3", "check.checker_identity", 200) };
  });
  if (new Set(checks.map(check => check.id)).size !== checks.length) throw new Error("scientific_checks contains duplicate ids");
  return checks;
}
export function parsePhase3WorkOrder(raw: unknown): Phase3WorkOrder {
  const value = object(raw, "CSE-Pi work order", ["schema_version", "task_id", "role", "objective", "scientific_question", "workspace", "context_files", "known_context", "constraints", "non_goals", "access", "write_policy", "network_policy", "expected_artifacts", "acceptance_criteria", "validation", "scientific_checks", "parent_identity", "budget", "worker", "specification"]);
  if (value.schema_version !== 3) throw new Error("CSE-Pi schema_version must be 3");
  if (value.role !== "build") throw new Error("CSE-Pi only supports role=build");
  const workspace = object(value.workspace, "workspace", ["root", "commit", "expected_identity", "dependency_paths"]);
  const root = text(workspace.root, "workspace.root", 4096); if (!root.startsWith("/")) throw new Error("workspace.root must be absolute");
  const commit = text(workspace.commit, "workspace.commit", 64); if (!/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(commit)) throw new Error("workspace.commit must be a full commit id");
  if (!Array.isArray(value.context_files)) throw new Error("context_files must be an array");
  const contextFiles = value.context_files.map(rawFile => { const file = object(rawFile, "context file", ["path", "sha256", "purpose"]); return { path: path(file.path, "context.path"), sha256: hash(file.sha256, "context.sha256"), purpose: text(file.purpose, "context.purpose") }; });
  if (new Set(contextFiles.map(file => file.path)).size !== contextFiles.length) throw new Error("context_files contains duplicate paths");
  const access = object(value.access, "access", ["read_paths", "write_paths", "write_scopes", "forbidden_paths"]);
  const writePaths = paths(access.write_paths ?? [], "access.write_paths");
  if (!writePaths.length || !Array.isArray(access.write_scopes)) throw new Error("build requires candidate write_paths and explicit write_scopes");
  const writeScopes = access.write_scopes.map(rawScope => {
    const scope = object(rawScope, "write scope", ["path", "kind"]);
    if (scope.kind !== "file" && scope.kind !== "directory") throw new Error("write scope kind is unsupported");
    return { path: path(scope.path, "write scope.path"), kind: scope.kind as Phase3WriteScope["kind"] };
  });
  if (new Set(writeScopes.map(scope => scope.path)).size !== writeScopes.length || writeScopes.length !== writePaths.length || writeScopes.some(scope => !writePaths.includes(scope.path))) throw new Error("write_scopes must exactly describe write_paths");
  if (value.write_policy !== "candidate") throw new Error("build requires write_policy=candidate");
  if (value.network_policy !== "none") throw new Error("only network_policy=none is supported");
  const budget = object(value.budget, "budget", ["wall_timeout_ms", "model_turn_limit", "command_timeout_ms", "output_bytes"]);
  const spec = object(value.specification ?? {}, "specification", ["text", "required_changes", "forbidden_changes", "permitted_paths"]);
  const specification = { text: text(spec.text ?? value.objective, "specification.text"), required_changes: strings(spec.required_changes ?? [], "required_changes"), forbidden_changes: strings(spec.forbidden_changes ?? [], "forbidden_changes"), permitted_paths: paths(spec.permitted_paths ?? writePaths, "permitted_paths") };
  if (specification.permitted_paths.some(item => !writeScopes.some(scope => item === scope.path || scope.kind === "directory" && item.startsWith(scope.path + "/")))) throw new Error("specification.permitted_paths exceeds write scope");
  let worker: Phase3WorkOrder["worker"];
  if (value.worker !== undefined) {
    const rawWorker = object(value.worker, "worker", ["provider", "model", "effort"]); worker = {};
    for (const key of ["provider", "model", "effort"] as const) if (rawWorker[key] !== undefined) worker[key] = text(rawWorker[key], "worker." + key, key === "effort" ? 20 : 200);
    if (worker.effort && !EFFORTS.includes(worker.effort)) throw new Error("worker.effort is unsupported");
  }
  return { schema_version: 3, role: "build", task_id: text(value.task_id, "task_id", 120), objective: text(value.objective, "objective"), scientific_question: text(value.scientific_question, "scientific_question"),
    workspace: { root, commit, expected_identity: hash(workspace.expected_identity, "workspace.expected_identity"), ...(workspace.dependency_paths === undefined ? {} : { dependency_paths: paths(workspace.dependency_paths, "workspace.dependency_paths") }) }, context_files: contextFiles,
    known_context: strings(value.known_context ?? [], "known_context"), constraints: strings(value.constraints ?? [], "constraints"), non_goals: strings(value.non_goals ?? [], "non_goals"),
    access: { read_paths: paths(access.read_paths ?? [], "access.read_paths"), write_paths: writePaths, write_scopes: writeScopes, forbidden_paths: paths(access.forbidden_paths ?? [], "access.forbidden_paths") },
    write_policy: "candidate", network_policy: "none", expected_artifacts: strings(value.expected_artifacts ?? [], "expected_artifacts"), acceptance_criteria: strings(value.acceptance_criteria ?? [], "acceptance_criteria"), validation: strings(value.validation ?? [], "validation"), scientific_checks: parseChecks(value.scientific_checks ?? []), parent_identity: text(value.parent_identity, "parent_identity", 400),
    budget: { wall_timeout_ms: integer(budget.wall_timeout_ms, "budget.wall_timeout_ms", 1000, 86_400_000), model_turn_limit: integer(budget.model_turn_limit, "budget.model_turn_limit", 1, 100), command_timeout_ms: integer(budget.command_timeout_ms, "budget.command_timeout_ms", 100, 3_600_000), output_bytes: integer(budget.output_bytes, "budget.output_bytes", 1024, 100_000_000) }, worker, specification };
}
function requestedModel(order: Phase3WorkOrder): Phase3Model {
  return { provider: order.worker?.provider ?? process.env.CSE_PI_BUILD_PROVIDER ?? process.env.CSE_PI_PROVIDER ?? DEFAULT_MODEL.provider, model: order.worker?.model ?? process.env.CSE_PI_BUILD_MODEL ?? process.env.CSE_PI_MODEL ?? DEFAULT_MODEL.model, effort: order.worker?.effort ?? process.env.CSE_PI_BUILD_EFFORT ?? process.env.CSE_PI_EFFORT ?? DEFAULT_MODEL.effort };
}
function rolePrompt(order: Phase3WorkOrder, root: string): string {
  return ["You are the bounded CSE-Pi build worker. The frozen work order is authoritative; do not expand scope.", "Your cwd is " + root + ". Use cse_edit for exact-text replacements, cse_write for new/whole files, and cse_run_command for sandboxed shell commands. Dependencies are read-only. Use /tmp for disposable scratch. Never install dependencies.", "Run declared checks with cse_run_check. The supervisor repeats checks on the final worktree. The parent decides whether to apply candidate.diff; never modify the source checkout.", JSON.stringify(order), "Submit exactly one terminating cse_submit_result call after the build work is complete."].join("\n");
}
async function existingParent(path: string): Promise<string> {
  let current = resolve(path); while (true) { try { return await realpath(current); } catch { const parent = dirname(current); if (parent === current) throw new Error("result directory has no existing parent"); current = parent; } }
}

export async function runPhase3(raw: unknown, resultDir: string, noInference = false, signal?: AbortSignal, hooks: Phase3Hooks = {}): Promise<Phase3RunResult> {
  const order = parsePhase3WorkOrder(raw); const runId = randomUUID(); const started = performance.now(); const startedAt = new Date().toISOString();
  const controller = new AbortController(); let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, order.budget.wall_timeout_ms);
  const activeSignal = signal ? AbortSignal.any([signal, controller.signal]) : controller.signal;
  const output = resolve(resultDir); const root = join(output, "worktree");
  const remaining = () => Math.max(1, Math.floor(order.budget.wall_timeout_ms - (performance.now() - started)));
  const commandTimeout = () => Math.min(order.budget.command_timeout_ms, remaining());
  let status: Phase3Status = "failed"; let resultReady = false; let worktreeAdded = false; let worktreeAttempted = false; let checkingIntegrity = false;
  const selectedModel = requestedModel(order); const commands: unknown[] = []; const runtimeEvents: Record<string, unknown>[] = []; const events: string[] = [];
  const body: Record<string, any> = { schema_version: 3, run_id: runId, task_id: order.task_id, role: order.role, parent_identity: order.parent_identity, status, started_at: startedAt, ended_at: null, wall_ms: null,
    requested_model: { ...selectedModel, source: order.worker ? "work_order" : "environment_or_role_default" }, resolved_model: selectedModel, observed_model: null, runtime: { node: process.version, role_defaults: DEFAULT_MODEL }, termination: null, model_requests: 0, usage: null, model_authored: null, role_result: null,
    worktree_commit: order.workspace.commit, workspace_identity: null, workspace_files: [], supervisor: { commands, checks: [], runtime_events: runtimeEvents, retained_evidence: ["candidate/", "candidate.diff", "events.jsonl", "command-evidence/"], source_before_after_equal: null, actual_changes: [] } };
  const retain = async (result: SandboxResult) => {
    const name = "command-" + commands.length + ".out"; await mkdir(join(output, "command-evidence"), { recursive: true });
    await writeFile(join(output, "command-evidence", name), result.raw_output, { flag: "wx", mode: 0o600 });
    const evidence = { ...result.evidence, output_path: "command-evidence/" + name }; commands.push(evidence); return evidence;
  };
  try {
    const workspace = await realpath(order.workspace.root); const parent = await existingParent(dirname(output));
    if ([output, parent].some(path => path === workspace || path.startsWith(workspace + sep))) throw new Error("result directory must be outside source workspace");
    await mkdir(output, { recursive: false, mode: 0o700 }); resultReady = true;
    if (selectedModel.provider !== "openai-codex" || !MODELS.includes(selectedModel.model) || !EFFORTS.includes(selectedModel.effort)) throw new Error("unsupported build provider/model/effort: " + Object.values(selectedModel).join("/"));
    const commit = (await git(workspace, ["rev-parse", "--verify", order.workspace.commit + "^{commit}"], activeSignal)).toString().trim();
    if (commit !== order.workspace.commit) throw new Error("workspace.commit did not resolve to itself");
    const sandbox = await worktreeOptions(order, activeSignal);
    await requireSandbox(activeSignal, Math.min(remaining(), 2000));
    worktreeAttempted = true; await git(workspace, ["worktree", "add", "--detach", root, commit], activeSignal); worktreeAdded = true;
    const frozen = await verifyIdentity(order, root, activeSignal); body.workspace_identity = frozen.identity; body.workspace_files = frozen.files;
    // The source may be on another revision or have local edits; only the worktree must match the order.
    const sourceState = () => git(workspace, ["diff", "--binary", "HEAD", "--"], activeSignal);
    const sourceBefore = await sourceState();
    events.push(JSON.stringify({ type: "validated", task_id: order.task_id, worktree_commit: commit }));
    const check = (item: Check) => runCheck(item, root, commandTimeout(), order.budget.output_bytes, activeSignal, sandbox, retain);
    if (noInference) { status = "preflight"; body.termination = "no_inference_preflight"; }
    else {
      const lifecycle = new ResultLifecycle();
      const tools = [safeCommandTool(root, commandTimeout, order.budget.output_bytes, sandbox, activeSignal, retain), ...writeTools(root, order, activeSignal),
        defineTool({ name: "cse_run_check", label: "Run declared check", description: "Run a frozen scientific check by id. The supervisor repeats it on the final worktree.", parameters: Type.Object({ id: Type.String({ minLength: 1 }) }), executionMode: "sequential", async execute(_id, params) {
          const item = order.scientific_checks.find(item => item.id === params.id); if (!item) throw new Error("unknown declared check: " + params.id);
          const { output: checkOutput, ...result } = await check(item); return { content: [{ type: "text" as const, text: JSON.stringify(result) + "\n" + checkOutput }], details: result, isError: !result.ok };
        } }), cseSubmitTool(lifecycle, value => { body.model_authored = value; })];
      const prompt = rolePrompt(order, root);
      let session: Phase3Session;
      if (hooks.createSession) session = await hooks.createSession({ role: order.role, model: selectedModel, prompt, tools });
      else {
        const agentDir = process.env.CSE_PI_AGENT_DIR || join(process.env.HOME || "/nonexistent", ".pi", "agent"); const authPath = join(agentDir, "auth.json");
        await access(authPath, constants.R_OK).catch(() => { throw new Error("CSE-PI capability error: supported Pi auth is unavailable"); });
        if (!readStoredCredential(selectedModel.provider, authPath)) throw new Error("CSE-PI capability error: supported subscription auth is unavailable");
        const runtime = await ModelRuntime.create({ authPath, modelsPath: join(agentDir, "models.json"), allowModelNetwork: false });
        const model = runtime.getModel(selectedModel.provider, selectedModel.model); if (!model || !runtime.hasConfiguredAuth(selectedModel.provider)) throw new Error("CSE-PI capability error: supported model is unavailable");
        const loader = new DefaultResourceLoader({ cwd: root, agentDir: output, noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true, systemPrompt: "CSE-Pi bounded worker." }); await loader.reload();
        const result = await createAgentSession({ cwd: root, agentDir: output, modelRuntime: runtime, model, thinkingLevel: selectedModel.effort as never, noTools: "builtin", excludeTools: ["read", "bash", "edit", "write", "grep", "find", "ls"], customTools: tools, resourceLoader: loader, sessionManager: SessionManager.inMemory(), settingsManager: SettingsManager.inMemory() });
        session = result.session as unknown as Phase3Session;
      }
      try {
        const names = tools.map(tool => tool.name); session.setActiveToolsByName(names);
        if (!names.every(name => session.getActiveToolNames().includes(name))) throw new Error("CSE-Pi tool registration failed");
        body.observed_model = { ...selectedModel, effort: session.thinkingLevel ?? null };
        if (session.thinkingLevel !== selectedModel.effort) throw new Error("observed effort mismatch");
        const terminal = await runOneTurn(session, prompt, lifecycle, order.budget, activeSignal, event => {
          if (event.type === "turn_start") body.model_requests++;
          if (runtimeEvents.length < 256) runtimeEvents.push(event);
        });
        body.termination = terminal; status = terminal === "turn_limit_exceeded" ? "failed" : terminal;
      } finally { if (session.getSessionStats) body.usage = tokenUsage(session.getSessionStats()); body.retries = session.retryAttempt ?? null; await session.dispose(); }
    }
    // These runs, not intermediate worker checks, determine the final check results.
    for (const item of order.scientific_checks) {
      if (activeSignal.aborted) break;
      const { output: _checkOutput, ...result } = await check(item); body.supervisor.checks.push(result);
    }
    if (activeSignal.aborted) { status = timedOut ? "timed_out" : "cancelled"; body.termination = timedOut ? "wall_timeout" : "cancelled"; }
    else if (!noInference && body.supervisor.checks.some((item: { ok: boolean }) => !item.ok)) { status = "failed"; body.termination = "scientific_check_failed"; }
    if (!activeSignal.aborted) {
      checkingIntegrity = true; await hooks.beforeFinalIntegrity?.();
      const sourceAfter = await sourceState(); body.supervisor.source_before_after_equal = sourceBefore.equals(sourceAfter);
      if (!body.supervisor.source_before_after_equal) { body.supervisor.actual_changes = ["source tracked content changed during CSE-Pi run"]; throw new Error("source workspace content changed during CSE-Pi run"); }
      checkingIntegrity = false;
    }
  } catch (error) {
    body.error = error instanceof Error ? error.message : String(error);
    if (checkingIntegrity) { status = "failed"; body.termination = "integrity_check_failed"; }
    else if (timedOut) { status = "timed_out"; body.termination = "wall_timeout"; }
    else if (activeSignal.aborted) { status = "cancelled"; body.termination = "cancelled"; }
    else { status = "failed"; body.termination ??= "failed"; }
  } finally {
    if (worktreeAdded) {
      try {
        const candidate = await retainCandidate(root, order.workspace.commit, output, paths => {
          const contains = (path: string, scope: string) => path === scope || path.startsWith(scope + "/");
          const violations = paths.filter(path => !order.access.write_scopes.some(scope => scope.kind === "directory" ? contains(path, scope.path) : path === scope.path) || order.access.forbidden_paths.some(scope => contains(path, scope)) || (order.workspace.dependency_paths ?? []).some(scope => contains(path, scope)));
          if (violations.length) { status = "failed"; body.termination = "scope_violation"; body.scope_violations = violations; }
        });
        body.candidate_changes = candidate.changes; body.diff_sha256 = candidate.diff_sha256;
        body.role_result = { outcome: body.model_authored?.outcome ?? null, files_changed: candidate.changes, validation_results: body.supervisor.checks };
      } catch (error) { status = "failed"; body.termination = body.scope_violations?.length ? "scope_violation" : "candidate_retention_failed"; body.candidate_error = String(error); }
    }
    if (worktreeAttempted) {
      try { await removeWorktree(order.workspace.root, root); body.worktree_removed = true; }
      catch (error) { status = "failed"; body.termination = "worktree_cleanup_failed"; body.cleanup_error = String(error); }
    }
    clearTimeout(timer);
  }
  if (!resultReady) throw new Error(String(body.error ?? "CSE-Pi run could not create result directory"));
  body.status = status; body.ended_at = new Date().toISOString(); body.wall_ms = Math.round(performance.now() - started);
  events.push(...runtimeEvents.map(event => JSON.stringify(event)), JSON.stringify({ type: "terminal", status }));
  const fullEvents = events.join("\n") + "\n";
  await writeFile(join(output, "events.jsonl"), Buffer.byteLength(fullEvents) <= order.budget.output_bytes ? fullEvents : events[0] + "\n" + JSON.stringify({ type: "events_truncated" }) + "\n" + events.at(-1) + "\n", { mode: 0o600 });
  let rendered = JSON.stringify(body, null, 2);
  if (Buffer.byteLength(rendered) > order.budget.output_bytes) {
    status = "failed";
    rendered = JSON.stringify({ schema_version: 3, run_id: runId, task_id: order.task_id, status, termination: body.termination, started_at: body.started_at, ended_at: body.ended_at, wall_ms: body.wall_ms, worktree_commit: body.worktree_commit, model_requests: body.model_requests, usage: body.usage, error: "result exceeded output byte budget" });
    if (Buffer.byteLength(rendered) > order.budget.output_bytes) throw new Error("minimum result exceeds output byte budget");
  }
  const resultPath = join(output, "result.json"); await writeFile(resultPath, rendered, { mode: 0o600 });
  return { schema_version: 3, run_id: runId, status, result_path: resultPath, result_sha256: await sha256File(resultPath) };
}
