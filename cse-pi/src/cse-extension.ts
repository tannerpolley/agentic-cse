import { lstat, mkdir, readFile, realpath, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { Type } from "typebox";
import { createEditToolDefinition, defineTool, withFileMutationQueue } from "@earendil-works/pi-coding-agent";
import { under, writablePath } from "./contracts.js";
import type { Phase3WorkOrder } from "./phase3.js";
import { runSandbox, type SandboxOptions } from "./sandbox.js";
import { ResultLifecycle } from "./lifecycle.js";

export const cseSubmitTool = (lifecycle = new ResultLifecycle(), submitted?: (value: unknown) => void) => defineTool({
  name: "cse_submit_result", label: "Submit CSE result", description: "Terminate with a structured CSE result.",
  parameters: Type.Object({ outcome: Type.Union([Type.Literal("accepted"), Type.Literal("inconclusive"), Type.Literal("blocked"), Type.Literal("needs_parent_input")]), facts: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), assumptions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 32 }), findings: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), evidence: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), limitations: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 32 }), deviations: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), questions: Type.Array(Type.String({ minLength: 1 }), { maxItems: 16 }), recommended_parent_action: Type.String({ minLength: 1, maxLength: 2000 }) }),
  executionMode: "sequential",
  async execute(_id, params) { lifecycle.submit(params.outcome); submitted?.(params); return { content: [{ type: "text" as const, text: JSON.stringify(params) }], details: params, terminate: true }; },
});
export function safeCommandTool(worktree: string, timeoutMs: () => number, outputBytes: number, sandboxOptions: SandboxOptions, signal: AbortSignal, retain: (result: Awaited<ReturnType<typeof runSandbox>>) => Promise<unknown>) {
  return defineTool({ name: "cse_run_command", label: "Run isolated command", description: "Run a bounded shell command in the worktree, without network or host credentials; dependencies are read-only.", parameters: Type.Object({ command: Type.String({ minLength: 1, maxLength: 16000 }) }), executionMode: "sequential", async execute(_id, params, toolSignal) {
    const result = await runSandbox(params.command, worktree, timeoutMs(), outputBytes, toolSignal ? AbortSignal.any([signal, toolSignal]) : signal, sandboxOptions);
    const evidence = await retain(result);
    return { content: [{ type: "text" as const, text: result.output }], details: evidence, isError: result.evidence.exit_code !== 0 || result.evidence.output_limited || result.evidence.timed_out };
  } });
}

async function writableTarget(root: string, rawPath: string, order: Phase3WorkOrder, allowMissing: boolean): Promise<string> {
  const path = relative(root, resolve(root, rawPath)).split(sep).join("/");
  const target = under(root, path);
  if (!writablePath(order, path)) throw new Error("write is outside frozen scope: " + path);
  let current = root;
  const parts = path.split("/");
  for (let index = 0; index < parts.length; index++) {
    current = join(current, parts[index]);
    try {
      const info = await lstat(current);
      if (info.isSymbolicLink() || (index < parts.length - 1 ? !info.isDirectory() : !info.isFile() || info.nlink !== 1)) throw new Error("write target is not a regular non-symlink path");
      const actual = await realpath(current); if (!actual.startsWith(root + sep)) throw new Error("write target escapes worktree");
    } catch (error) { if (!allowMissing || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
  }
  return target;
}
export function writeTools(root: string, order: Phase3WorkOrder, signal: AbortSignal) {
  const target = (path: string, missing: boolean) => { if (signal.aborted) throw new Error("CSE-PI operation cancelled"); return writableTarget(root, path, order, missing); };
  const edit = createEditToolDefinition(root, { operations: {
    access: async path => { await target(path, false); },
    readFile: async path => readFile(await target(path, false)),
    writeFile: async (path, content) => { await writeFile(await target(path, false), content); },
  } });
  return [
    defineTool({ name: "cse_edit", label: "Edit worktree file", description: edit.description, parameters: edit.parameters, executionMode: "sequential", execute: (id, params, toolSignal, onUpdate, ctx) => edit.execute(id, params, toolSignal ? AbortSignal.any([signal, toolSignal]) : signal, onUpdate, ctx) }),
    defineTool({ name: "cse_write", label: "Write worktree file", description: "Create or overwrite one regular, non-symlink file within the frozen write scope.", parameters: Type.Object({ path: Type.String({ minLength: 1 }), content: Type.String() }), executionMode: "sequential", async execute(_id, params, toolSignal) {
      return withFileMutationQueue(resolve(root, params.path), async () => {
        if (toolSignal?.aborted) throw new Error("CSE-PI operation cancelled");
        const path = await target(params.path, true); await mkdir(dirname(path), { recursive: true });
        await writeFile(await target(params.path, true), params.content);
        return { content: [{ type: "text" as const, text: "wrote " + params.path }], details: { path: params.path } };
      });
    } }),
  ];
}
