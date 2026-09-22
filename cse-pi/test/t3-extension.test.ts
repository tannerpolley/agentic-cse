import assert from "node:assert/strict";
import { lstat, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import cseT3Worker, { T3_BUILD_USAGE } from "../src/t3-extension.ts";
import { fixture } from "./build-fixture.ts";

type Tool = { name: string; execute: (id: string, params: any) => Promise<any> };
type Handler = (event: any) => unknown;
const SUBMIT = { outcome: "accepted", facts: ["changed candidate"], assumptions: [], findings: ["candidate changed"], evidence: ["candidate.diff"], limitations: ["parent must inspect"], deviations: [], questions: [], recommended_parent_action: "inspect candidate" };

/**
 * A Pi host whose agent run executes `agent` against the tools active when it starts. Like Pi,
 * a message sent from a command runs only after the command handler returns.
 */
function fakeHost(options: { model?: { provider: string; id: string }; thinking?: string; retries?: number; agent: (tools: Map<string, Tool>, attempt: number) => Promise<string | undefined> }) {
  const handlers = new Map<string, Handler[]>();
  const tools = new Map<string, Tool>();
  const notes: string[] = [];
  const seen = { systemPrompt: undefined as string | undefined, activeDuringRun: [] as string[], activePerAttempt: [] as string[][], ran: false };
  let active = ["read", "bash", "t3_thread_list"];
  let queued: (() => Promise<void>) | undefined;
  let command: ((args: string, ctx: any) => Promise<void>) | undefined;
  const emit = (type: string, event: Record<string, unknown>) => handlers.get(type)?.map(handler => handler({ type, ...event }));
  const pi = {
    on(type: string, handler: Handler) { handlers.set(type, [...(handlers.get(type) ?? []), handler]); },
    registerCommand(name: string, spec: { handler: typeof command }) { if (name === "cse-build") command = spec.handler; },
    registerTool(tool: Tool) { tools.set(tool.name, tool); },
    getActiveTools: () => [...active],
    setActiveTools(names: string[]) { active = [...names]; },
    getThinkingLevel: () => options.thinking ?? "high",
    sendUserMessage() {
      queued = async () => {
        seen.ran = true;
        seen.systemPrompt = (emit("before_agent_start", { systemPrompt: "host prompt" })?.[0] as { systemPrompt?: string } | undefined)?.systemPrompt;
        seen.activeDuringRun = [...active];
        // Like Pi, an automatic retry continues after agent_end; agent_settled comes last.
        for (let attempt = 0; attempt <= (options.retries ?? 0); attempt += 1) {
          seen.activePerAttempt.push([...active]);
          emit("turn_start", { turnIndex: attempt });
          const stopReason = await options.agent(new Map([...tools].filter(([name]) => active.includes(name))), attempt);
          emit("message_end", { message: { role: "assistant", content: [{ type: "toolCall" }], stopReason: stopReason ?? "toolUse" } });
          emit("agent_end", {});
          await new Promise(resolve => setTimeout(resolve, 20));
        }
        emit("agent_settled", {});
      };
    },
  };
  cseT3Worker(pi as never);
  const ctx = { model: options.model ?? { provider: "openai-codex", id: "gpt-5.6-luna" }, ui: { notify: (message: string) => notes.push(message) }, isIdle: () => true, abort() {} };
  const runCommand = async (args: string) => {
    await command!(args, ctx);
    const run = queued;
    queued = undefined;
    await run?.();
  };
  const toolCall = (toolName: string) => (handlers.get("tool_call") ?? []).map(handler => handler({ type: "tool_call", toolCallId: "1", toolName, input: {} }))[0];
  return { runCommand, notes, seen, activeTools: () => active, toolCall };
}

/** result.json is written last, after the worker run; it is the parent's completion signal. */
async function resultOf(resultDir: string): Promise<any> {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    try { return JSON.parse(await readFile(join(resultDir, "result.json"), "utf8")); } catch { await new Promise(resolve => setTimeout(resolve, 25)); }
  }
  throw new Error("result.json was not written");
}

async function orderFile(modelTurnLimit?: number): Promise<{ data: Awaited<ReturnType<typeof fixture>>; path: string; resultDir: string }> {
  const data = await fixture();
  const path = join(data.base, "order.json");
  const budget = modelTurnLimit === undefined ? data.order.budget : { ...data.order.budget, model_turn_limit: modelTurnLimit };
  await writeFile(path, JSON.stringify({ ...data.order, budget }));
  return { data, path, resultDir: join(data.base, "run") };
}

test("/cse-build runs the Build worker as the host session and restores its tools", async () => {
  const { data, path, resultDir } = await orderFile();
  const host = fakeHost({
    async agent(tools) {
      await tools.get("cse_write_candidate")!.execute("write", { path: "model.txt", content: "after\n" });
      await tools.get("cse_submit_result")!.execute("submit", SUBMIT);
      return undefined;
    },
  });
  try {
    await host.runCommand(`${path} ${resultDir}`);
    const body = await resultOf(resultDir);
    assert.equal(body.status, "completed");
    assert.equal(body.candidate_changes[0].path, "model.txt");
    assert.equal(body.supervisor.source_before_after_equal, true);
    assert.equal(await readFile(join(data.source, "model.txt"), "utf8"), "before\n");
    assert.deepEqual(host.seen.activeDuringRun.sort(), ["cse_delete_candidate", "cse_run_command", "cse_submit_result", "cse_write_candidate"]);
    assert.equal(host.seen.systemPrompt, "CSE-Pi bounded worker.");
    assert.deepEqual(host.activeTools(), ["read", "bash", "t3_thread_list"]);
  } finally {
    await rm(data.base, { recursive: true, force: true });
  }
});

test("/cse-build records a host model that differs from the work order instead of running", async () => {
  const { data, path, resultDir } = await orderFile();
  const host = fakeHost({ model: { provider: "openai-codex", id: "gpt-6-luna" }, async agent() { return undefined; } });
  try {
    await host.runCommand(`${path} ${resultDir}`);
    const body = await resultOf(resultDir);
    assert.equal(body.status, "failed");
    assert.match(body.error, /requires openai-codex\/gpt-5\.6-luna/);
    assert.equal(host.seen.ran, false);
  } finally {
    await rm(data.base, { recursive: true, force: true });
  }
});

test("/cse-build reports a host stop as cancellation", async () => {
  const { data, path, resultDir } = await orderFile();
  const host = fakeHost({ async agent() { return "aborted"; } });
  try {
    await host.runCommand(`${path} ${resultDir}`);
    const body = await resultOf(resultDir);
    assert.equal(body.status, "cancelled");
    assert.equal(await readFile(join(data.source, "model.txt"), "utf8"), "before\n");
  } finally {
    await rm(data.base, { recursive: true, force: true });
  }
});

test("/cse-build rejects relative paths without creating a result", async () => {
  const { data, resultDir } = await orderFile();
  const host = fakeHost({ async agent() { return undefined; } });
  try {
    await host.runCommand(`order.json ${resultDir}`);
    assert.deepEqual(host.notes, [T3_BUILD_USAGE]);
    await assert.rejects(() => lstat(resultDir), /ENOENT/);
  } finally {
    await rm(data.base, { recursive: true, force: true });
  }
});

test("/cse-build keeps the worker tools through Pi's automatic retry", async () => {
  const { data, path, resultDir } = await orderFile(5);
  const host = fakeHost({
    retries: 1,
    async agent(tools, attempt) {
      if (attempt === 0) return "error";
      await tools.get("cse_write_candidate")!.execute("write", { path: "model.txt", content: "after\n" });
      await tools.get("cse_submit_result")!.execute("submit", SUBMIT);
      return undefined;
    },
  });
  try {
    await host.runCommand(`${path} ${resultDir}`);
    const body = await resultOf(resultDir);
    assert.equal(body.status, "completed");
    for (const active of host.seen.activePerAttempt) assert.ok(!active.includes("bash"), `host tools active during an attempt: ${active}`);
    assert.equal(await readFile(join(data.source, "model.txt"), "utf8"), "before\n");
  } finally {
    await rm(data.base, { recursive: true, force: true });
  }
});

test("a CSE-Pi session blocks every tool except the worker tools", () => {
  const host = fakeHost({ async agent() { return undefined; } });
  assert.deepEqual(host.toolCall("bash"), { block: true, reason: "This CSE-Pi session only runs CSE-Pi worker tools." });
  assert.equal(host.toolCall("t3_thread_list")?.block, true);
  assert.equal(host.toolCall("cse_run_command"), undefined);
});
