export type WorkerTerminal = "completed" | "needs_parent_input" | "blocked" | "failed" | "timed_out" | "cancelled" | "turn_limit_exceeded";
export function tokenUsage(stats: unknown): unknown { return stats && typeof stats === "object" && !Array.isArray(stats) && "tokens" in stats ? (stats as { tokens: unknown }).tokens : stats ?? null; }
export class ResultLifecycle {
  private submitted = false;
  private value: WorkerTerminal | undefined;
  plainFinal(): never { throw new Error("plain final is not an accepted structured submission"); }
  submit(outcome: "accepted" | "inconclusive" | "blocked" | "needs_parent_input"): WorkerTerminal {
    if (this.submitted) throw new Error("duplicate structured submission"); this.submitted = true;
    return this.value = outcome === "needs_parent_input" ? "needs_parent_input" : outcome === "blocked" ? "blocked" : "completed";
  }
  terminal(): WorkerTerminal | undefined { return this.value; }
}
export type Runner = { prompt(text: string): Promise<void>; waitForIdle(): Promise<void>; abort(): Promise<void> | void; subscribe(listener: (event: any) => void): () => void };
export async function runOneTurn(session: Runner, prompt: string, lifecycle: ResultLifecycle, budget: { wall_timeout_ms: number; model_turn_limit: number }, signal?: AbortSignal, onEvent?: (event: Record<string, unknown>) => void): Promise<WorkerTerminal> {
  if (signal?.aborted) return "cancelled";
  let turns = 0; let plain = false; let cancelled = false; let timedOut = false; let turnLimitExceeded = false;
  const cancel = () => { cancelled = true; void session.abort(); }; const timeout = () => { timedOut = true; void session.abort(); };
  const timer = setTimeout(timeout, budget.wall_timeout_ms); signal?.addEventListener("abort", cancel, { once: true });
  const unlisten = session.subscribe((event) => {
    if (event.type === "turn_start") { turns += 1; if (turns > budget.model_turn_limit) { turnLimitExceeded = true; void session.abort(); } }
    if (event.type === "message_end" && event.message?.role === "assistant" && !event.message?.content?.some((x: any) => x.type === "toolCall") && !lifecycle.terminal()) plain = true;
    onEvent?.({ type: event.type, turnIndex: event.turnIndex, toolName: event.toolName, isError: event.isError });
  });
  try { await session.prompt(prompt); await session.waitForIdle(); if (timedOut) return "timed_out"; if (cancelled) return "cancelled"; if (turnLimitExceeded) return "turn_limit_exceeded"; if (plain || !lifecycle.terminal()) lifecycle.plainFinal(); return lifecycle.terminal()!; } catch (error) { if (timedOut) return "timed_out"; if (cancelled) return "cancelled"; if (turnLimitExceeded) return "turn_limit_exceeded"; throw error; } finally { clearTimeout(timer); signal?.removeEventListener("abort", cancel); unlisten(); }
}
