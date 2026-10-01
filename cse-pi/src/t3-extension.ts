import { readFile } from "node:fs/promises";
import type { ExtensionAPI, ExtensionCommandContext, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { runPhase3, type Phase3Session } from "./phase3.js";

export const T3_BUILD_USAGE = "Usage: /cse-build /absolute/work-order.json /absolute/new-result-directory";
const WORKER_SYSTEM_PROMPT = "CSE-Pi bounded worker.";
const WORKER_TOOLS = new Set(["cse_run_command", "cse_edit", "cse_write", "cse_run_check", "cse_submit_result"]);
type Listener = (event: Record<string, unknown>) => void;

/**
 * Pi extension for hosts that run Pi as a visible subagent (T3 Code). `/cse-build` runs the
 * same Build worker as `cse-pi run`, but the current Pi session is the worker session: its
 * turns and tool calls appear in the host while the worktree, worker tools,
 * Bubblewrap commands and retained evidence stay unchanged.
 *
 * Pi starts a message sent from a command only after the command returns, so the command
 * returns as soon as the worker prompt is sent. The worker tools and system prompt stay in
 * force until that run settles, after any automatic retry or compaction; runPhase3 then
 * finalizes and writes `result.json` last, which is the parent's completion signal. Nothing is
 * posted after the run, because hosts end the child when it settles.
 *
 * Load this extension only in a Pi instance dedicated to CSE-Pi: it blocks every tool except
 * the worker's own, so a prompt that is not a well-formed `/cse-build` gets no tools at all.
 */
export default function cseT3Worker(pi: ExtensionAPI): void {
  const listeners = new Set<Listener>();
  let active = false;
  let hostContext: ExtensionContext | undefined;
  let endRun: (() => void) | undefined;
  const forward = (event: Record<string, unknown>) => { for (const listener of listeners) listener(event); };
  pi.on("turn_start", (event, ctx) => { hostContext = ctx; forward({ ...event }); });
  pi.on("message_end", event => forward({ ...event }));
  pi.on("tool_execution_end", event => forward({ ...event }));
  pi.on("agent_settled", () => { const end = endRun; endRun = undefined; end?.(); });
  pi.on("tool_call", event =>
    WORKER_TOOLS.has(event.toolName) ? undefined : { block: true, reason: "This CSE-Pi session only runs CSE-Pi worker tools." },
  );
  // Match the headless worker: no user skills, context files or host guidance in the prompt.
  pi.on("before_agent_start", () => (active ? { systemPrompt: WORKER_SYSTEM_PROMPT } : undefined));

  pi.registerCommand("cse-build", {
    description: "Run a CSE-Pi Build work order as this session: /cse-build <work-order.json> <result-dir>",
    handler: async (args: string, ctx: ExtensionCommandContext) => {
      const [taskPath, resultDir, ...rest] = args.trim().split(/\s+/u);
      if (!taskPath?.startsWith("/") || !resultDir?.startsWith("/") || rest.length > 0) {
        ctx.ui.notify(T3_BUILD_USAGE, "error");
        return;
      }
      if (active) {
        ctx.ui.notify("A CSE-Pi work order is already running in this session.", "error");
        return;
      }
      let order: unknown;
      try {
        order = JSON.parse(await readFile(taskPath, "utf8"));
      } catch (error) {
        ctx.ui.notify(`Cannot read work order: ${error instanceof Error ? error.message : String(error)}`, "error");
        return;
      }
      const previousTools = pi.getActiveTools();
      const cancel = new AbortController();
      let promptSent!: () => void;
      const sent = new Promise<void>(resolve => { promptSent = resolve; });
      active = true;
      void runPhase3(order, resultDir, false, cancel.signal, {
        createSession: async ({ model, tools }) => {
          const observed = ctx.model;
          if (observed?.provider !== model.provider || observed.id !== model.model) {
            throw new Error(`T3 child runs ${observed?.provider ?? "no provider"}/${observed?.id ?? "no model"}; the work order requires ${model.provider}/${model.model}. Delegate with that model.`);
          }
          for (const tool of tools) pi.registerTool(tool as Parameters<ExtensionAPI["registerTool"]>[0]);
          const priorEntries = new Set(ctx.sessionManager.getEntries().map(entry => entry.id));
          let runEnded: Promise<void> = Promise.resolve();
          // Set when the worker aborts itself (turn limit, timeout, cancellation) so that abort keeps its own status.
          let selfAborted = false;
          const session: Phase3Session = {
            setActiveToolsByName: names => pi.setActiveTools(names),
            getActiveToolNames: () => pi.getActiveTools(),
            thinkingLevel: pi.getThinkingLevel(),
            async prompt(text) {
              runEnded = new Promise<void>(resolve => { endRun = resolve; });
              pi.sendUserMessage(text);
              promptSent();
            },
            waitForIdle: () => runEnded,
            abort() {
              selfAborted = true;
              const host = hostContext ?? ctx;
              host.abort();
              // A run that never started has no agent_settled to wait for.
              if (host.isIdle()) { const end = endRun; endRun = undefined; end?.(); }
            },
            subscribe(listener) {
              // A host Stop aborts the run; report it as cancellation rather than a missing submission.
              // An abort the worker requested keeps the status the lifecycle already recorded.
              const wrapped: Listener = event => {
                const message = event.message as { stopReason?: string } | undefined;
                if (event.type === "message_end" && message?.stopReason === "aborted" && !selfAborted) cancel.abort();
                listener(event);
              };
              listeners.add(wrapped);
              return () => listeners.delete(wrapped);
            },
            getSessionStats() {
              // ExtensionContext exposes the session manager, not AgentSession.getSessionStats().
              // Read persisted usage, including retries/compaction, and exclude earlier host work.
              const tokens = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 };
              for (const entry of ctx.sessionManager.getEntries()) {
                if (priorEntries.has(entry.id)) continue;
                const usage = entry.type === "message" && (entry.message.role === "assistant" || entry.message.role === "toolResult") ? entry.message.usage
                  : (entry.type === "compaction" || entry.type === "branch_summary") ? entry.usage : undefined;
                if (!usage) continue;
                for (const key of ["input", "output", "cacheRead", "cacheWrite"] as const) tokens[key] += usage[key];
              }
              tokens.total = tokens.input + tokens.output + tokens.cacheRead + tokens.cacheWrite;
              return { tokens };
            },
            dispose: () => pi.setActiveTools(previousTools),
          };
          return session;
        },
      })
        .catch(error => {
          // Only failures before the result directory exists land here; later ones are in result.json.
          ctx.ui.notify(`CSE-Pi work order failed: ${error instanceof Error ? error.message : String(error)}`, "error");
        })
        .finally(() => {
          active = false;
          pi.setActiveTools(previousTools);
          promptSent();
        });
      // Return so Pi can start the worker run; the restrictions above outlive this handler.
      await sent;
    },
  });
}
