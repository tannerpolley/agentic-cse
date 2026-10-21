import assert from "node:assert/strict";
import test from "node:test";
import { ResultLifecycle, runOneTurn } from "../src/lifecycle.ts";
test("only one structured result terminates a worker", () => { const lifecycle = new ResultLifecycle(); assert.throws(() => lifecycle.plainFinal(), /plain final/); assert.equal(lifecycle.submit("needs_parent_input"), "needs_parent_input"); assert.throws(() => lifecycle.submit("accepted"), /duplicate/); });
test("blocked and inconclusive outcomes are distinct", () => { assert.equal(new ResultLifecycle().submit("blocked"), "blocked"); assert.equal(new ResultLifecycle().submit("inconclusive"), "completed"); });
test("same control flow prompts once and rejects a plain final", async () => { let prompts = 0; const runner = { async prompt() { prompts++; }, async waitForIdle() {}, async abort() {}, subscribe(listener: (event: any) => void) { listener({ type: "agent_start" }); listener({ type: "message_end", message: { role: "assistant", content: [{ type: "text" }] } }); return () => {}; } }; await assert.rejects(() => runOneTurn(runner, "x", new ResultLifecycle(), { wall_timeout_ms: 1000, model_turn_limit: 1 }), /plain final/); assert.equal(prompts, 1); });
test("same control flow captures structured parent input", async () => { const lifecycle = new ResultLifecycle(); const runner = { async prompt() { lifecycle.submit("needs_parent_input"); }, async waitForIdle() {}, async abort() {}, subscribe(listener: (event: any) => void) { listener({ type: "agent_start" }); return () => {}; } }; assert.equal(await runOneTurn(runner, "x", lifecycle, { wall_timeout_ms: 1000, model_turn_limit: 1 }), "needs_parent_input"); });
test("one-turn runner enforces turn, timeout, and cancellation boundaries", async () => {
  let aborted = 0;
  const overLimit = { async prompt() {}, async waitForIdle() {}, async abort() { aborted++; }, subscribe(listener: (event: any) => void) { listener({ type: "turn_start" }); listener({ type: "turn_start" }); return () => {}; } };
  assert.equal(await runOneTurn(overLimit, "x", new ResultLifecycle(), { wall_timeout_ms: 1000, model_turn_limit: 1 }), "turn_limit_exceeded"); assert.equal(aborted, 1);
  const slow = { async prompt() {}, async waitForIdle() { await new Promise(resolve => setTimeout(resolve, 20)); }, async abort() { aborted++; }, subscribe() { return () => {}; } };
  assert.equal(await runOneTurn(slow, "x", new ResultLifecycle(), { wall_timeout_ms: 1, model_turn_limit: 1 }), "timed_out");
  const cancelled = new AbortController(); cancelled.abort();
  assert.equal(await runOneTurn(overLimit, "x", new ResultLifecycle(), { wall_timeout_ms: 1000, model_turn_limit: 1 }, cancelled.signal), "cancelled");
});
