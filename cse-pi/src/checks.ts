import { join } from "node:path";
import { createHash } from "node:crypto";
import { runSandbox, type SandboxOptions, type SandboxResult } from "./sandbox.js";

export type Check =
  | { id: string; kind: "command"; command: string; timeout_ms?: number; checker_identity?: string }
  | { id: string; kind: "json" | "convergence" | "plot_metadata"; path: string; sha256: string; checker_identity?: string };
export function shellQuote(value: string): string { return "'" + value.replaceAll("'", "'\"'\"'") + "'"; }
export async function runCheck(check: Check, worktree: string, timeout: number, bytes: number, signal: AbortSignal | undefined, options: SandboxOptions, retain: (result: SandboxResult) => Promise<unknown>) {
  const command = check.kind === "command" ? check.command : "cat -- " + shellQuote(join(worktree, check.path));
  const result = await runSandbox(command, worktree, Math.min(timeout, check.kind === "command" ? check.timeout_ms ?? timeout : timeout), bytes, signal, options);
  const evidence = await retain(result);
  const base = { id: check.id, kind: check.kind, checker_identity: check.checker_identity ?? null, evidence, output: result.output };
  if (check.kind === "command") return { ...base, ok: result.evidence.exit_code === 0 && !result.evidence.output_limited && !result.evidence.timed_out, exit_code: result.evidence.exit_code, detail: "sandboxed command check" };
  if (result.evidence.exit_code !== 0 || result.evidence.output_limited) return { ...base, ok: false, sha256: "", detail: "sandboxed scientific-check read failed" };
  const actual = createHash("sha256").update(result.raw_output).digest("hex");
  if (actual !== check.sha256) return { ...base, ok: false, sha256: actual, detail: "stale input SHA-256" };
  let value: unknown;
  try { value = JSON.parse(result.output); } catch { return { ...base, ok: false, sha256: actual, detail: "malformed JSON" }; }
  const finite = (v: unknown): boolean => typeof v === "number" ? Number.isFinite(v) : typeof v === "string" || typeof v === "boolean" || v === null ? true : Array.isArray(v) ? v.every(finite) : v && typeof v === "object" ? Object.values(v as Record<string, unknown>).every(finite) : false;
  if (!finite(value)) return { ...base, ok: false, sha256: actual, detail: "nonfinite numerical value" };
  if (check.kind === "convergence") {
    if (!Array.isArray(value) || value.length < 2 || value.some(row => !row || typeof row !== "object" || typeof (row as Record<string, unknown>).h !== "number" || typeof (row as Record<string, unknown>).error !== "number" || !((row as Record<string, unknown>).h as number > 0) || !((row as Record<string, unknown>).error as number > 0))) return { ...base, ok: false, sha256: actual, detail: "convergence rows require positive numeric h and error" };
    return { ...base, ok: true, sha256: actual, detail: "input structure only; no universal order is imposed" };
  }
  if (check.kind === "plot_metadata") return { ...base, ok: typeof value === "object" && value !== null, sha256: actual, detail: "metadata only; does not verify rendered figure correctness" };
  return { ...base, ok: true, sha256: actual, detail: "valid finite JSON" };
}
