import assert from "node:assert/strict";
import { readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { run } from "../src/worker.ts";
import { fixture } from "./build-fixture.ts";

test("missing configured Pi auth fails after build validation", async () => {
  const data = await fixture(); const previous = process.env.CSE_PI_AGENT_DIR; process.env.CSE_PI_AGENT_DIR = join(data.base, "no-auth");
  try { const result = await run(data.order, join(data.base, "run")); assert.equal(result.status, "failed"); assert.match(await readFile(result.result_path, "utf8"), /Pi auth is unavailable/); }
  finally { if (previous === undefined) delete process.env.CSE_PI_AGENT_DIR; else process.env.CSE_PI_AGENT_DIR = previous; await rm(data.base, { recursive: true, force: true }); }
});
test("unsupported provider is rejected before auth", async () => {
  const data = await fixture(); data.order.worker = { provider: "other", model: "anything", effort: "low" };
  try { const result = await run(data.order, join(data.base, "run"), true); assert.equal(result.status, "failed"); assert.match(await readFile(result.result_path, "utf8"), /unsupported build provider/); }
  finally { await rm(data.base, { recursive: true, force: true }); }
});
test("already-cancelled runs retain a cancellation result", async () => {
  const data = await fixture(); const controller = new AbortController(); controller.abort();
  try { const result = await run(data.order, join(data.base, "run"), true, controller.signal); assert.equal(result.status, "cancelled"); }
  finally { await rm(data.base, { recursive: true, force: true }); }
});
