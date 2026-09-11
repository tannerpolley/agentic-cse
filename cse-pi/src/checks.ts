import { relative } from "node:path";
import { createHash } from "node:crypto";
import { runSandbox } from "./sandbox.js";

export type Check = { id: string; kind: "json" | "convergence" | "plot_metadata"; path: string; sha256: string; checker_identity?: string };
export function shellQuote(value: string): string { return "'" + value.replaceAll("'", "'\"'\"'") + "'"; }
export async function runCheck(check: Check, snapshot: string, scratch: string, timeout = 10000, bytes = 1_000_000, signal?: AbortSignal): Promise<{ id: string; checker_identity: string | null; ok: boolean; sha256: string; detail: string }> {
  const path = relative(snapshot, check.path); if (path.startsWith("..") || path === "") throw new Error("scientific check must target snapshot file");
  const result = await runSandbox("cat -- " + shellQuote("/workspace/" + path), snapshot, scratch, timeout, bytes, signal);
  if (result.evidence.exit_code !== 0 || result.evidence.output_limited) return { id: check.id, checker_identity: check.checker_identity ?? null, ok: false, sha256: "", detail: "sandboxed scientific-check read failed" };
  const actual = createHash("sha256").update(result.output).digest("hex");
  if (actual !== check.sha256) return { id: check.id, checker_identity: check.checker_identity ?? null, ok: false, sha256: actual, detail: "stale input SHA-256" };
  let value: unknown;
  try { value = JSON.parse(result.output); } catch { return { id: check.id, checker_identity: check.checker_identity ?? null, ok: false, sha256: actual, detail: "malformed JSON" }; }
  const finite = (v: unknown): boolean => typeof v === "number" ? Number.isFinite(v) : typeof v === "string" || typeof v === "boolean" || v === null ? true : Array.isArray(v) ? v.every(finite) : v && typeof v === "object" ? Object.values(v as Record<string, unknown>).every(finite) : false;
  if (!finite(value)) return { id: check.id, checker_identity: check.checker_identity ?? null, ok: false, sha256: actual, detail: "nonfinite numerical value" };
  if (check.kind === "convergence") {
    if (!Array.isArray(value) || value.length < 2 || value.some(row => !row || typeof row !== "object" || typeof (row as Record<string, unknown>).h !== "number" || typeof (row as Record<string, unknown>).error !== "number" || !((row as Record<string, unknown>).h as number > 0) || !((row as Record<string, unknown>).error as number > 0))) return { id: check.id, checker_identity: check.checker_identity ?? null, ok: false, sha256: actual, detail: "convergence rows require positive numeric h and error" };
    return { id: check.id, checker_identity: check.checker_identity ?? null, ok: true, sha256: actual, detail: "input structure only; no universal order is imposed" };
  }
  if (check.kind === "plot_metadata") return { id: check.id, checker_identity: check.checker_identity ?? null, ok: typeof value === "object" && value !== null ? true : false, sha256: actual, detail: "metadata only; does not verify rendered figure correctness" };
  return { id: check.id, checker_identity: check.checker_identity ?? null, ok: true, sha256: actual, detail: "valid finite JSON" };
}
