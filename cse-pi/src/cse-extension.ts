import { mkdir, writeFile } from "node:fs/promises";
import { join, relative, resolve, sep } from "node:path";
import { Type } from "typebox";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { runSandbox, type SandboxOptions } from "./sandbox.js";
import { ResultLifecycle } from "./lifecycle.js";

export const CSE_GUIDANCE = "Investigate only. State evidence, assumptions, limitations, and remaining uncertainty. Distinguish code verification, solution verification, fitting, prediction, and physical validation. Use cse_submit_result as the terminating structured submission; plain text is not accepted.";
export const cseSubmitTool = (lifecycle = new ResultLifecycle(), submitted?: (value: unknown) => void) => defineTool({
  name: "cse_submit_result", label: "Submit CSE result", description: "Terminate with a structured CSE result.",
  parameters: Type.Object({ outcome: Type.Union([Type.Literal("accepted"), Type.Literal("inconclusive"), Type.Literal("blocked"), Type.Literal("needs_parent_input")]), facts: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), assumptions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 32 }), findings: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), evidence: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), limitations: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), deviations: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), questions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), recommended_parent_action: Type.String({ minLength: 1, maxLength: 2000 }) }),
  executionMode: "sequential",
  async execute(_id, params) { lifecycle.submit(params.outcome); submitted?.(params); return { content: [{ type: "text" as const, text: JSON.stringify(params) }], details: params, terminate: true }; },
});
export function cseExtension(pi: ExtensionAPI): void {
  pi.on("before_agent_start", event => ({ systemPrompt: `${event.systemPrompt}\n\n${CSE_GUIDANCE}` }));
  pi.registerTool(cseSubmitTool());
}
export const cseExtensionWithResult = (lifecycle: ResultLifecycle, submitted: (value: unknown) => void) => (pi: ExtensionAPI): void => { pi.on("before_agent_start", event => ({ systemPrompt: `${event.systemPrompt}\n\n${CSE_GUIDANCE}` })); pi.registerTool(cseSubmitTool(lifecycle, submitted)); };
export function safeCommandTool(snapshot: string, scratch: string, timeoutMs: number, outputBytes: number, evidence: unknown[], retainedEvidenceDir = join(resolve(scratch, ".."), "command-evidence"), sandboxOptions: SandboxOptions = {}) {
  const snapshotRoot = resolve(snapshot); const scratchRoot = resolve(scratch); const evidenceRoot = resolve(retainedEvidenceDir); if (evidenceRoot === snapshotRoot || evidenceRoot.startsWith(snapshotRoot + sep)) throw new Error("supervisor command evidence must be outside the snapshot"); if (evidenceRoot === scratchRoot || evidenceRoot.startsWith(scratchRoot + sep)) throw new Error("supervisor command evidence must be outside candidate scratch");
  const parentRoot = resolve(scratch, ".."); const evidencePrefix = relative(parentRoot, evidenceRoot).replaceAll("\\", "/"); if (!evidencePrefix || evidencePrefix === "." || evidencePrefix.startsWith(`..${sep}`) || evidencePrefix.startsWith("../") || evidencePrefix.startsWith("/")) throw new Error("supervisor command evidence must be parent-relative");
  return defineTool({ name: "cse_run_command", label: "Run isolated command", description: "Run a bounded command against the read-only input snapshot and writable scratch.", parameters: Type.Object({ command: Type.String({ minLength: 1, maxLength: 16000 }) }), executionMode: "sequential", async execute(_id, params, signal) {
 const result = await runSandbox(params.command, snapshot, scratch, timeoutMs, outputBytes, signal, sandboxOptions);
    const outputName = `command-${evidence.length}.out`;
    await mkdir(evidenceRoot, { recursive: true, mode: 0o700 });
    const outputPath = join(evidenceRoot, outputName);
    const evidencePath = `${evidencePrefix}/${outputName}`;
    await writeFile(outputPath, result.raw_output, { flag: "wx", mode: 0o600 });
    evidence.push({ ...result.evidence, output_path: evidencePath });
    return { content: [{ type: "text" as const, text: result.output }], details: { ...result.evidence, output_path: evidencePath }, isError: result.evidence.exit_code !== 0 || result.evidence.scratch_limited || result.evidence.workspace_limited === true };
  } });
}
