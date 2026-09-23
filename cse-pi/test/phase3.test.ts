import assert from "node:assert/strict";
import { lstat, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { parsePhase3WorkOrder, runPhase3, type Phase3WorkOrder } from "../src/phase3.ts";
import { digest, fixture } from "./build-fixture.ts";

function fakeSessionFactory() {
  const seen: Array<{ role: string; model: string; effort: string; tools: string[]; prompt: string }> = [];
  const createSession = async (config: { role: Phase3WorkOrder["role"]; model: { model: string; effort: string }; prompt: string; tools: readonly unknown[] }) => {
    const names = config.tools.map(tool => (tool as { name: string }).name);
    seen.push({ role: config.role, model: config.model.model, effort: config.model.effort, tools: names, prompt: config.prompt });
    const find = (name: string) => config.tools.find(tool => (tool as { name: string }).name === name) as { execute: (id: string, params: any) => Promise<any> } | undefined;
    const session = {
      setActiveToolsByName() {},
      getActiveToolNames: () => names,
      thinkingLevel: config.model.effort,
      async prompt() {
        assert.equal(config.role, "build");
        const runCommand = find("cse_run_command");
        const write = find("cse_write_candidate");
        const remove = find("cse_delete_candidate");
        const submit = find("cse_submit_result");
        assert.ok(runCommand && write && remove && submit);
        assert.equal((await runCommand.execute("read", { command: "cat /workspace/model.txt" })).isError, false);
        assert.equal((await runCommand.execute("deny", { command: "touch /workspace/forbidden.txt" })).isError, true);
        await assert.rejects(() => write.execute("forbidden", { path: "../outside.txt", content: "no" }), /relative|scope|escapes/);
        await remove.execute("delete", { path: "model.txt" });
        await write.execute("allowed", { path: "model.txt", content: "after\n" });
        await submit.execute("submit", { outcome: "accepted", facts: ["changed candidate"], assumptions: [], findings: ["candidate changed"], evidence: ["candidate.diff"], limitations: ["parent must inspect"], deviations: [], questions: [], recommended_parent_action: "inspect candidate" });
      },
      async waitForIdle() {},
      async abort() {},
      subscribe() { return () => {}; },
      getSessionStats: () => ({ tokens: { input: 1, output: 1 } }),
      retryAttempt: 0,
      async dispose() {},
    };
    return session;
  };
  return { createSession, seen };
}

test("parser rejects retired roles and analysis-only fields", () => {
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 1, role: "investigate" }), /schema_version/);
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 3, role: "research" }), /only supports role=build/);
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 3, role: "implement" }), /only supports role=build/);
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 3, role: "build", analysis_checks: [] }), /unknown field/);
});

test("non-build runs reject before result creation", async () => {
  const fixtureData = await fixture();
  try {
    await assert.rejects(() => runPhase3({ ...fixtureData.order, role: "research" as never, worker: { provider: "retired" } }, join(fixtureData.base, "run")), /only supports role=build/);
    await assert.rejects(() => lstat(join(fixtureData.base, "run")), /ENOENT/);
  } finally {
    await rm(fixtureData.base, { recursive: true, force: true });
  }
});

test("build preflight retains candidate evidence and preserves source", async () => {
  const fixtureData = await fixture();
  try {
    const result = await runPhase3(fixtureData.order, join(fixtureData.base, "run"), true);
    assert.equal(result.status, "preflight");
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(body.schema_version, 3);
    assert.equal(body.role, "build");
    assert.equal(body.requested_model.provider, "openai-codex");
    assert.equal(body.supervisor.source_before_after_equal, true);
    assert.equal(body.candidate_identity, fixtureData.order.workspace.expected_identity);
    assert.deepEqual(body.candidate_changes, []);
    assert.equal(await readFile(join(fixtureData.base, "run", "candidate.diff"), "utf8"), "");
    assert.equal(await readFile(join(fixtureData.source, "model.txt"), "utf8"), "before\n");
  } finally {
    await rm(fixtureData.base, { recursive: true, force: true });
  }
});

test("live final-integrity failures override a completed build", async () => {
  const fixtureData = await fixture();
  const fake = fakeSessionFactory();
  try {
    const result = await runPhase3(fixtureData.order, join(fixtureData.base, "run"), false, undefined, { createSession: fake.createSession, beforeFinalIntegrity: async () => rm(join(fixtureData.source, "input.json")) });
    assert.equal(result.status, "failed");
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(body.termination, "integrity_check_failed");
  } finally {
    await rm(fixtureData.base, { recursive: true, force: true });
  }
});

test("build retains scoped candidate diff and denies traversal", async () => {
  const fixtureData = await fixture();
  const fake = fakeSessionFactory();
  try {
    const result = await runPhase3(fixtureData.order, join(fixtureData.base, "run"), false, undefined, { createSession: fake.createSession });
    assert.equal(result.status, "completed");
    assert.equal(await readFile(join(fixtureData.source, "model.txt"), "utf8"), "before\n");
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(body.role, "build");
    assert.equal(body.candidate_changes[0].path, "model.txt");
    assert.equal(body.candidate_changes[0].action, "modified");
    assert.equal(body.supervisor.source_before_after_equal, true);
    assert.match(await readFile(join(fixtureData.base, "run", "candidate.diff"), "utf8"), /model.txt/);
    assert.equal(fake.seen[0].model, "gpt-5.6-luna");
    assert.deepEqual(fake.seen[0].tools.sort(), ["cse_delete_candidate", "cse_run_command", "cse_submit_result", "cse_write_candidate"]);
  } finally {
    await rm(fixtureData.base, { recursive: true, force: true });
  }
});

test("build supports deletion and nested creation in an explicit directory scope", async () => {
  const base = await mkdtemp(join(tmpdir(), "cse-pi-phase3-directory-"));
  const source = join(base, "source");
  await mkdir(join(source, "out"), { recursive: true });
  await writeFile(join(source, "input.json"), '{"value":1}\n');
  await writeFile(join(source, "out", "keep.txt"), "keep\n");
  const inputHash = digest('{"value":1}\n');
  const keepHash = digest("keep\n");
  const order = parsePhase3WorkOrder({
    schema_version: 3,
    task_id: "phase3-directory",
    role: "build",
    objective: "exercise directory scope",
    scientific_question: "are nested changes retained?",
    workspace: { root: source, expected_identity: digest("input.json\0" + inputHash + "\nout/keep.txt\0" + keepHash) },
    context_files: [{ path: "input.json", sha256: inputHash, purpose: "fixture input" }],
    known_context: [],
    constraints: ["bounded"],
    non_goals: [],
    access: { read_paths: ["input.json", "out"], write_paths: ["out"], write_scopes: [{ path: "out", kind: "directory" }], forbidden_paths: [] },
    write_policy: "candidate",
    network_policy: "none",
    expected_artifacts: [],
    acceptance_criteria: ["directory changes"],
    validation: [],
    scientific_checks: [],
    parent_identity: "parent-phase3",
    budget: { wall_timeout_ms: 5000, model_turn_limit: 1, command_timeout_ms: 1000, output_bytes: 65536 },
    specification: { text: "directory scope", required_changes: ["delete keep and create new"], forbidden_changes: [], permitted_paths: ["out"] },
  });
  const createSession = async (config: { model: { effort: string }; tools: readonly unknown[] }) => {
    const names = config.tools.map(tool => (tool as { name: string }).name);
    const find = (name: string) => config.tools.find(tool => (tool as { name: string }).name === name) as { execute: (id: string, params: any) => Promise<unknown> };
    const remove = find("cse_delete_candidate");
    const write = find("cse_write_candidate");
    const submit = find("cse_submit_result");
    return {
      setActiveToolsByName() {},
      getActiveToolNames: () => names,
      thinkingLevel: config.model.effort,
      async prompt() {
        await remove.execute("delete", { path: "out/keep.txt" });
        await write.execute("write", { path: "out/new.txt", content: "new\n" });
        await submit.execute("submit", { outcome: "accepted", facts: ["directory changes"], assumptions: [], findings: ["nested file"], evidence: ["candidate.diff"], limitations: [], deviations: [], questions: [], recommended_parent_action: "inspect" });
      },
      async waitForIdle() {},
      async abort() {},
      subscribe() { return () => {}; },
      async dispose() {},
    };
  };
  try {
    const result = await runPhase3(order, join(base, "run"), false, undefined, { createSession });
    assert.equal(result.status, "completed");
    assert.equal(await readFile(join(source, "out", "keep.txt"), "utf8"), "keep\n");
    assert.equal(await readFile(join(base, "run", "candidate", "out", "new.txt"), "utf8"), "new\n");
    await assert.rejects(() => lstat(join(base, "run", "candidate", "out", "keep.txt")), /ENOENT/);
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.deepEqual(body.candidate_changes.map((change: { path: string; action: string }) => [change.path, change.action]), [["out/keep.txt", "deleted"], ["out/new.txt", "created"]]);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});
